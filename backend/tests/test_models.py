"""Tests for the ORM models and the migration history (phase A6).

All offline: these read ``Base.metadata`` and the Alembic script directory, not
a database. The live checks were run by hand against Neon and are recorded in
the commit — upgrade head, the full schema verified in information_schema and
pg_indexes, autogenerate producing an EMPTY migration, and downgrade base
leaving nothing behind.

What these tests protect is the stuff that breaks silently later: a model added
without a migration, a cascade quietly changed to the wrong rule, a branched
revision history.
"""

import pytest
from sqlalchemy import CheckConstraint

from app.db.models import EXPECTED_TABLES, Base


# ---------------------------------------------------------------------------
# The table set
# ---------------------------------------------------------------------------


def test_metadata_contains_exactly_the_nine_expected_tables():
    """Catches a model added without a thought about its migration."""
    assert set(Base.metadata.tables) == set(EXPECTED_TABLES)


def test_every_table_has_a_primary_key():
    missing = [
        name
        for name, table in Base.metadata.tables.items()
        if not table.primary_key.columns
    ]

    assert not missing, f"tables without a primary key: {missing}"


@pytest.mark.parametrize(
    "table,column",
    [
        ("datasets", "created_at"),
        ("datasets", "updated_at"),
        ("messages", "created_at"),
        ("conversations", "created_at"),
        ("sessions", "created_at"),
    ],
)
def test_timestamps_are_timezone_aware(table, column):
    """A naive timestamp silently reinterprets itself if the server TZ moves."""
    col = Base.metadata.tables[table].columns[column]

    assert col.type.timezone is True, f"{table}.{column} is not timestamptz"


# ---------------------------------------------------------------------------
# Ownership and the upgrade path
# ---------------------------------------------------------------------------


def test_sessions_id_has_no_server_default():
    """The client supplies the session id, so the server must not invent one.

    If the database defaulted this, a request with a malformed X-Session-Id
    would quietly create an orphan session the browser can never address
    again.
    """
    col = Base.metadata.tables["sessions"].columns["id"]

    assert col.server_default is None
    assert col.default is None


def test_datasets_and_conversations_hang_off_sessions_not_users():
    """The whole upgrade path depends on this.

    Ownership lives on sessions, so signing up later is one UPDATE. A user_id
    on these tables would mean a nullable column with two meanings and a
    backfill over live rows.
    """
    for table in ("datasets", "conversations"):
        columns = set(Base.metadata.tables[table].columns.keys())
        assert "session_id" in columns
        assert "user_id" not in columns, f"{table} must not carry user_id"


def test_users_to_sessions_is_set_null_not_cascade():
    """Deleting an account must un-link data, never destroy it."""
    fks = list(Base.metadata.tables["sessions"].columns["user_id"].foreign_keys)

    assert len(fks) == 1
    assert fks[0].ondelete == "SET NULL"


@pytest.mark.parametrize(
    "table,column",
    [
        ("datasets", "session_id"),
        ("dataset_columns", "dataset_id"),
        ("dataset_files", "dataset_id"),
        ("preprocessing_reports", "dataset_id"),
        ("conversations", "dataset_id"),
        ("conversations", "session_id"),
        ("messages", "conversation_id"),
        ("conversation_summaries", "conversation_id"),
    ],
)
def test_every_child_cascades_on_delete(table, column):
    """"Delete dataset" must be one statement that cannot leave orphan rows.

    Note the limit of this guarantee: the cascade does NOT reach the object
    store. See test_dataframe_store and docs/PLAN.md §4.
    """
    fks = list(Base.metadata.tables[table].columns[column].foreign_keys)

    assert fks, f"{table}.{column} has no foreign key"
    assert fks[0].ondelete == "CASCADE", f"{table}.{column} does not cascade"


def test_covers_through_id_does_not_cascade():
    """Deliberately no ondelete: messages cascade from conversations, which
    cascades this row too, so the FK never resolves a half-deleted state."""
    fks = list(
        Base.metadata.tables["conversation_summaries"]
        .columns["covers_through_id"]
        .foreign_keys
    )

    assert len(fks) == 1
    assert fks[0].ondelete is None


