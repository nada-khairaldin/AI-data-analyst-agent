"""Connection-URL translation, with no engine as a side effect.

Separate from session.py so that alembic/env.py can reuse this logic without
importing session.py, which builds an engine on the POOLED url at import time.
Alembic must never touch the pooler (docs/PLAN.md §8), so that import had to
not happen at all.
"""

from urllib.parse import urlencode, urlsplit, urlunsplit

# Parameters libpq accepts and asyncpg does not. Dropped from the URL and,
# where they matter, re-expressed in connect_args.
_LIBPQ_ONLY_PARAMS = ("sslmode", "channel_binding", "options", "target_session_attrs")


def normalize_async_url(url: str) -> str:
    """Turn a Neon connection string into one asyncpg can use.

    Returns an empty string unchanged so that an unconfigured environment
    fails at connect time with a clear message, rather than at import time.
    """
    if not url:
        return url

    parts = urlsplit(url)

    scheme = parts.scheme
    if scheme in ("postgres", "postgresql"):
        scheme = "postgresql+asyncpg"

    kept = [
        (key, value)
        for key, value in _parse_pairs(parts.query)
        if key.lower() not in _LIBPQ_ONLY_PARAMS
    ]

    # SQLAlchemy keeps its own cache of asyncpg prepared statements, separate
    # from asyncpg's. It is equally unsafe through a transaction-mode pooler,
    # and the dialect only accepts the setting from the URL query string --
    # as a create_async_engine() keyword it raises "Invalid argument(s)".
    if not any(key.lower() == "prepared_statement_cache_size" for key, _ in kept):
        kept.append(("prepared_statement_cache_size", "0"))

    return urlunsplit(
        (scheme, parts.netloc, parts.path, urlencode(kept), parts.fragment)
    )


def _parse_pairs(query: str):
    if not query:
        return []
    pairs = []
    for chunk in query.split("&"):
        if not chunk:
            continue
        key, _, value = chunk.partition("=")
        pairs.append((key, value))
    return pairs


def requires_tls(url: str) -> bool:
    """True when the original URL asked for TLS.

    Neon requires it, and the parameter that says so is one of the ones
    stripped above, so the answer has to be read before normalising.
    """
    if not url:
        return False
    query = urlsplit(url).query.lower()
    return "sslmode=require" in query or "sslmode=verify" in query


def connect_args_for(url: str) -> dict:
    """Keyword arguments handed to ``asyncpg.connect``.

    Only names asyncpg itself accepts belong here. SQLAlchemy's own
    ``prepared_statement_cache_size`` is a *dialect* argument and is passed to
    create_async_engine instead — putting it in connect_args reaches
    asyncpg.connect(), which rejects it with a TypeError.
    """
    args = {
        # Required behind Neon's pooler. See the module docstring.
        "statement_cache_size": 0,
    }
    if requires_tls(url):
        args["ssl"] = "require"
    return args
