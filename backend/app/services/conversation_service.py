"""Conversations and messages: create, read, rename, search.

Writing a message also updates the conversation's denormalised counters in the
same transaction, so they can never drift from the rows they summarise.
"""

import json
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


# ---------------------------------------------------------------------------
# The condenser's window (PLAN §6.2)
# ---------------------------------------------------------------------------

DIGEST_ROWS = 5


def result_digest(message) -> str:
    """The first 5 rows plus the total count — never the full result_data.

    The most expensive mistake available here: one 500-row answer left in the
    window would be re-sent on every later turn, growing the cost of every
    future question forever. Five rows answers what a follow-up actually needs
    ("and the second one?") at a fixed size.
    """
    rows = message.result_data
    if rows is None:
        return "no result"
    if not isinstance(rows, list):
        return f"scalar result: {rows}"
    if not rows:
        return "0 rows"

    head = json.dumps(rows[:DIGEST_ROWS], separators=(",", ":"))
    if len(rows) > DIGEST_ROWS:
        return f"{head} (first {DIGEST_ROWS} of {len(rows)} rows)"
    return f"{head} ({len(rows)} rows)"


async def window_exchanges(db: AsyncSession, conversation_id, *, exchanges=3):
    """The last N complete user+agent pairs, oldest first.

    Counted in PAIRS, never messages: a window that opens on an agent reply
    whose question has been cut off is actively misleading — worse than no
    context at all.
    """
    statement = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(exchanges * 4)
    )
    rows = list((await db.execute(statement)).scalars())
    rows.reverse()

    pairs = []
    pending = None
    for message in rows:
        if message.role == "user":
            pending = message
        elif pending is not None:
            pairs.append((pending, message))
            pending = None

    return pairs[-exchanges:]


def render_window(pairs) -> str:
    """The window as text for the condenser prompt.

    Each agent turn carries its condensed_question, its plan as compact JSON
    and the result digest — the three things a follow-up refers back to.
    """
    if not pairs:
        return "none"

    lines = []
    for question, answer in pairs:
        lines.append(f"user: {question.content}")
        if answer.condensed_question:
            lines.append(f"  understood as: {answer.condensed_question}")
        if answer.status and answer.status != "ready":
            lines.append(f"  agent ({answer.status}): {answer.content}")
            continue
        if answer.analysis_plan:
            lines.append(
                f"  plan: {json.dumps(answer.analysis_plan, separators=(',', ':'))}"
            )
        lines.append(f"  result: {result_digest(answer)}")
        lines.append(f"  agent: {answer.content}")
    return "\n".join(lines)


async def last_agent_message(db: AsyncSession, conversation_id):
    """For the clarification pairing — see PLAN §6.4."""
    statement = (
        select(Message)
        .where(Message.conversation_id == conversation_id, Message.role == "agent")
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(1)
    )
    return (await db.execute(statement)).scalar_one_or_none()
