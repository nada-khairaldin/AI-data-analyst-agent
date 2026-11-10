"""datasets and its three satellites.

All three satellites cascade from ``datasets``, so deleting a dataset is one
statement and cannot leave an orphan row — but note that the cascade does
**not** reach the object store, which is why ``dataset_service.delete()`` must
remove the Parquet object first (docs/PLAN.md §4).
"""

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at, updated_at, uuid_pk

DATASET_STATUSES = ("ready", "processing", "failed")

# Mirrors MAX_DATASET_ROWS in app/config.py. Duplicated into a CHECK on
# purpose: a config mistake must not be able to put an unservable dataset into
# the database, and the database is the one layer that cannot be bypassed.
MAX_DATASET_ROWS = 100_000


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = uuid_pk()
    session_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="ready")

    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Stored as numbers and formatted by presenters.py. Storing "2.1%" would
    # make these unsortable and useless for a threshold comparison.
    missing_rate: Mapped[float] = mapped_column(Numeric(6, 5), nullable=False)
    duplicate_rate: Mapped[float] = mapped_column(Numeric(6, 5), nullable=False)
    quality_score: Mapped[float] = mapped_column(Numeric(6, 5), nullable=False)

    created_at = created_at()
    updated_at = updated_at()

    session: Mapped["Session"] = relationship(  # noqa: F821
        back_populates="datasets"
    )
    columns: Mapped[list["DatasetColumn"]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="DatasetColumn.position",
    )
    file: Mapped["DatasetFile | None"] = relationship(
        back_populates="dataset", cascade="all, delete-orphan", uselist=False
    )
    report: Mapped["PreprocessingReport | None"] = relationship(
        back_populates="dataset", cascade="all, delete-orphan", uselist=False
    )
    conversations: Mapped[list["Conversation"]] = relationship(  # noqa: F821
        back_populates="dataset", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # The sidebar's only query: this session's datasets, newest first.
        Index(
            "ix_datasets_session_id_created_at",
            "session_id",
            text("created_at DESC"),
        ),
        CheckConstraint(
            "status in ('ready','processing','failed')", name="status_valid"
        ),
        CheckConstraint(
            f"row_count <= {MAX_DATASET_ROWS}", name="row_count_within_limit"
        ),
    )


class DatasetColumn(Base):
    """One row per CSV column — the agent's schema dict, as a table.

    ``is_available`` and ``exclusion_reason`` fix a real bug: today excluded
    columns are dropped and ``unavailable_columns={}`` is handed to the agent,
    so it cannot explain *why* a column is unusable. With these columns both
    the planner and the condenser get the real dict.
    """

    __tablename__ = "dataset_columns"

    id: Mapped[str] = uuid_pk()
    dataset_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String, nullable=False)
    # Exists so that JSON object key order never drives table headers.
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    dtype: Mapped[str] = mapped_column(String, nullable=False)
    original_dtype: Mapped[str | None] = mapped_column(String, nullable=True)
    converted_to: Mapped[str | None] = mapped_column(String, nullable=True)
    conversion_success_rate: Mapped[float | None] = mapped_column(
        Numeric(6, 5), nullable=True
    )

    missing_ratio: Mapped[float] = mapped_column(Numeric(6, 5), nullable=False)
    is_available: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    exclusion_reason: Mapped[str | None] = mapped_column(String, nullable=True)

    dataset: Mapped["Dataset"] = relationship(back_populates="columns")

    __table_args__ = (
        UniqueConstraint("dataset_id", "name"),
        Index("ix_dataset_columns_dataset_id_position", "dataset_id", "position"),
    )


class DatasetFile(Base):
    """A POINTER to the Parquet object, not the bytes.

    ``object_key`` is stored rather than recomputed from the dataset id, so
    changing the key naming scheme later does not orphan every existing
    object, and a stray object in the bucket can be matched back to its row.
    The unique constraint makes a double-write detectable.
    """

    __tablename__ = "dataset_files"

    dataset_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        primary_key=True,
    )
    object_key: Mapped[str] = mapped_column(String, nullable=False)
    format: Mapped[str] = mapped_column(String, nullable=False, server_default="parquet")
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at = created_at()

    dataset: Mapped["Dataset"] = relationship(back_populates="file")

    __table_args__ = (UniqueConstraint("object_key"),)


class PreprocessingReport(Base):
    """Computed once at upload, from data that is then thrown away.

    Recomputing it later would mean re-running prepare_dataframe() on a CSV
    that no longer exists — only the normalised Parquet is kept.
    """

    __tablename__ = "preprocessing_reports"

    id: Mapped[str] = uuid_pk()
    dataset_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Promoted to real columns because these two ARE queried: the rejection
    # threshold and the quality score both read them.
    overall_missing_ratio: Mapped[float] = mapped_column(Numeric(6, 5), nullable=False)
    duplicate_ratio: Mapped[float] = mapped_column(Numeric(6, 5), nullable=False)

    checks_completed: Mapped[int] = mapped_column(Integer, nullable=False)
    notice_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # jsonb because these are display-only: never queried, never joined.
    # Normalising six presentational rows would buy nothing.
    warnings: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    errors: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    checks: Mapped[list] = mapped_column(JSONB, nullable=False)

    created_at = created_at()

    dataset: Mapped["Dataset"] = relationship(back_populates="report")
