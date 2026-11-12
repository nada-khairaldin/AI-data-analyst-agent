"""Dataset lifecycle: upload, read, delete.

The upload path is the only place in the app where all four layers meet — the
request, pandas, the object store and Postgres — so the ordering of the steps
is the interesting part and is explained where it is decided.
"""

import io
import logging
import uuid

import pandas as pd

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.errors import (
    DatasetLimitReached,
    DatasetRejected,
    FileTooLarge,
    NotFound,
    TooManyRows,
    UnsupportedFile,
)
from app.config import settings
from app.data.data_utils import get_schema
from app.data.validation import load_csv, prepare_dataframe
from app.db.models import (
    Conversation,
    Dataset,
    DatasetColumn,
    DatasetFile,
    PreprocessingReport,
)
from app.db.models import Session as SessionRow
from app.presenters import format_bytes, format_percent, quality_score
from app.services import dataframe_store

logger = logging.getLogger(__name__)

# The six checks the Preprocessing Report shows. Fixed in number and order so
# "6 checks completed" is a real count rather than the literal the JSX has
# today (API_CONTRACT.md endpoint 5).
CHECK_COUNT = 6


CALENDAR_SUFFIXES = ("_year", "_month")


def add_calendar_columns(frame):
    """For every datetime column add <col>_year (int) and <col>_month (YYYY-MM).

    "Show it per month" needs a column to group by: tools.py has no date
    truncation, so without these the planner can only group by the raw date
    and answer per DAY. Derived at upload so it works on any CSV.
    """
    for name in list(frame.columns):
        if not pd.api.types.is_datetime64_any_dtype(frame[name]):
            continue
        year = f"{name}_year"
        month = f"{name}_month"
        if year not in frame.columns:
            # Nullable Int64: .dt.year on NaT would otherwise force a float.
            frame[year] = frame[name].dt.year.astype("Int64")
        if month not in frame.columns:
            frame[month] = frame[name].dt.strftime("%Y-%m")
    return frame


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


