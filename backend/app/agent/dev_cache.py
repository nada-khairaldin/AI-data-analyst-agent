"""An on-disk cache of LLM responses, for development only.

The Gemini free tier allows **20 generateContent requests per day per model**.
Two verification runs are enough to exhaust a day, which makes iterating on
anything downstream of the model — the explainer, the presenters, the frontend
— disproportionately expensive. This cache makes a repeat of the same prompt
free.

It is deliberately crude, because a sophisticated cache here would be a
liability:

- The key is a hash of the **model id and the complete prompt**, nothing else.
  Any change to the prompt, the schema, the question or the model is a
  different key, so a stale hit is not possible as long as the prompt is a
  pure function of the inputs. It is: ``build_agent_prompt`` takes the
  question, the schema and the tool schemas and nothing hidden.
- There is no expiry and no size limit. It is a development scratch area;
  deleting the directory is the eviction policy.
- It is refused in production by ``app/config.py``, which ANDs the flag with
  ``not is_production``. Serving a cached answer to a real user would be wrong
  in a way that is very hard to spot: the answer looks perfectly fine, it was
  just computed for someone else's dataset.

Streaming is served from the cache too, by replaying the stored text in
chunks. The chunking is synthetic, so timings from a cached stream are
meaningless — which is why the live latency numbers come from
``scratch/check_model.py`` with the cache off.
"""

import hashlib
import json
import logging
import pathlib

from app.config import settings

logger = logging.getLogger(__name__)

# Bumped if the stored format changes, so old entries are simply missed rather
# than misread.
_FORMAT_VERSION = 1


def _root() -> pathlib.Path:
    """The cache directory, resolved relative to backend/ not the cwd."""
    configured = pathlib.Path(settings.llm_dev_cache_dir)
    if configured.is_absolute():
        return configured
    backend_dir = pathlib.Path(__file__).resolve().parent.parent.parent
    return backend_dir / configured


def key_for(model: str, prompt: str) -> str:
    """A stable key for (model, prompt).

    The two parts are length-prefixed before hashing so that no pair of
    (model, prompt) values can collide by running together — without it,
    ("ab", "c") and ("a", "bc") would hash identically.
    """
    digest = hashlib.sha256()
    for part in (str(_FORMAT_VERSION), model, prompt):
        encoded = part.encode("utf-8")
        digest.update(str(len(encoded)).encode("ascii"))
        digest.update(b":")
        digest.update(encoded)
    return digest.hexdigest()


def _path_for(model: str, prompt: str) -> pathlib.Path:
    return _root() / f"{key_for(model, prompt)}.json"


def get(model: str, prompt: str):
    """The cached text, or None. Never raises."""
    if not settings.dev_cache_enabled:
        return None

    path = _path_for(model, prompt)
    try:
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        logger.debug("Dev cache read failed for %s: %s", path.name, error)
        return None

    if payload.get("version") != _FORMAT_VERSION:
        return None

    text = payload.get("text")
    if not isinstance(text, str):
        return None

    logger.info("DEV CACHE HIT  %s  (%s)", model, path.name[:12])
    return text


def put(model: str, prompt: str, text: str) -> None:
    """Store a response. Never raises: a cache failure must not fail a call."""
    if not settings.dev_cache_enabled or not isinstance(text, str):
        return

    path = _path_for(model, prompt)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": _FORMAT_VERSION,
            "model": model,
            # The prompt is stored for debugging. This is also why the
            # directory must stay out of git: prompts embed the dataset's
            # column names and the user's question.
            "prompt": prompt,
            "text": text,
        }
        # Written to a temporary file and moved, so an interrupted write
        # cannot leave a half-written entry that reads as valid JSON.
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary.replace(path)
        logger.info("DEV CACHE STORE %s  (%s)", model, path.name[:12])
    except OSError as error:
        logger.debug("Dev cache write failed for %s: %s", path.name, error)


def chunk(text: str, size: int = 24):
    """Replay cached text as a stream.

    Chunked on whitespace boundaries so a replayed stream looks like a real
    one to anything rendering it incrementally.
    """
    if not text:
        return

    words = text.split(" ")
    buffer = ""
    for word in words:
        candidate = f"{buffer} {word}" if buffer else word
        if len(candidate) >= size:
            yield candidate + " "
            buffer = ""
        else:
            buffer = candidate
    if buffer:
        yield buffer


def stats() -> dict:
    root = _root()
    try:
        entries = list(root.glob("*.json"))
    except OSError:
        entries = []
    return {
        "enabled": settings.dev_cache_enabled,
        "directory": str(root),
        "entries": len(entries),
    }


def clear() -> int:
    """Delete every entry. Returns how many were removed."""
    removed = 0
    for path in _root().glob("*.json"):
        try:
            path.unlink()
            removed += 1
        except OSError:
            pass
    return removed
