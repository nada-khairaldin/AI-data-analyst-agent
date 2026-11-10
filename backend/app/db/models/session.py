"""sessions — the ownership root for everything a user uploads.

The id is **supplied by the browser** (``crypto.randomUUID()``), so there is no
server default here: the server must reject a malformed id rather than mint a
row for it, or a typo creates an orphan session nobody can reach.

``datasets`` and ``conversations`` carry ``session_id``, never ``user_id``. That
is the whole point — signing up later is
``UPDATE sessions SET user_id = ... WHERE id = ...`` and every dataset and
conversation is claimed at once, with no backfill.
"""

from sqlalchemy import DateTime, ForeignKey, Index, Integer, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at


class Session(Base):
    __tablename__ = "sessions"

    # No default: the client supplies this.
    id: Mapped[str] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)

    # SET NULL, not CASCADE: deleting an account must un-link the data, never
    # silently destroy it.
    user_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = created_at()
    last_seen_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Denormalised so the 20-dataset cap is a comparison, not a COUNT(*) on
    # every upload. Maintained in the same transaction as the dataset insert.
    dataset_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    user: Mapped["User | None"] = relationship(  # noqa: F821
        back_populates="sessions"
    )
    datasets: Mapped[list["Dataset"]] = relationship(  # noqa: F821
        back_populates="session", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # Partial: the overwhelming majority of rows are anonymous, and an
        # index over a column that is almost entirely NULL is mostly dead
        # weight.
        Index(
            "ix_sessions_user_id",
            "user_id",
            postgresql_where=text("user_id IS NOT NULL"),
        ),
    )