async def create_dataset(
    db: AsyncSession,
    session_id: uuid.UUID,
    *,
    filename: str,
    content: bytes,
):
    """Validate, store and record one CSV.

    The order of checks is from API_CONTRACT.md endpoint 2 and is deliberate:
    the two cheap checks come first so an oversized or over-quota upload never
    reaches pandas, and the row count can only be known after parsing.

        1. body size        -> 413 FILE_TOO_LARGE
        2. datasets held    -> 409 DATASET_LIMIT_REACHED
        3. rows parsed      -> 413 TOO_MANY_ROWS
        4. quality          -> 422 DATASET_REJECTED

    The object is written to storage **before** the rows are committed. If the
    commit then fails, the result is an orphaned object — invisible but
    harmless — whereas committing first and failing to store would leave a row
    whose dataset cannot be read, which looks to the user like a dataset that
    exists but is permanently broken. The recoverable failure is the one worth
    choosing. Same argument as the delete ordering, in the other direction.
    """
    if not filename or not filename.lower().endswith(".csv"):
        raise UnsupportedFile(
            "Only .csv files are supported.",
            details={"filename": filename},
        )

    # 1. Size, before anything touches pandas.
    if len(content) > settings.max_upload_bytes:
        raise FileTooLarge(
            f"The file is larger than the {format_bytes(settings.max_upload_bytes)} "
            "limit.",
            details={
                "filename": filename,
                "fileSize": format_bytes(len(content)),
                "maxAllowed": format_bytes(settings.max_upload_bytes),
            },
        )

    if not content:
        raise DatasetRejected(
            "The file is empty.",
            details={"filename": filename, "reasons": ["The file is empty."]},
        )

    # 2. The per-session cap, counted from the table rather than from
    #    sessions.dataset_count: the counter is a denormalisation and this is
    #    the one place where being wrong would let a session exceed the cap.
    held = await db.scalar(
        select(func.count())
        .select_from(Dataset)
        .where(Dataset.session_id == session_id)
    )
    if held >= settings.max_datasets_per_session:
        raise DatasetLimitReached(
            f"You already have {held} datasets. Delete one before uploading "
            "another.",
            details={"current": held, "maximum": settings.max_datasets_per_session},
        )

    # Parse.
    frame, error = load_csv(io.BytesIO(content))
    if error:
        raise DatasetRejected(
            error,
            details={
                "filename": filename,
                "fileSize": format_bytes(len(content)),
                "reasons": [error],
            },
        )

    # 3. Rows, which can only be known now.
    if len(frame) > settings.max_dataset_rows:
        raise TooManyRows(
            f"The file has {len(frame):,} rows, more than the "
            f"{settings.max_dataset_rows:,} row limit.",
            details={
                "filename": filename,
                "rowCount": len(frame),
                "maxAllowed": settings.max_dataset_rows,
            },
        )

    # 4. Quality.
    prepared = prepare_dataframe(frame)
    if prepared["errors"]:
        # prepare_dataframe returns only the messages, so the numbers the
        # rejection screen renders as a bar are recomputed from the raw frame.
        # Cheap, and it keeps validation.py's return shape alone.
        missing = float(frame.isna().mean().mean()) if len(frame.columns) else 0.0
        raise DatasetRejected(
            "The dataset contains too many missing values to provide reliable "
            "analysis."
            if any("missing" in e for e in prepared["errors"])
            else prepared["errors"][0],
            details={
                "filename": filename,
                "fileSize": format_bytes(len(content)),
                # The UI's rejection screen renders these two as a bar, so
                # they are always present even when the rejection was for
                # duplicates rather than missingness.
                "missingRate": format_percent(missing),
                "maxAllowed": format_percent(0.40, decimals=0),
                "reasons": prepared["errors"],
            },
        )

    working = prepared["working_df"]
    excluded = prepared["unavailable_columns"]
    conversions = prepared["conversions"]

    # Before the schema is read, so the derived columns reach dataset_columns
    # and the planner.
    working = add_calendar_columns(working)

    # The working frame keeps EVERY column, including excluded ones. The old
    # endpoint dropped them, which is exactly why the agent was handed
    # `unavailable_columns={}` and could not explain why a column was
    # unusable. Availability is recorded per column instead, and the planner
    # reads it from dataset_columns (PLAN §4).
    dataset_id = uuid.uuid4()
    schema = get_schema(working)

    # Store the Parquet object first. See the docstring.
    object_key, byte_size = dataframe_store.save(dataset_id, working)

    missing_ratios = working.isna().mean()
    overall_missing = float(missing_ratios.mean())
    duplicate_ratio = float(working.duplicated().mean())
    score = quality_score(overall_missing)

    dataset = Dataset(
        id=dataset_id,
        session_id=session_id,
        name=filename,
        status="ready",
        row_count=len(working),
        column_count=len(working.columns),
        size_bytes=len(content),
        missing_rate=round(overall_missing, 5),
        duplicate_rate=round(duplicate_ratio, 5),
        quality_score=round(score, 5),
    )
    db.add(dataset)

    db.add(
        DatasetFile(
            dataset_id=dataset_id,
            object_key=object_key,
            format="parquet",
            byte_size=byte_size,
        )
    )

    for position, name in enumerate(working.columns):
        conversion = conversions.get(name, {})
        db.add(
            DatasetColumn(
                dataset_id=dataset_id,
                name=str(name),
                position=position,
                dtype=schema[name],
                original_dtype=conversion.get("original_type"),
                converted_to=conversion.get("converted_to"),
                conversion_success_rate=(
                    round(float(conversion["success_rate"]), 5)
                    if conversion.get("success_rate") is not None
                    else None
                ),
                missing_ratio=round(float(missing_ratios[name]), 5),
                is_available=name not in excluded,
                exclusion_reason=excluded.get(name),
            )
        )

    db.add(
        PreprocessingReport(
            dataset_id=dataset_id,
            overall_missing_ratio=round(overall_missing, 5),
            duplicate_ratio=round(duplicate_ratio, 5),
            checks_completed=CHECK_COUNT,
            notice_count=len(excluded) + (1 if conversions else 0),
            warnings=list(prepared["warnings"]),
            errors=[],
            checks=_build_checks(
                row_count=len(working),
                column_count=len(working.columns),
                overall_missing=overall_missing,
                duplicate_ratio=duplicate_ratio,
                excluded=excluded,
                conversions=conversions,
                schema=schema,
            ),
        )
    )

    # Keep the denormalised counter in the same transaction as the insert, so
    # it can never drift from the rows it summarises.
    await db.execute(
        SessionRow.__table__.update()
        .where(SessionRow.id == session_id)
        .values(dataset_count=held + 1)
    )

    await db.flush()
    return dataset


