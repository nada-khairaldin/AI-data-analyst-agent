"""Conversations and messages: create, read, rename, search.

Writing a message also updates the conversation's denormalised counters in the
same transaction, so they can never drift from the rows they summarise.
"""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import NotFound
from app.db.models import Conversation, Dataset, Message
from app.presenters import DEFAULT_TITLE, title_from_question


async def create_conversation(
    db: AsyncSession, session_id: uuid.UUID, dataset_id, *, title=None
):
    """session_id is denormalised onto the row so ownership needs no join."""
    result = await db.execute(
        select(Dataset).where(
            Dataset.id == dataset_id, Dataset.session_id == session_id
        )
    )
    if result.scalar_one_or_none() is None:
        raise NotFound("Dataset not found.")

    conversation = Conversation(
        dataset_id=dataset_id,
        session_id=session_id,
        title=(title or "").strip() or DEFAULT_TITLE,
    )
    db.add(conversation)
    await db.flush()
    return conversation


async def get_conversation(db: AsyncSession, session_id: uuid.UUID, conversation_id):
    """Another session's conversation is a 404, not a 403: with a bearer
    capability, telling the two apart confirms other people's ids exist."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.session_id == session_id,
        )
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise NotFound("Conversation not found.")
    return conversation


async def list_conversations(
    db: AsyncSession, session_id: uuid.UUID, dataset_id, *, limit=None, offset=0
):
    statement = (
        select(Conversation)
        .where(
            Conversation.dataset_id == dataset_id,
            Conversation.session_id == session_id,
        )
        .order_by(Conversation.last_message_at.desc())
        .offset(offset)
    )
    if limit:
        statement = statement.limit(limit)
    result = await db.execute(statement)
    return list(result.scalars())


async def search_conversations(db: AsyncSession, session_id: uuid.UUID, query: str):
    """ILIKE on title and message content, per the contract. No FTS until this
    proves too slow — the search input is cosmetic today."""
    statement = (
        select(Conversation)
        .where(Conversation.session_id == session_id)
        .order_by(Conversation.last_message_at.desc())
    )

    text = (query or "").strip()
    if text:
        pattern = f"%{text}%"
        matching = select(Message.conversation_id).where(Message.content.ilike(pattern))
        statement = statement.where(
            or_(Conversation.title.ilike(pattern), Conversation.id.in_(matching))
        )

    result = await db.execute(statement)
    return list(result.scalars())


async def rename_conversation(
    db: AsyncSession, session_id: uuid.UUID, conversation_id, title: str
):
    conversation = await get_conversation(db, session_id, conversation_id)
    cleaned = (title or "").strip()
    if cleaned:
        conversation.title = cleaned[:200]
    await db.flush()
    return conversation


async def list_messages(
    db: AsyncSession, session_id: uuid.UUID, conversation_id, *, limit=None
):
    conversation = await get_conversation(db, session_id, conversation_id)
    statement = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at, Message.id)
    )
    if limit:
        statement = statement.limit(limit)
    result = await db.execute(statement)
    return conversation, list(result.scalars())


async def add_message(
    db: AsyncSession,
    conversation: Conversation,
    *,
    role: str,
    content: str,
    status=None,
    condensed_question=None,
    analysis_plan=None,
    chart_plan=None,
    result_data=None,
    result_kind=None,
    plan_display=None,
    latency_ms=None,
):
    """Persist one message and move the conversation's counters with it.

    exchange_count counts COMPLETED user+agent pairs, so it advances on the
    agent row only — never on half a pair (PLAN §6).
    """
    message = Message(
        conversation_id=conversation.id,
        role=role,
        status=status,
        content=content or "",
        condensed_question=condensed_question if role == "agent" else None,
        analysis_plan=analysis_plan,
        chart_plan=chart_plan,
        result_data=result_data,
        result_kind=result_kind,
        plan_display=plan_display,
        latency_ms=latency_ms,
    )
    db.add(message)

    conversation.message_count = (conversation.message_count or 0) + 1
    conversation.last_message_at = func.now()
    if role == "agent":
        conversation.exchange_count = (conversation.exchange_count or 0) + 1

    await db.flush()
    return message


async def is_first_question(db: AsyncSession, conversation_id) -> bool:
    """True when no user message exists yet — used to auto-title and to skip
    condensation (nothing to resolve on a first turn)."""
    count = await db.scalar(
        select(func.count())
        .select_from(Message)
        .where(Message.conversation_id == conversation_id, Message.role == "user")
    )
    return (count or 0) == 0


async def autotitle(db: AsyncSession, conversation: Conversation, question: str):
    """Rename from the first question, matching the mock's substring(0,25)."""
    if conversation.title == DEFAULT_TITLE:
        conversation.title = title_from_question(question)
        await db.flush()
    return conversation
