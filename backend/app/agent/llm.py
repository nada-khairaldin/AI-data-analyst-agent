"""The single place that builds an LLM client.

Before this module, ``agent/core.py`` and ``agent/explainer.py`` each
constructed their own ``OpenAI`` client, each read ``HUGGINGFACE_API_KEY``
directly, and each hardcoded the same model id. That is two places to update
for one change, and it is how the model id ended up duplicated.

The client is OpenAI-*compatible*, not necessarily OpenAI: ``LLM_BASE_URL``
points at the Hugging Face router today. Swapping provider is a config change.

This is also the seam where LangChain arrives in feature 5 (docs/PLAN.md §6):
callers already depend on ``complete()``, not on a vendor client, so the
replacement is confined to this file.
"""

from functools import lru_cache

from openai import OpenAI

from app.config import settings


class LLMNotConfigured(RuntimeError):
    """Raised when a call is attempted without a key or model configured.

    Separate from a provider failure on purpose: this one is a deployment
    mistake the operator must fix, not a transient error worth retrying.
    """


@lru_cache
def get_client() -> OpenAI:
    """The shared client. Built once; the SDK handles connection pooling.

    Timeout and retries come from config because the original code set
    neither, so a hung provider hung the request for as long as the socket
    stayed open.
    """
    api_key = settings.resolved_llm_api_key
    if not api_key:
        raise LLMNotConfigured(
            "No LLM API key configured. Set LLM_API_KEY in backend/.env "
            "(HUGGINGFACE_API_KEY is still read as a fallback)."
        )

    return OpenAI(
        base_url=settings.llm_base_url,
        api_key=api_key,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )


def _require_model() -> str:
    if not settings.llm_model:
        raise LLMNotConfigured(
            "No LLM model configured. Set LLM_MODEL in backend/.env."
        )
    return settings.llm_model


def complete(prompt: str) -> str:
    """Send a single user-role prompt and return the whole reply.

    Behaviour is identical to the ``call_llm`` that used to live in core.py:
    one user message, no system prompt, no temperature override. Only the
    client construction moved.
    """
    completion = get_client().chat.completions.create(
        model=_require_model(),
        messages=[{"role": "user", "content": prompt}],
    )
    return completion.choices[0].message.content


def stream(prompt: str):
    """Yield the reply in chunks as they arrive.

    Not used by the legacy endpoints. It exists now so that step A4 can prove
    the configured model actually supports streaming, because the whole
    streaming design in docs/PLAN.md §6B depends on that being true and there
    is no point discovering otherwise in feature 5.5.
    """
    response = get_client().chat.completions.create(
        model=_require_model(),
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )

    for chunk in response:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        text = getattr(delta, "content", None)
        if text:
            yield text
