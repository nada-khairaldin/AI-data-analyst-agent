"""The single place that builds an LLM client.

Google Gemini via LangChain's ``langchain-google-genai`` integration. **No
other module in the app may talk to a provider** — a test enforces that — so
switching provider again is a rewrite of this file and nothing else. That rule
has already paid for itself once: this module previously held an
OpenAI-compatible client pointed at the Hugging Face router, and replacing it
touched two call sites.

Two models, because the work is two different jobs:

- **planner** (``LLM_PLANNER_MODEL``) — ``core.py``. Has to emit a tool plan
  that survives ``validators.py``, so it gets the stronger model.
- **fast** (``LLM_FAST_MODEL``) — ``explainer.py``, and later the condenser
  and summariser. Cheap rewriting work that runs several times per turn; on a
  free tier, running it on the big model would burn the quota for no gain.

Three things about this integration that are not obvious:

1. **``response.content`` is a list of content blocks, not a string.** Under
   langchain-core 1.x a reply is
   ``[{'type': 'text', 'text': 'OK', 'extras': {...}}]``. Joining it as a
   string raises ``TypeError: sequence item 0: expected str instance, list
   found``. ``response.text`` is the accessor that returns a plain string, and
   it is the only one used here.
2. **The key is passed explicitly.** The SDK checks ``GOOGLE_API_KEY`` then
   ``GEMINI_API_KEY``, and there is an open issue where having only
   ``GEMINI_API_KEY`` set alongside Application Default Credentials fails
   authentication outright. Passing ``google_api_key`` avoids the lookup.
3. **``gemini-3.8-flash`` is a reasoning model.** By default it spends most of
   its output budget on hidden thinking tokens. See
   ``LLM_PLANNER_THINKING_BUDGET``.
"""

import logging
import random
import time
from functools import lru_cache

from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import settings

logger = logging.getLogger(__name__)

PLANNER = "planner"
FAST = "fast"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class LLMError(RuntimeError):
    """Base class, so a caller can catch every provider failure at once."""

    #: What the API layer should turn this into. See app/api/errors.py.
    status_code = 502
    code = "LLM_UNAVAILABLE"

    def __init__(self, message, *, retry_after=None):
        super().__init__(message)
        self.message = message
        self.retry_after = retry_after


class LLMNotConfigured(LLMError):
    """No API key or no model configured.

    Separate from a provider failure on purpose: this one is a deployment
    mistake the operator must fix, and retrying will never help.
    """

    status_code = 503
    code = "LLM_NOT_CONFIGURED"


class LLMRateLimited(LLMError):
    """The free tier's quota is exhausted for now.

    Its own class because it is the one provider failure with a real user
    response — wait and try again — and because it must surface as HTTP 429
    rather than a generic 500.
    """

    status_code = 429
    code = "LLM_RATE_LIMITED"


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------


def _require_key() -> str:
    if not settings.gemini_api_key:
        raise LLMNotConfigured(
            "No Gemini API key configured. Set GEMINI_API_KEY in backend/.env."
        )
    return settings.gemini_api_key


def model_name(role: str) -> str:
    name = (
        settings.llm_planner_model if role == PLANNER else settings.llm_fast_model
    )
    if not name:
        raise LLMNotConfigured(
            f"No model configured for the {role!r} role. Set "
            f"{'LLM_PLANNER_MODEL' if role == PLANNER else 'LLM_FAST_MODEL'}."
        )
    return name


@lru_cache(maxsize=2)
def get_model(role: str = PLANNER) -> ChatGoogleGenerativeAI:
    """The shared client for a role. Built once per process.

    ``max_retries=0`` is deliberate: the integration's own retry is opaque and
    does not distinguish a 429 from a 500, so backoff is handled in
    ``_call_with_retry`` where the distinction can be made and logged.
    """
    if role not in (PLANNER, FAST):
        raise ValueError(f"Unknown model role: {role!r}")

    kwargs = {
        "model": model_name(role),
        "google_api_key": _require_key(),
        "temperature": 0,
        "timeout": settings.llm_timeout_seconds,
        "max_retries": 0,
    }

    # Only the planner is a reasoning model, and only it accepts a budget
    # worth setting. None means "use the model default".
    if role == PLANNER and settings.llm_planner_thinking_budget is not None:
        kwargs["thinking_budget"] = settings.llm_planner_thinking_budget

    return ChatGoogleGenerativeAI(**kwargs)


