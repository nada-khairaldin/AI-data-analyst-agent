"""Conversation endpoints: API_CONTRACT.md 10, 12, 14. Endpoint 11 is B2."""

import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_or_create_session, get_session_id
from app.api.serializers import (
    conversation_summary,
    message_detail,
    search_result,
)
from app.api.errors import ApiError
from app.api.sse import SSE_HEADERS, stream_events
from app.config import settings
from app.db.models import Dataset
from app.db.session import get_db
from app.services import analysis_service, conversation_service, dataset_service

router = APIRouter(prefix="/api", tags=["conversations"])


class ConversationRename(BaseModel):
    title: str


class MessageCreate(BaseModel):
    content: str


@router.get("/conversations")
async def search_conversations(
    q: str = Query(default=""),
    session_id: uuid.UUID = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
):
    """Endpoint 14. Declared before /conversations/{id} so the literal path
    wins — FastAPI matches in declaration order."""
    conversations = await conversation_service.search_conversations(db, session_id, q)

    names = {}
    if conversations:
        rows = await db.execute(
            select(Dataset.id, Dataset.name).where(
                Dataset.id.in_({c.dataset_id for c in conversations})
            )
        )
        names = {row.id: row.name for row in rows}

    return {
        "conversations": [
            search_result(c, names.get(c.dataset_id)) for c in conversations
        ]
    }


@router.get("/conversations/{conversation_id}/messages")
async def list_messages(
    conversation_id: uuid.UUID,
    limit: int | None = Query(default=None, ge=1, le=500),
    session_id: uuid.UUID = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
):
    """Endpoint 10. The only endpoint returning full message objects."""
    conversation, messages = await conversation_service.list_messages(
        db, session_id, conversation_id, limit=limit
    )
    return {
        "conversationId": str(conversation.id),
        "title": conversation.title,
        "datasetId": str(conversation.dataset_id),
        "messages": [message_detail(m) for m in messages],
    }


@router.patch("/conversations/{conversation_id}")
async def rename_conversation(
    conversation_id: uuid.UUID,
    body: ConversationRename,
    session_id: uuid.UUID = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
):
    """Endpoint 12."""
    conversation = await conversation_service.rename_conversation(
        db, session_id, conversation_id, body.title
    )
    await db.commit()
    await db.refresh(conversation)
    return conversation_summary(conversation)


@router.post("/conversations/{conversation_id}/messages", status_code=201)
async def send_message(
    conversation_id: uuid.UUID,
    body: MessageCreate,
    session_id: uuid.UUID = Depends(get_or_create_session),
    db: AsyncSession = Depends(get_db),
):
    """Endpoint 11, the non-streaming chat endpoint.

    Drains the SAME generator the SSE endpoint will forward, discarding every
    intermediate event and returning only the final message, so the two can
    never drift apart.
    """
    question = (body.content or "").strip()
    if not question:
        raise ApiError(
            "A question is required.", code="VALIDATION_ERROR", status_code=400
        )

    generator = await _turn_generator(db, session_id, conversation_id, question)

    done = None
    failure = None
    async for item in generator:
        if item["event"] == "done":
            done = item["data"]
        elif item["event"] == "error":
            failure = item["data"]

    if done is None:
        # The agent message with status "failed" is already persisted by the
        # generator, so the invariant holds even though this returns an error.
        raise ApiError(
            (failure or {}).get("message", "The turn could not be completed."),
            code=(failure or {}).get("code", "INTERNAL_ERROR"),
            status_code=502,
        )

    return done


async def _turn_generator(db, session_id, conversation_id, question):
    """Shared setup for both chat endpoints, so neither can drift."""
    conversation = await conversation_service.get_conversation(
        db, session_id, conversation_id
    )
    dataset = await dataset_service.get_dataset(
        db, session_id, conversation.dataset_id
    )
    columns = await dataset_service.get_columns(db, session_id, dataset.id)
    frame = await dataset_service.load_frame(db, session_id, dataset.id)

    return analysis_service.run_turn(
        db, conversation, dataset, frame, columns, question, history=[]
    )


@router.post("/conversations/{conversation_id}/messages/stream")
async def stream_message(
    conversation_id: uuid.UUID,
    body: MessageCreate,
    session_id: uuid.UUID = Depends(get_or_create_session),
    db: AsyncSession = Depends(get_db),
):
    """Endpoint 11b — the same work as endpoint 11, delivered as it happens.

    Both endpoints drain the SAME generator, so they cannot answer
    differently. The 4xx checks run BEFORE the response starts: once the
    status line is sent, an error can only be an `error` event, which is far
    less useful to a client than a real status code.
    """
    question = (body.content or "").strip()
    if not question:
        raise ApiError(
            "A question is required.", code="VALIDATION_ERROR", status_code=400
        )

    generator = await _turn_generator(db, session_id, conversation_id, question)

    return StreamingResponse(
        stream_events(generator, heartbeat=settings.sse_heartbeat_seconds),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
