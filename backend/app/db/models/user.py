"""users — created EMPTY in the first migration.

Nothing writes to this table yet. It exists from day one so that
``sessions.user_id`` has a real foreign key to point at, which is what makes
"link to a real account later" a one-statement change instead of a migration
over live data (docs/PLAN.md §4, decision Q1d).
"""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at, uuid_pk


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = uuid_pk()
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at = created_at()

    sessions: Mapped[list["Session"]] = relationship(  # noqa: F821
        back_populates="user"
    )