def reset_models() -> None:
    """Drop the cached clients. For tests that change configuration."""
    get_model.cache_clear()


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

    google-api-core may raise ``ResourceExhausted``, the REST transport may
    raise an HTTP error, and LangChain may wrap either. Matching the text is
    inelegant but it is the only thing all three have in common, and the cost
    of a false negative is retrying a non-retryable error twice.
    """
    if type(error).__name__ in ("ResourceExhausted", "TooManyRequests"):
        return True
    text = str(error).lower()
    return any(marker in text for marker in _RATE_LIMIT_MARKERS)


def _retry_after(error: Exception):
    """Seconds the provider asked us to wait, if it said."""
    for attr in ("retry_after", "retry_delay"):
        value = getattr(error, attr, None)
        seconds = getattr(value, "seconds", value)
        if isinstance(seconds, (int, float)) and seconds > 0:
            return float(seconds)
    return None


def _wrap(error: Exception, *, role: str | None = None) -> LLMError:
    if isinstance(error, LLMError):
        return error
    if _is_rate_limit(error):
        return LLMRateLimited(
            "The Gemini free tier's rate limit was reached. Wait a minute and "
            "ask again.",
            retry_after=_retry_after(error),
        )

    # A 400 on the planner is very likely the thinking budget: the budget is
    # applied by ROLE, not by model capability, so pointing
    # LLM_PLANNER_MODEL at a model that does not accept one (any `-lite`
    # model, for instance) fails every call with a bare INVALID_ARGUMENT that
    # says nothing about why. Worth naming, because the fix is one env var.
    if (
        role == PLANNER
        and settings.llm_planner_thinking_budget is not None
        and "invalid_argument" in str(error).lower()
    ):
        logger.warning(
            "INVALID_ARGUMENT from %s with thinking_budget=%s. Models that do "
            "not support a thinking budget reject it. Set "
            "LLM_PLANNER_THINKING_BUDGET blank for this model.",
            model_name(PLANNER),
            settings.llm_planner_thinking_budget,
        )
        return LLMError(
            "The planner model rejected its configuration. If "
            "LLM_PLANNER_MODEL was changed, LLM_PLANNER_THINKING_BUDGET may "
            "need to be left blank — not every model accepts one."
        )
    # The provider's own message can be long and full of internals, so it is
    # logged rather than returned.
    logger.warning("LLM call failed: %s: %s", type(error).__name__, error)
    return LLMError(
        "The language model is temporarily unavailable. Please try again."
    )


def _call_with_retry(role: str, operation, *, what: str):
    """Run ``operation`` on the role's model, retrying only a 429.

    Nothing else is retried: a malformed request or an auth failure will fail
    identically the second time and the user just waits longer for it.
    """
    attempts = max(1, settings.llm_max_retries + 1)
    model = get_model(role)

    for attempt in range(1, attempts + 1):
        try:
            return operation(model)
        except Exception as error:
            wrapped = _wrap(error, role=role)

            if not isinstance(wrapped, LLMRateLimited) or attempt == attempts:
                raise wrapped from error

            # Exponential backoff with jitter. Jitter matters because the
            # condenser, planner and explainer of one turn can be rate-limited
            # within milliseconds of each other and would otherwise retry in
            # lockstep.
            delay = wrapped.retry_after or min(2 ** (attempt - 1) * 2.0, 30.0)
            delay += random.uniform(0, 0.5)
            logger.warning(
                "Rate limited on %s (%s), attempt %d/%d; retrying in %.1fs",
                what,
                model_name(role),
                attempt,
                attempts,
                delay,
            )
            time.sleep(delay)

    raise LLMError("The language model could not be reached.")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def complete(prompt: str, *, role: str = PLANNER) -> str:
    """Send one prompt and return the whole reply as a string.

    ``.text`` rather than ``.content``: see note 1 in the module docstring.
    """
    response = _call_with_retry(
        role, lambda model: model.invoke(prompt), what="completion"
    )
    return response.text


def stream(prompt: str, *, role: str = FAST):
    """Yield the reply in text chunks as they arrive.

    Defaults to the fast model because the thing being streamed is the answer
    text, which ``explainer.py`` produces. Retry applies to establishing the
    stream; once chunks are flowing a mid-stream failure cannot be retried
    without replaying text the user has already seen, so it propagates.
    """
    iterator = _call_with_retry(
        role, lambda model: iter(model.stream(prompt)), what="stream"
    )

    try:
        for chunk in iterator:
            text = chunk.text
            if text:
                yield text
    except Exception as error:
        raise _wrap(error, role=role) from error
