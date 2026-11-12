"""The single place that builds an LLM client.

Google Gemini via LangChain's ``langchain-google-genai``. **No other module in
the app may talk to a provider** — a test enforces that — so switching
provider again is a rewrite of this file and nothing else.

Everything in here is shaped by one measured fact: the Gemini free tier allows
**20 ``generateContent`` requests per day, per model, per project**. Not per
minute. That single number drives four decisions:

1. **Chains, not models.** ``LLM_PLANNER_MODELS`` and ``LLM_FAST_MODELS`` are
   ordered lists. A 429 moves to the next model *immediately* rather than
   sleeping, because a daily quota does not recover from a backoff of any
   length. Three models is three times the daily capacity.
2. **JSON mode for the planner.** Gemini used to wrap its reply in a
   ````json`` fence on attempt 1 of every question, which failed
   ``json.loads`` and spent a second planner call on the retry — doubling
   consumption. ``response_mime_type="application/json"`` asks for raw JSON,
   and ``strip_code_fence`` is the deterministic belt to that braces.
3. **Thinking configured per MODEL, never per role.** Capability belongs to
   the model. See ``_thinking_kwargs``.
4. **A development cache.** ``LLM_DEV_CACHE=true`` makes a repeated prompt
   free. Refused in production.

Two integration details that are not obvious and have each cost time:

- ``response.content`` is a **list of content blocks**, not a string, under
  langchain-core 1.x: ``[{'type': 'text', 'text': 'OK', ...}]``. Joining it
  raises ``TypeError: sequence item 0: expected str instance, list found``.
  ``response.text`` is the accessor that returns a plain string.
- The API key is passed **explicitly**. The SDK checks ``GOOGLE_API_KEY`` then
  ``GEMINI_API_KEY``, and there is a known failure when only the latter is set
  alongside Application Default Credentials.
"""

import logging
import random
import time

from langchain_google_genai import ChatGoogleGenerativeAI

from app.agent import dev_cache
from app.agent.text_utils import strip_code_fence
from app.config import settings

logger = logging.getLogger(__name__)

PLANNER = "planner"
FAST = "fast"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class LLMError(RuntimeError):
    """Base class, so a caller can catch every provider failure at once."""

    status_code = 502
    code = "LLM_UNAVAILABLE"

    def __init__(self, message, *, retry_after=None):
        super().__init__(message)
        self.message = message
        self.retry_after = retry_after


class LLMNotConfigured(LLMError):
    """No API key or no model configured.

    A deployment mistake the operator must fix; retrying never helps.
    """

    status_code = 503
    code = "LLM_NOT_CONFIGURED"


class LLMRateLimited(LLMError):
    """Every model in the chain is out of quota.

    Its own class because it is the one provider failure with a real user
    response — wait and try again — and because it must surface as HTTP 429
    rather than a generic 500.
    """

    status_code = 429
    code = "LLM_RATE_LIMITED"


# ---------------------------------------------------------------------------
# Thinking capability, discovered per model
# ---------------------------------------------------------------------------

# "Supports thinking" and "can have thinking turned off" are different
# properties, and the API only exposes the first. models.list reports
# thinking=True for every model in both chains, yet gemini-3.5-flash-lite
# accepts a thinking budget of 512 or -1 and REJECTS 0 with a bare
# INVALID_ARGUMENT. There is no way to ask which models allow 0, so it is
# learned: a model that refuses the budget is recorded here and from then on
# is built without one.
_rejects_thinking_budget: set[str] = set()


def _thinking_kwargs(model: str) -> dict:
    """Thinking settings for one model, by capability rather than by role."""
    budget = settings.llm_thinking_budget
    if budget is None or model in _rejects_thinking_budget:
        return {}
    return {"thinking_budget": budget}


def _looks_like_thinking_rejection(error: Exception) -> bool:
    return "invalid_argument" in str(error).lower()


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------

_clients: dict[tuple, ChatGoogleGenerativeAI] = {}


def _require_key() -> str:
    if not settings.gemini_api_key:
        raise LLMNotConfigured(
            "No Gemini API key configured. Set GEMINI_API_KEY in backend/.env."
        )
    return settings.gemini_api_key


def chain_for(role: str) -> list[str]:
    """The ordered model chain for a role."""
    if role == PLANNER:
        chain = settings.planner_models
        setting = "LLM_PLANNER_MODELS"
    elif role == FAST:
        chain = settings.fast_models
        setting = "LLM_FAST_MODELS"
    else:
        raise ValueError(f"Unknown model role: {role!r}")

    if not chain:
        raise LLMNotConfigured(f"No models configured for {role!r}. Set {setting}.")
    return chain


