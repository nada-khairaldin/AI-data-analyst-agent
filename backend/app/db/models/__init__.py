"""Every model, imported so Base.metadata is complete.

Alembic's ``--autogenerate`` diffs ``Base.metadata`` against the database. A
model that is never imported is not in that metadata, so autogenerate will
cheerfully produce a migration that DROPS its table. Importing all nine here,
and importing this package from alembic/env.py, is what prevents that.

The relationship() calls use string names across modules, so they resolve only
once every class is registered — another reason this file imports all of them
rather than leaving it to whoever imports first.
"""

from app.db.base import Base
from app.db.models.conversation import (
    MESSAGE_ROLES,
    MESSAGE_STATUSES,
    RESULT_KINDS,
    Conversation,
    ConversationSummary,
    Message,
)
from app.db.models.dataset import (
    DATASET_STATUSES,
    MAX_DATASET_ROWS,
    Dataset,
    DatasetColumn,
    DatasetFile,
    PreprocessingReport,
)
from app.db.models.session import Session
from app.db.models.user import User

__all__ = [
    "Base",
    "Conversation",
    "ConversationSummary",
    "DATASET_STATUSES",
    "Dataset",
    "DatasetColumn",
    "DatasetFile",
    "MAX_DATASET_ROWS",
    "MESSAGE_ROLES",
    "MESSAGE_STATUSES",
    "Message",
    "PreprocessingReport",
    "RESULT_KINDS",
    "Session",
    "User",
]

# The nine tables the first migration must create. Asserted in the tests, so
# that a model added without a migration is caught by the suite rather than by
# a 500 in production.
EXPECTED_TABLES = frozenset(
    {
        "users",
        "sessions",
        "datasets",
        "dataset_columns",
        "dataset_files",
        "preprocessing_reports",
        "conversations",
        "messages",
        "conversation_summaries",
    }
)
