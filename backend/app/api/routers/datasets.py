"""Dataset endpoints: API_CONTRACT.md 2-9 and 13."""

import uuid

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_or_create_session, get_session_id
from app.api.serializers import (
    column_detail,
    conversation_summary,
    dataset_detail,
    report_detail,
)
from app.config import settings
from app.presenters import format_bytes, to_jsonable
from app.db.session import get_db
from app.services import conversation_service, dataset_service

router = APIRouter(prefix="/api", tags=["datasets"])


class ConversationCreate(BaseModel):
    title: str | None = None


@router.post("/datasets", status_code=201)
async def upload_dataset(
    file: UploadFile = File(...),
    session_id: uuid.UUID = Depends(get_or_create_session),
    db: AsyncSession = Depends(get_db),
):
    """Endpoint 2. 413 / 409 / 413 / 422 in that order; see the service."""
    content = await file.read()
    dataset = await dataset_service.create_dataset(
        db, session_id, filename=file.filename or "", content=content
    )
    await db.commit()
    await db.refresh(dataset, attribute_names=["conversations"])
    return dataset_detail(dataset)


@router.get("/datasets")
async def list_datasets(
    session_id: uuid.UUID = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
):
    """Endpoint 3. A read never creates a session row."""
    datasets = await dataset_service.list_datasets(db, session_id)
    return {"datasets": [dataset_detail(d) for d in datasets]}


@router.get("/datasets/{dataset_id}")
async def get_dataset(
    dataset_id: uuid.UUID,
    session_id: uuid.UUID = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
):
    """Endpoint 4."""
    dataset = await dataset_service.get_dataset(db, session_id, dataset_id)
    return dataset_detail(dataset)


@router.get("/datasets/{dataset_id}/report")
async def get_report(
    dataset_id: uuid.UUID,
    session_id: uuid.UUID = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
):
    """Endpoint 5."""
    dataset, report = await dataset_service.get_report(db, session_id, dataset_id)
    return report_detail(dataset, report)


@router.get("/datasets/{dataset_id}/columns")
async def get_columns(
    dataset_id: uuid.UUID,
    session_id: uuid.UUID = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
):
    """Endpoint 6."""
    columns = await dataset_service.get_columns(db, session_id, dataset_id)
    return {
        "datasetId": str(dataset_id),
        "columns": [column_detail(c) for c in columns],
    }


@router.get("/datasets/{dataset_id}/preview")
async def get_preview(
    dataset_id: uuid.UUID,
    limit: int = Query(default=5, ge=1, le=100),
    session_id: uuid.UUID = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
):
    """Endpoint 7. columns is sent separately and ordered: JSON key order must
    not drive table headers. NaN/NaT serialise as null."""
    frame = await dataset_service.load_frame(db, session_id, dataset_id)
    head = frame.head(limit)

    rows = []
    for record in head.to_dict(orient="records"):
        row = {}
        for key, value in record.items():
            row[str(key)] = to_jsonable(value)
        rows.append(row)

    return {
        "datasetId": str(dataset_id),
        "columns": [str(c) for c in frame.columns],
        "rows": rows,
        "totalRows": int(len(frame)),
    }


@router.get("/datasets/{dataset_id}/conversations")
async def list_dataset_conversations(
    dataset_id: uuid.UUID,
    limit: int | None = Query(default=None, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session_id: uuid.UUID = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
):
    """Endpoint 8."""
    await dataset_service.get_dataset(db, session_id, dataset_id)
    conversations = await conversation_service.list_conversations(
        db, session_id, dataset_id, limit=limit, offset=offset
    )
    return {"conversations": [conversation_summary(c) for c in conversations]}


@router.post("/datasets/{dataset_id}/conversations", status_code=201)
async def create_conversation(
    dataset_id: uuid.UUID,
    body: ConversationCreate | None = None,
    session_id: uuid.UUID = Depends(get_or_create_session),
    db: AsyncSession = Depends(get_db),
):
    """Endpoint 9. Returns messages:[] so the object drops into UI state as-is."""
    conversation = await conversation_service.create_conversation(
        db, session_id, dataset_id, title=(body.title if body else None)
    )
    await db.commit()
    await db.refresh(conversation)
    payload = conversation_summary(conversation)
    payload["messages"] = []
    return payload


@router.delete("/datasets/{dataset_id}", status_code=204)
async def delete_dataset(
    dataset_id: uuid.UUID,
    session_id: uuid.UUID = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
):
    """Endpoint 13. Object first, then the row — see the service."""
    await dataset_service.delete_dataset(db, session_id, dataset_id)
    await db.commit()
    return Response(status_code=204)


@router.get("/limits")
async def get_limits():
    """Not in the contract. The frontend hardcodes "5 MB" today; serving the
    real numbers stops the two drifting apart."""
    return {
        "maxUploadBytes": settings.max_upload_bytes,
        "maxUploadSize": format_bytes(settings.max_upload_bytes),
        "maxDatasetRows": settings.max_dataset_rows,
        "maxDatasetsPerSession": settings.max_datasets_per_session,
    }