def _build_checks(
    *,
    row_count,
    column_count,
    overall_missing,
    duplicate_ratio,
    excluded,
    conversions,
    schema,
):
    """The ordered check list for the Preprocessing Report.

    Built once at upload and stored as jsonb, because it is computed from data
    that is then thrown away: recomputing it later would mean re-running
    prepare_dataframe() on a CSV that no longer exists (PLAN §4).

    All six entries are always present, including the two that are only
    interesting when something happened, so "6 checks completed" is honest and
    the report has a stable shape.
    """
    checks = [
        {
            "order": 1,
            "level": "success",
            "title": "File validation",
            "summary": "CSV file loaded successfully.",
        },
        {
            "order": 2,
            "level": "success",
            "title": "Dataset size",
            "summary": f"{row_count:,} rows • {column_count} columns",
        },
        {
            "order": 3,
            "level": "success",
            "title": "Missing values",
            "summary": (
                f"Overall missing rate: {format_percent(overall_missing)} "
                "(within threshold)."
            ),
        },
    ]

    if excluded:
        checks.append(
            {
                "order": 4,
                "level": "warning",
                "title": "Column excluded from analysis",
                "summary": (
                    "This column remains in the original dataset but will not "
                    "be used for analysis."
                ),
                "excludedColumns": [
                    {"name": name, "reason": format_percent_reason(reason)}
                    for name, reason in excluded.items()
                ],
            }
        )
    else:
        checks.append(
            {
                "order": 4,
                "level": "success",
                "title": "Column availability",
                "summary": "All columns are available for analysis.",
            }
        )

    if conversions:
        checks.append(
            {
                "order": 5,
                "level": "info",
                "title": "Data type conversion",
                "summary": None,
                "conversions": [
                    {
                        "name": name,
                        "from": detail.get("original_type"),
                        "to": schema.get(name, detail.get("converted_to")),
                        "successRate": _format_success(detail.get("success_rate")),
                    }
                    for name, detail in conversions.items()
                ],
            }
        )
    else:
        checks.append(
            {
                "order": 5,
                "level": "success",
                "title": "Data type conversion",
                "summary": "No type conversions were necessary.",
            }
        )

    level = "success" if duplicate_ratio <= 0.10 else "warning"
    qualifier = "below threshold" if duplicate_ratio <= 0.10 else "above threshold"
    checks.append(
        {
            "order": 6,
            "level": level,
            "title": "Duplicate rows",
            "summary": f"{format_percent(duplicate_ratio)} detected ({qualifier}).",
        }
    )

    return checks


def format_percent_reason(reason: str) -> str:
    """``"73.9% of values are missing."`` -> ``"73.9% missing"``.

    The report's excluded-column chip is short ("78.4% missing" in the JSX),
    while validation.py produces a sentence. Shortened here rather than
    changing validation.py, whose string is also shown elsewhere in full.
    """
    text = (reason or "").strip()
    if "%" in text:
        percent = text.split("%")[0].strip()
        return f"{percent}% missing"
    return text.rstrip(".")


def _format_success(ratio):
    from app.presenters import format_success_rate

    return format_success_rate(ratio)


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


