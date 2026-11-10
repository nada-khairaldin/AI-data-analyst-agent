"""The async engine and session factory.

Two things here are load-bearing and neither is obvious from the Neon
dashboard, so both are explained rather than just set.

1. **The URL has to be rewritten.** Neon hands out
   ``postgresql://...?sslmode=require&channel_binding=require``. SQLAlchemy
   needs the driver in the scheme (``postgresql+asyncpg``), and asyncpg does
   *not* understand either query parameter: it takes ``ssl=`` instead, and an
   unrecognised keyword is a hard connection error. So ``sslmode`` and
   ``channel_binding`` are stripped from the URL and TLS is requested through
   connect_args. Leaving them in produces a TypeError about an unexpected
   keyword argument, which reads like a library bug rather than a URL problem.

2. **Statement caching must be off behind the pooler.** Neon's pooled endpoint
   is PgBouncer in transaction mode, so a prepared statement cached on one
   logical connection may be looked up on a different physical one, and the
   query fails with a confusing "prepared statement does not exist" at random.
   asyncpg caches by default, so ``statement_cache_size=0`` is required, not
   an optimisation.
"""

import logging
from urllib.parse import urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

logger = logging.getLogger(__name__)

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


engine = create_async_engine(
    normalize_async_url(settings.database_url),
    connect_args=connect_args_for(settings.database_url),
    # Neon autosuspends an idle compute, which silently kills pooled sockets.
    # pre_ping costs one round trip and turns "random dead connection" into a
    # transparent reconnect; pool_recycle keeps sockets younger than the
    # idle timeout in the first place.
    pool_pre_ping=True,
    pool_recycle=300,
    # Deliberately small. A free Neon compute has a low connection ceiling and
    # the pooler is doing the real multiplexing.
    pool_size=5,
    max_overflow=5,
    echo=False,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # keeps ORM objects usable after commit
    autoflush=False,
)


async def get_db():
    """FastAPI dependency yielding one session per request."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
