"""conversations, messages and conversation_summaries.

``messages`` is both the UI's history and the condenser's memory — one table,
one source of truth. That is the central design decision of docs/PLAN.md §6:
anything that keeps conversational memory separately has to be reconciled with
what the user can see, and the two drift.
"""

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at, uuid_pk

MESSAGE_ROLES = ("user", "agent")
# Mirrors the agent's own statuses. 'failed' is written when a stream dies
# mid-turn, so a conversation can never hold a user message with no reply.
MESSAGE_STATUSES = ("ready", "needs_clarification", "cannot_answer", "failed")
RESULT_KINDS = ("table", "scalar")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = uuid_pk()

    # not null because a question is meaningless without a dataset — the
    # schema enforces what the UI already assumes.
    dataset_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Denormalised from datasets so cross-dataset search and any ownership
    # check need no join.
    session_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String, nullable=False, server_default="New Conversation"
    )

    # message_count and last_message_at are denormalised deliberately: the
    # sidebar renders both for every conversation, and a COUNT(*)/MAX()
    # subquery per row is the classic N+1 on this app's most frequent query.
    message_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    # Counted in COMPLETED user+agent pairs, never half a pair. This is what
    # the history window and the summary trigger are measured in.
    exchange_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    last_message_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at = created_at()

    dataset: Mapped["Dataset"] = relationship(  # noqa: F821
        back_populates="conversations"
    )
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
    summary: Mapped["ConversationSummary | None"] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", uselist=False
    )

    __table_args__ = (
        Index(
            "ix_conversations_dataset_id_last_message_at",
            "dataset_id",
            text("last_message_at DESC"),
        ),
        Index(
            "ix_conversations_session_id_last_message_at",
            "session_id",
            text("last_message_at DESC"),
        ),
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = uuid_pk()
    conversation_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # The standalone question the planner actually received. Earns its column
    # three times: it is shown to the user as "Understood as: ...", so it must
    # survive a reload; it is what the NEXT turn's condenser reads, so each
    # turn stays one hop from the truth instead of re-deriving the chain; and
    # it is the debugging record that separates a condensation failure from a
    # planning failure.
    condensed_question: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Kept raw as well as rendered, so a prompt or presenter change can be
    # replayed over old conversations without another LLM call.
    analysis_plan: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    chart_plan: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result_data: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # A plan with no group_by returns a SCALAR, not rows. Without this the
    # frontend cannot tell which renderer to use.
    result_kind: Mapped[str | None] = mapped_column(String, nullable=True)
    plan_display: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # One integer that will tell you whether the slow part is the LLM or
    # pandas. Cheap now, impossible to reconstruct later.
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at = created_at()

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

    __table_args__ = (
        Index("ix_messages_conversation_id_created_at", "conversation_id", "created_at"),
        CheckConstraint("role in ('user','agent')", name="role_valid"),
        # Keeps condensed_question off user rows, where it is meaningless.
        CheckConstraint(
            "role = 'agent' or condensed_question is null",
            name="condensed_question_agent_only",
        ),
    )


class ConversationSummary(Base):
    """The rolling fact sheet, one row per conversation.

    In the FIRST migration on purpose: feature 5 uses it immediately, and
    adding a table to a live database for a feature you already know you want
    is pure overhead.
    """

    __tablename__ = "conversation_summaries"

    conversation_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)

    # The whole reason the update can be incremental: it records the exact
    # message where the fact sheet stops, so a refresh folds in only the
    # exchanges between that point and the current window — never the whole
    # conversation. On a free tier that is the difference between a summary
    # prompt that grows forever and one that stays a fixed small size.
    #
    # No ondelete here: messages cascade from conversations, which cascades
    # this row too, so the FK never has to resolve a half-deleted state.
    covers_through_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("messages.id"), nullable=False
    )

    # Makes the refresh trigger a comparison instead of a query.
    exchange_count: Mapped[int] = mapped_column(Integer, nullable=False)

    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="summary")