def model_name(role: str) -> str:
    """The first model in the role's chain — the one normally used."""
    return chain_for(role)[0]


def get_model(model: str, *, role: str = FAST) -> ChatGoogleGenerativeAI:
    """A client for one model, built once and reused.

    Cached on the full configuration, not just the model name, so that
    learning a model rejects a thinking budget produces a genuinely new
    client rather than returning the broken cached one.

    ``max_retries=0`` is deliberate: the integration's own retry is opaque and
    cannot distinguish a 429 from a 500, so retrying is handled here where the
    difference decides between backing off and changing model.
    """
    thinking = _thinking_kwargs(model)
    json_mode = role == PLANNER and settings.llm_planner_json_mode

    cache_key = (model, json_mode, tuple(sorted(thinking.items())))
    if cache_key in _clients:
        return _clients[cache_key]

    kwargs = {
        "model": model,
        "google_api_key": _require_key(),
        "temperature": 0,
        "timeout": settings.llm_timeout_seconds,
        "max_retries": 0,
        **thinking,
    }
    if json_mode:
        kwargs["response_mime_type"] = "application/json"

    client = ChatGoogleGenerativeAI(**kwargs)
    _clients[cache_key] = client
    return client


def reset_models() -> None:
    """Drop cached clients and learned capabilities. For tests."""
    _clients.clear()
    _rejects_thinking_budget.clear()


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------

_RATE_LIMIT_MARKERS = (
    "429",
    "resource_exhausted",
    "resourceexhausted",
    "quota",
    "rate limit",
    "ratelimit",
    "too many requests",
)


def _is_rate_limit(error: Exception) -> bool:
    """Detect a 429 across the several shapes it arrives in.

    google-api-core may raise ``ResourceExhausted``, the REST transport an
    HTTP error, and LangChain may wrap either. Matching the text is inelegant
    but it is the only thing all three have in common.
    """
    if type(error).__name__ in ("ResourceExhausted", "TooManyRequests"):
        return True
    text = str(error).lower()
    return any(marker in text for marker in _RATE_LIMIT_MARKERS)


def _retry_after(error: Exception):
    """Seconds the provider asked us to wait, if it said.

    Capped: against a *daily* quota Gemini returns a retryDelay of nine hours,
    which is not a sleep any request can take. Beyond the cap the honest
    answer is a 429 to the user.
    """
    for attr in ("retry_after", "retry_delay"):
        value = getattr(error, attr, None)
        seconds = getattr(value, "seconds", value)
        if isinstance(seconds, (int, float)) and 0 < seconds <= 120:
            return float(seconds)
    return None


def _wrap(error: Exception, *, model: str | None = None) -> LLMError:
    if isinstance(error, LLMError):
        return error
    if _is_rate_limit(error):
        return LLMRateLimited(
            "The Gemini free tier's rate limit was reached on every available "
            "model. Wait a minute and ask again.",
            retry_after=_retry_after(error),
        )
    logger.warning(
        "LLM call failed on %s: %s: %s", model, type(error).__name__, error
    )
    return LLMError("The language model is temporarily unavailable. Please try again.")


# ---------------------------------------------------------------------------
# The call loop
# ---------------------------------------------------------------------------


def _attempt(model, role, operation, what):
    """One call against one model, retrying once if thinking is refused.

    The thinking retry is not a general retry: it fires only when a budget was
    actually applied and the model rejected the request, which is a
    configuration problem this process can fix by itself and then never hit
    again.
    """
    try:
        return operation(get_model(model, role=role))
    except Exception as error:
        applied = bool(_thinking_kwargs(model))
        if applied and _looks_like_thinking_rejection(error):
            logger.warning(
                "%s rejected thinking_budget=%s; retrying without it and "
                "remembering for this process.",
                model,
                settings.llm_thinking_budget,
            )
            _rejects_thinking_budget.add(model)
            return operation(get_model(model, role=role))
        raise


