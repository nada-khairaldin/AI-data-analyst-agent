"""The rolling fact sheet (PLAN §6.3).

A fact sheet, not a narrative: what a later question needs is "revenue =
price x quantity", "only 2024", "Laptop = 1,248" — not the shape of the
conversation. Fixed headings also make a regression visible; a paragraph that
drifts is a bug you cannot see.

Refreshed only when 2 exchanges have left the window, which amortises the call
to ~0.5 per turn. Every failure keeps the old summary and never blocks the
chat.
"""

import logging
import pathlib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm import FAST, complete
from app.config import settings
from app.db.models import ConversationSummary, Message
from app.services.conversation_service import result_digest

logger = logging.getLogger(__name__)

PROMPT_PATH = (
    pathlib.Path(__file__).resolve().parent.parent / "prompts" / "summarizer.txt"
)

HEADINGS = (
    "Goal:",
    "Definitions & agreements:",
    "Active filters/assumptions:",
    "Key findings:",
)
MAX_WORDS = 150


def build_prompt(existing_summary, new_exchanges) -> str:
    return (
        PROMPT_PATH.read_text(encoding="utf-8")
        .replace("{existing_summary}", (existing_summary or "").strip() or "(empty)")
        .replace("{new_exchanges}", new_exchanges or "none")
    )


def is_usable(text) -> bool:
    """Reject a reply that lost the headings.

    The headings are the contract: without them the "Active filters" line
    cannot be found, and keeping the previous sheet is strictly better than
    storing prose that later turns will misread.
    """
    if not text or not text.strip():
        return False
    return all(heading.lower() in text.lower() for heading in HEADINGS)


def trim(text) -> str:
    words = text.split()
    if len(words) <= MAX_WORDS * 2:
        return text.strip()
    # Generous ceiling: the prompt asks for 150 words and this only stops a
    # runaway reply from being stored.
    return " ".join(words[: MAX_WORDS * 2]).strip()


def render_exchanges(pairs) -> str:
    """The exchanges to fold in, in the same shape the condenser sees."""
    lines = []
    for question, answer in pairs:
        lines.append(f"user: {question.content}")
        if answer.condensed_question:
            lines.append(f"  understood as: {answer.condensed_question}")
        if answer.status and answer.status != "ready":
            lines.append(f"  agent ({answer.status}): {answer.content}")
            continue
        lines.append(f"  result: {result_digest(answer)}")
        lines.append(f"  agent: {answer.content}")
    return "\n".join(lines) or "none"


async def load_summary(db: AsyncSession, conversation_id):
    result = await db.execute(
        select(ConversationSummary).where(
            ConversationSummary.conversation_id == conversation_id
        )
    )
    return result.scalar_one_or_none()


async def fact_sheet(db: AsyncSession, conversation_id) -> str:
    row = await load_summary(db, conversation_id)
    return row.summary if row else ""


def is_due(conversation, summary) -> bool:
    """True when 2 exchanges have left the window since the last refresh.

    A comparison rather than a query, which is what `exchange_count` on both
    rows is for:

        exchanges - window - already_summarised >= 2
    """
    total = conversation.exchange_count or 0
    window = settings.history_window_exchanges
    covered = summary.exchange_count if summary else 0
    return (total - window - covered) >= settings.summary_refresh_exchanges


async def refresh(db: AsyncSession, conversation, pairs, covers_through_id):
    """Fold `pairs` into the fact sheet. Returns the new text, or None.

    Never raises: a summariser failure must leave the previous sheet in place
    and must not affect a turn that has already been answered.
    """
    summary = await load_summary(db, conversation.id)
    existing = summary.summary if summary else ""

    try:
        raw = complete(build_prompt(existing, render_exchanges(pairs)), role=FAST)
    except Exception as error:
        logger.warning("Summariser call failed, keeping the old fact sheet: %s", error)
        return None

    if not is_usable(raw):
        logger.warning("Summariser reply lost its headings, keeping the old fact sheet")
        return None

    text = trim(raw)
    covered = (conversation.exchange_count or 0) - settings.history_window_exchanges

    if summary is None:
        db.add(
            ConversationSummary(
                conversation_id=conversation.id,
                summary=text,
                covers_through_id=covers_through_id,
                exchange_count=max(0, covered),
            )
        )
    else:
        summary.summary = text
        summary.covers_through_id = covers_through_id
        summary.exchange_count = max(0, covered)

    await db.flush()
    return text


async def exchanges_outside_window(db: AsyncSession, conversation_id, *, covered):
    """The pairs that have left the window but are not yet in the fact sheet.

    This is what `covers_through_id` makes possible: a refresh folds in only
    the new exchanges, so the summariser prompt stays a fixed small size
    instead of growing with the conversation.
    """
    statement = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at, Message.id)
    )
    rows = list((await db.execute(statement)).scalars())

    pairs = []
    pending = None
    for message in rows:
        if message.role == "user":
            pending = message
        elif pending is not None:
            pairs.append((pending, message))
            pending = None

    window = settings.history_window_exchanges
    outside = pairs[: max(0, len(pairs) - window)]
    return outside[covered:]
