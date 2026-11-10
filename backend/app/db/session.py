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

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings
from app.db.url import connect_args_for, normalize_async_url

logger = logging.getLogger(__name__)

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