# ---------------------------------------------------------------------------
# Constraints that encode a product rule
# ---------------------------------------------------------------------------


def constraint_names(table):
    return {
        c.name
        for c in Base.metadata.tables[table].constraints
        if isinstance(c, CheckConstraint)
    }


# Names are asserted in their RESOLVED form (ck_<table>_<name>), which also
# covers the naming convention in app/db/base.py. That convention is not
# cosmetic: without it Alembic generates names like ck_1a2b3c that differ
# between autogenerate runs, and a later migration cannot drop a constraint it
# cannot name.


def test_row_count_ceiling_is_enforced_by_the_database():
    """Mirrors MAX_DATASET_ROWS so a config mistake cannot bypass it."""
    assert "ck_datasets_row_count_within_limit" in constraint_names("datasets")


def test_dataset_status_is_constrained():
    assert "ck_datasets_status_valid" in constraint_names("datasets")


def test_message_role_is_constrained():
    assert "ck_messages_role_valid" in constraint_names("messages")


def test_condensed_question_is_agent_only():
    """It is meaningless on a user row, so the database refuses it there."""
    assert "ck_messages_condensed_question_agent_only" in constraint_names("messages")


def test_object_key_is_unique():
    """Makes a double-write to the same storage key detectable."""
    table = Base.metadata.tables["dataset_files"]
    uniques = [
        set(c.columns.keys())
        for c in table.constraints
        if c.__class__.__name__ == "UniqueConstraint"
    ]

    assert {"object_key"} in uniques


def test_dataset_files_stores_a_pointer_not_bytes():
    """The Q2 storage decision, asserted.

    If a `content` column ever reappears here, the bytea design has crept
    back in and dataframe_store.py is no longer the only door to storage.
    """
    columns = set(Base.metadata.tables["dataset_files"].columns.keys())

    assert "object_key" in columns
    assert "content" not in columns


def test_column_position_exists():
    """JSON key order must never drive table headers."""
    assert "position" in Base.metadata.tables["dataset_columns"].columns


def test_excluded_columns_can_explain_themselves():
    """Fixes the unavailable_columns={} bug: the agent needs the reason."""
    columns = set(Base.metadata.tables["dataset_columns"].columns.keys())

    assert "is_available" in columns
    assert "exclusion_reason" in columns


# ---------------------------------------------------------------------------
# Migration history
# ---------------------------------------------------------------------------


def alembic_scripts():
    from pathlib import Path

    from alembic.config import Config
    from alembic.script import ScriptDirectory

    backend = Path(__file__).resolve().parent.parent
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    return ScriptDirectory.from_config(config)


def test_there_is_exactly_one_migration_head():
    """A branched history makes `upgrade head` ambiguous and it refuses to run.

    Cheap to assert now, confusing to diagnose after two people have each
    added a migration on top of the same parent.
    """
    heads = alembic_scripts().get_heads()

    assert len(heads) == 1, f"expected one head, found {heads}"


def test_every_migration_has_an_upgrade_and_a_downgrade():
    """A migration you cannot reverse is a migration you cannot test."""
    for script in alembic_scripts().walk_revisions():
        source = script.path
        with open(source, encoding="utf-8") as handle:
            text = handle.read()
        assert "def upgrade()" in text, f"{script.revision} has no upgrade()"
        assert "def downgrade()" in text, f"{script.revision} has no downgrade()"


def test_the_initial_migration_creates_all_nine_tables():
    """Guards against a table being added to the models but not the migration.

    The real proof is `alembic upgrade head` followed by an empty
    autogenerate, which was run by hand. This is the cheap version that runs
    in CI without a database.
    """
    for script in alembic_scripts().walk_revisions():
        if script.down_revision is None:
            with open(script.path, encoding="utf-8") as handle:
                text = handle.read()
            for table in EXPECTED_TABLES:
                assert f"'{table}'" in text, f"{table} is not in the first migration"
            return

    pytest.fail("no initial migration found")
