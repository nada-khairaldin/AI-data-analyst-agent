"""Request dependencies: the database session and the caller's session id.

``X-Session-Id`` is the whole of the ownership model (PLAN §4, decision Q1d).
Every row the API returns is scoped by it, so this module is the only place
that decides who the caller is — and the only place that creates a session
row.

Two rules here are security-relevant rather than stylistic:

1. **The server never mints an id for the client.** A missing or malformed
   header is ``400 SESSION_REQUIRED``, not a new session. If the server
   invented one, every request with a typo'd header would silently create an
   unreachable session, and the user's datasets would scatter across rows
   nobody can address again.
2. **The id must be a real UUID.** The column is ``uuid``, so a non-UUID would
   fail at the database with a 500 instead of a 400; and validating the shape
   here is what stops an attacker from probing with short guessable strings.

The honest limitation, repeated from PLAN §4 because this is where it is
enforced: this is a **bearer capability, not authentication**. Anyone who
learns the id can read that session's data. ``crypto.randomUUID()`` gives 122
bits, so guessing is not the risk — leaking is.
"""

import uuid

from fastapi import Depends, Header
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import SessionRequired
from app.db.models import Session as SessionRow
from app.db.session import get_db

SESSION_HEADER = "X-Session-Id"


def parse_session_id(raw) -> uuid.UUID:
    """Validate the header value. Raises ``SessionRequired`` if unusable."""
    if not raw or not str(raw).strip():
        raise SessionRequired(
            f"The {SESSION_HEADER} header is required.",
            details={"header": SESSION_HEADER},
        )

    try:
        return uuid.UUID(str(raw).strip())
    except (ValueError, AttributeError, TypeError):
        raise SessionRequired(
            f"The {SESSION_HEADER} header must be a UUID.",
            details={"header": SESSION_HEADER},
        )


async def get_session_id(
    x_session_id: str | None = Header(default=None, alias=SESSION_HEADER),
) -> uuid.UUID:
    """The caller's session id, validated but not yet persisted.

    Used by read-only endpoints: a GET that happens to carry an unknown
    session should return an empty list, not create a row. Only writes call
    ``get_or_create_session``.
    """
    return parse_session_id(x_session_id)


async def get_or_create_session(
    session_id: uuid.UUID = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    """Ensure a ``sessions`` row exists, and refresh ``last_seen_at``.

    An upsert rather than select-then-insert: two requests from a new browser
    can arrive concurrently (the UI loads datasets and conversations at once),
    and the naive version loses that race with a duplicate-key error.

    ``ON CONFLICT DO UPDATE`` is used instead of ``DO NOTHING`` so that
    ``last_seen_at`` moves, which is what a future cleanup job for abandoned
    anonymous sessions will need.
    """
    statement = (
        pg_insert(SessionRow)
        .values(id=session_id)
        .on_conflict_do_update(
            index_elements=[SessionRow.id],
            set_={"last_seen_at": func.now()},
        )
    )
    await db.execute(statement)
    return session_id


async def load_session(db: AsyncSession, session_id: uuid.UUID):
    """The session row, or None. For the dataset-count cap."""
    result = await db.execute(select(SessionRow).where(SessionRow.id == session_id))
    return result.scalar_one_or_none()