def _run(role: str, operation, *, what: str):
    """Run ``operation`` across the role's chain, then back off and repeat.

    The order matters and is the whole point of this function:

    - A 429 tries the **next model immediately**. The quota is per model, so
      another model may well answer, and a daily limit will not clear by
      waiting.
    - Only once *every* model has refused does it back off and try the chain
      again, which is what recovers a per-minute limit.
    - Anything that is not a 429 fails straight away. A malformed request will
      fail identically on every model in the chain, and trying all of them
      would burn three days' quota on one bad prompt.
    """
    chain = chain_for(role)
    rounds = max(1, settings.llm_max_retries + 1)
    last_rate_limit = None

    for round_number in range(1, rounds + 1):
        for model in chain:
            try:
                result = operation(model)
            except Exception as error:
                wrapped = _wrap(error, model=model)
                if not isinstance(wrapped, LLMRateLimited):
                    raise wrapped from error

                last_rate_limit = wrapped
                logger.warning(
                    "Rate limited on %s (%s); trying the next model",
                    model,
                    what,
                )
                continue

            if round_number > 1 or model != chain[0]:
                logger.info("%s answered by fallback model %s", what, model)
            else:
                logger.info("%s answered by %s", what, model)
            return result, model

        if round_number < rounds:
            # Every model refused. Now a wait is worth something, but only
            # for a per-minute limit; _retry_after caps the provider's
            # nine-hour daily suggestion out of consideration.
            delay = (last_rate_limit and last_rate_limit.retry_after) or min(
                2 ** (round_number - 1) * 2.0, 30.0
            )
            delay += random.uniform(0, 0.5)
            logger.warning(
                "All %d model(s) rate limited for %s, round %d/%d; waiting %.1fs",
                len(chain),
                what,
                round_number,
                rounds,
                delay,
            )
            time.sleep(delay)

    raise last_rate_limit or LLMError("The language model could not be reached.")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def complete(prompt: str, *, role: str = PLANNER) -> str:
    """Send one prompt and return the reply as a clean string.

    The reply is passed through ``strip_code_fence`` because JSON mode is a
    request, not a guarantee, and a fenced reply costs a whole extra call when
    the parse fails.
    """
    for model in chain_for(role):
        cached = dev_cache.get(model, prompt)
        if cached is not None:
            return strip_code_fence(cached)

    def operation(model):
        response = _attempt(
            model, role, lambda client: client.invoke(prompt), "completion"
        )
        return response.text

    text, model = _run(role, operation, what="completion")
    dev_cache.put(model, prompt, text or "")
    return strip_code_fence(text)


def stream(prompt: str, *, role: str = FAST):
    """Yield the reply in text chunks as they arrive.

    Defaults to the fast model because what gets streamed is the answer text,
    which ``explainer.py`` produces.

    No fence stripping here: a fence can only be recognised once the whole
    reply is in hand, and the point of streaming is to emit text before that.
    Streamed output goes to a human, not to ``json.loads``, so a stray fence
    is cosmetic rather than fatal — which is exactly why the explainer must
    switch to plain text before feature 5.5 (docs/PLAN.md §6B).
    """
    for model in chain_for(role):
        cached = dev_cache.get(model, prompt)
        if cached is not None:
            yield from dev_cache.chunk(cached)
            return

    def operation(model):
        return _attempt(
            model, role, lambda client: iter(client.stream(prompt)), "stream"
        )

    iterator, model = _run(role, operation, what="stream")

    collected = []
    try:
        for chunk in iterator:
            text = chunk.text
            if text:
                collected.append(text)
                yield text
    except Exception as error:
        # A mid-stream failure cannot be retried without replaying text the
        # user has already seen, so it propagates.
        raise _wrap(error, model=model) from error

    dev_cache.put(model, prompt, "".join(collected))


async def astream(prompt: str, *, role: str = FAST):
    """Async version of `stream`, for the SSE path.

    The sync `stream` would block the event loop for the whole explainer
    call, which is exactly the latency SSE exists to hide.

    The chain walk and the retry are done synchronously before the first
    chunk — that part is a single call setup — and only the iteration is
    async.
    """
    for model in chain_for(role):
        cached = dev_cache.get(model, prompt)
        if cached is not None:
            for piece in dev_cache.chunk(cached):
                yield piece
            return

    chain = chain_for(role)
    last_rate_limit = None

    for model in chain:
        try:
            client = get_model(model, role=role)
            collected = []
            async for chunk in client.astream(prompt):
                text = chunk.text
                if text:
                    collected.append(text)
                    yield text
            logger.info("astream answered by %s", model)
            dev_cache.put(model, prompt, "".join(collected))
            return
        except Exception as error:
            wrapped = _wrap(error, model=model)
            if not isinstance(wrapped, LLMRateLimited):
                raise wrapped from error
            # Only safe to fall through while nothing has been yielded; once
            # text has reached the client it cannot be replayed.
            last_rate_limit = wrapped
            logger.warning("Rate limited on %s (astream); trying the next model", model)
            continue

    raise last_rate_limit or LLMError("The language model could not be reached.")
