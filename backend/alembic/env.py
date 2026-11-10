"""Alembic environment.

Two rules are enforced here rather than left to discipline, because getting
either wrong is expensive and the failure is confusing:

1. **The direct URL only.** Migrations run against ``DATABASE_URL_DIRECT``,
   never the pooled ``DATABASE_URL``. Neon's pooled endpoint is PgBouncer in
   transaction mode, which breaks DDL that spans statements and leaves
   migrations *partially applied* — the worst possible state, because
   ``alembic upgrade`` then refuses to run again and the schema matches
   neither the old nor the new version. There is deliberately **no fallback**
   to ``DATABASE_URL``: a missing direct URL raises, because silently
   migrating through the pooler is worse than not migrating.

2. **A pooler URL is rejected outright.** Even if someone pastes a pooled
   string into ``DATABASE_URL_DIRECT``, the hostname is checked for
   ``-pooler`` and the run aborts with an explanation.

``app.db.url`` is imported rather than ``app.db.session`` on purpose: importing
session.py would build an engine on the pooled URL as a side effect, which is
exactly what this file exists to avoid.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import settings
from app.db.url import connect_args_for, normalize_async_url

# Importing the models package registers all nine tables on Base.metadata.
# Without this, --autogenerate would see an empty metadata and write a
# migration that DROPS every table.
from app.db.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def migration_url() -> str:
    """The direct URL, validated. Raises rather than falling back."""
    raw = settings.database_url_direct

    if not raw:
        raise RuntimeError(
            "DATABASE_URL_DIRECT is not set. Alembic must use Neon's DIRECT "
            "connection string (the host WITHOUT '-pooler'). There is no "
            "fallback to DATABASE_URL on purpose: migrating through the "
            "pooler can leave migrations partially applied."
        )

    if "-pooler" in raw:
        raise RuntimeError(
            "DATABASE_URL_DIRECT points at Neon's POOLED endpoint (its host "
            "contains '-pooler'). Use the direct connection string instead — "
            "DDL through a transaction-mode pooler can be applied partially. "
            "See docs/PLAN.md §8."
        )

    return normalize_async_url(raw)


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting, for `alembic upgrade --sql`."""
    context.configure(
        url=migration_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # Alembic does NOT detect either of these by default, and both drift
        # silently. docs/PLAN.md §4 warns that autogenerate misses enum and
        # server-default changes; this is the switch that fixes half of it.
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    url = migration_url()
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = url

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args_for(settings.database_url_direct),
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