async def list_datasets(db: AsyncSession, session_id: uuid.UUID):
    """This session's datasets, newest first, each with its conversations."""
    result = await db.execute(
        select(Dataset)
        .where(Dataset.session_id == session_id)
        .options(selectinload(Dataset.conversations))
        .order_by(Dataset.created_at.desc())
    )
    return list(result.scalars())


async def get_dataset(db: AsyncSession, session_id: uuid.UUID, dataset_id):
    """One dataset, scoped to the session.

    A dataset belonging to another session is reported as ``404``, not
    ``403``: with a bearer capability, distinguishing "exists but not yours"
    from "does not exist" would confirm the existence of other people's ids.
    """
    result = await db.execute(
        select(Dataset)
        .where(Dataset.id == dataset_id, Dataset.session_id == session_id)
        .options(selectinload(Dataset.conversations))
    )
    dataset = result.scalar_one_or_none()
    if dataset is None:
        raise NotFound("Dataset not found.")
    return dataset


async def get_columns(db: AsyncSession, session_id: uuid.UUID, dataset_id):
    await get_dataset(db, session_id, dataset_id)
    result = await db.execute(
        select(DatasetColumn)
        .where(DatasetColumn.dataset_id == dataset_id)
        .order_by(DatasetColumn.position)
    )
    return list(result.scalars())


async def get_report(db: AsyncSession, session_id: uuid.UUID, dataset_id):
    dataset = await get_dataset(db, session_id, dataset_id)
    result = await db.execute(
        select(PreprocessingReport).where(
            PreprocessingReport.dataset_id == dataset_id
        )
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise NotFound("Report not found for this dataset.")
    return dataset, report


async def load_frame(db: AsyncSession, session_id: uuid.UUID, dataset_id):
    """The stored DataFrame for a dataset, via the LRU cache.

    Callers must not mutate the result: it is the cached object, shared with
    every other caller for the same dataset (see dataframe_store).
    """
    await get_dataset(db, session_id, dataset_id)
    result = await db.execute(
        select(DatasetFile).where(DatasetFile.dataset_id == dataset_id)
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise NotFound("The stored file for this dataset is missing.")
    return dataframe_store.load(record.object_key)


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


async def delete_dataset(db: AsyncSession, session_id: uuid.UUID, dataset_id):
    """Remove a dataset, its object, and everything that cascades from it.

    **The object is deleted first, then the row** (PLAN §4). The Postgres
    cascade does not reach the bucket, so one of the two possible failures has
    to be chosen:

    - object gone, row left  -> ``load()`` raises ObjectMissing, the user can
      re-upload. Visible and recoverable.
    - row gone, object left  -> an object no row points at: invisible to the
      application and findable only by listing the bucket.

    This order produces the first. ``dataframe_store.delete`` returns False
    rather than raising for the same reason: the user asked for the dataset to
    be gone, and a failed object delete must not leave the row behind.
    """
    dataset = await get_dataset(db, session_id, dataset_id)

    result = await db.execute(
        select(DatasetFile).where(DatasetFile.dataset_id == dataset_id)
    )
    record = result.scalar_one_or_none()
    if record is not None:
        if not dataframe_store.delete(record.object_key):
            # Logged as a warning by dataframe_store, and deliberately not
            # surfaced: there is nothing the user can do, and the dataset is
            # genuinely gone from their view (API_CONTRACT.md endpoint 13).
            logger.warning(
                "Dataset %s deleted with an orphaned object %s",
                dataset_id,
                record.object_key,
            )

    await db.execute(sa_delete(Dataset).where(Dataset.id == dataset_id))

    held = await db.scalar(
        select(func.count())
        .select_from(Dataset)
        .where(Dataset.session_id == session_id)
    )
    await db.execute(
        SessionRow.__table__.update()
        .where(SessionRow.id == session_id)
        .values(dataset_count=held)
    )
    return dataset


async def count_conversations(db: AsyncSession, dataset_id) -> int:
    return await db.scalar(
        select(func.count())
        .select_from(Conversation)
        .where(Conversation.dataset_id == dataset_id)
    )
