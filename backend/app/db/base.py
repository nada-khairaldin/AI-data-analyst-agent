"""The declarative base and the column conventions every table follows.

Conventions, each chosen once here rather than re-decided per table:

- **UUID primary keys**, because ids appear in URLs. Sequential integers leak
  how many datasets exist and invite enumeration.
- ``gen_random_uuid()`` as a **server** default, so the database can always
  produce a valid row even for an INSERT that did not come from this app.
  It is core Postgres from v13 (this project runs 18.6), so no extension is
  needed — ``pgcrypto`` is only required on older servers.
- ``timestamptz`` everywhere, never a naive timestamp. A naive column silently
  reinterprets its contents when the server's timezone changes.
- **Named constraint conventions.** Without these, Alembic generates
  constraint names like ``ck_1a2b3c`` that differ between autogenerate runs,
  and a later migration cannot drop a constraint it cannot name.
"""

import uuid

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, mapped_column

# Deterministic constraint names. "ix"/"uq"/"ck"/"fk"/"pk" plus the table and
# column, so every name is stable, readable and reproducible.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def uuid_pk():
    """A server-generated UUID primary key."""
    return mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )


def created_at():
    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


def updated_at():
    """Set by the database on insert; the app maintains it on update.

    Deliberately not an ON UPDATE trigger: a trigger would also fire for
    administrative backfills, making "updated_at" mean "last touched by
    anything", which is useless for showing a user when their data changed.
    """
    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
