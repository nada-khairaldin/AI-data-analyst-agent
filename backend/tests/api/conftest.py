"""Fixtures for the API tests.

**Isolation.** The task asked for a Neon *branch*. There is no Neon API key or
CLI in this environment, so one cannot be created from here. Each test session
instead gets its own Postgres **schema** on the same database, with every
table redirected into it by ``schema_translate_map``. The ``public`` data is
never read or written. Deviation recorded in PLAN §9.

**One loop, one connection.** Opening a connection to this Neon compute was
measured at 4-65 seconds, while a statement on an already-open one is ~0.35s.
So the engine is session-scoped with a pool of exactly one, and everything —
setup, truncation, requests — runs on one session-scoped event loop, because
asyncpg connections are bound to the loop that created them. That is also why
these tests use ``httpx.AsyncClient`` rather than ``TestClient``: TestClient
runs the app on its own private loop, which the fixtures cannot share.

**Storage** is an in-memory dict; writing to the real bucket per test would
cost requests and, since Neon's delete is a soft delete, leave rubbish behind.
**The LLM** is never called.
"""

import io
import uuid

import pandas as pd
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import MetaData, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.db.models import Base
from app.db.url import connect_args_for, normalize_async_url

SCHEMA = f"test_{uuid.uuid4().hex[:12]}"


def _ddl_statements(schema):
    """Every CREATE for the schema, qualified, as plain SQL strings."""
    from sqlalchemy.schema import CreateIndex, CreateTable

    dialect = postgresql.dialect()

    # One shared target MetaData: copying tables into separate ones leaves
    # every foreign key unresolvable.
    target = MetaData(schema=schema)
    scoped = [table.to_metadata(target) for table in Base.metadata.sorted_tables]

    statements = []
    for table in scoped:
        statements.append(str(CreateTable(table).compile(dialect=dialect)).strip())
        for index in table.indexes:
            statements.append(str(CreateIndex(index).compile(dialect=dialect)).strip())
    return statements


# asyncpg's default connect timeout is 60s. Connects to this compute measured
# between 6.7s and 65s, and at the top of that range the handshake fails with
# "Authentication timed out" — which then fails every test in the session,
# since they all share the one connection.
CONNECT_TIMEOUT_SECONDS = 180
SETUP_ATTEMPTS = 3


def _test_connect_args():
    args = dict(connect_args_for(settings.database_url))
    args["timeout"] = CONNECT_TIMEOUT_SECONDS
    return args


@pytest.fixture(scope="session")
async def engine():
    """One engine, one connection, for the whole session."""
    instance = create_async_engine(
        normalize_async_url(settings.database_url),
        connect_args=_test_connect_args(),
        pool_size=1,
        max_overflow=0,
        # One extra round trip per checkout, but this Neon compute drops idle
        # connections ("connection was closed in the middle of operation") and
        # with a pool of one that kills the rest of the session.
        pool_pre_ping=True,
        pool_recycle=300,
    ).execution_options(schema_translate_map={None: SCHEMA})

    # All DDL in ONE round trip, and straight to the asyncpg connection:
    # SQLAlchemy sends statements as prepared statements, and asyncpg refuses
    # a multi-statement script there. Its own execute() uses the simple-query
    # protocol, which allows a script. create_all would issue ~30 separate
    # statements, which measured 61s of pure latency.
    script = ";\n".join(_ddl_statements(SCHEMA))
    last = None
    for _ in range(SETUP_ATTEMPTS):
        try:
            async with instance.begin() as conn:
                await conn.execute(text(f'create schema if not exists "{SCHEMA}"'))
                raw = await conn.get_raw_connection()
                await raw.driver_connection.execute(script)
            last = None
            break
        except Exception as error:  # noqa: BLE001 - reported below
            last = error
            await instance.dispose()

    if last is not None:
        # Skipped rather than failed: an unreachable database says nothing
        # about the code under test, and these are the only tests that need
        # one. The reason is printed so it is never mistaken for a pass.
        pytest.skip(
            "Neon is not reachable, so the API tests cannot run: "
            f"{type(last).__name__}: {last}",
            allow_module_level=True,
        )

    yield instance

    async with instance.begin() as conn:
        await conn.execute(text(f'drop schema if exists "{SCHEMA}" cascade'))
    await instance.dispose()


@pytest.fixture(autouse=True)
async def clean_tables(engine):
    """Truncate between tests so each starts empty.

    TRUNCATE CASCADE from the two roots rather than dropping and recreating:
    one statement, and the cascade follows the same foreign keys the app does.
    """
    async with engine.begin() as conn:
        await conn.execute(
            text(f'truncate table "{SCHEMA}".sessions, "{SCHEMA}".users cascade')
        )
    yield


@pytest.fixture
def fake_store(monkeypatch):
    """The object store as a dict. Returned so tests can assert on it."""
    from app.services import dataframe_store

    objects = {}

    def save(dataset_id, frame):
        key = dataframe_store.object_key_for(dataset_id)
        buffer = io.BytesIO()
        frame.to_parquet(buffer, engine="pyarrow", index=False)
        objects[key] = buffer.getvalue()
        return key, len(objects[key])

    def load(key):
        if key not in objects:
            raise dataframe_store.ObjectMissing(f"missing {key}; re-upload")
        return pd.read_parquet(io.BytesIO(objects[key]), engine="pyarrow")

    def delete(key):
        objects.pop(key, None)
        return True

    monkeypatch.setattr(dataframe_store, "save", save)
    monkeypatch.setattr(dataframe_store, "load", load)
    monkeypatch.setattr(dataframe_store, "delete", delete)
    monkeypatch.setattr(dataframe_store, "exists", lambda key: key in objects)
    monkeypatch.setattr(
        dataframe_store, "check_storage", lambda force=False: ("ok", None)
    )
    return objects


@pytest.fixture
async def client(engine, fake_store):
    """An httpx client over the ASGI app, using the test schema."""
    from app.db.session import get_db
    from app.main import app

    factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)

    async def override_get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as instance:
        yield instance
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def db_factory(engine):
    """A session factory for tests that drive a service directly."""
    return async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


@pytest.fixture
def session_id():
    return str(uuid.uuid4())


@pytest.fixture
def headers(session_id):
    return {"X-Session-Id": session_id}


@pytest.fixture
def samples():
    import pathlib

    return pathlib.Path(__file__).resolve().parents[3] / "samples"


@pytest.fixture
def upload(client, headers, samples):
    """Upload a sample; returns the raw response."""

    async def do(name="orders.csv", request_headers=None):
        content = (samples / name).read_bytes()
        return await client.post(
            "/api/datasets",
            files={"file": (name, content, "text/csv")},
            headers=request_headers or headers,
        )

    return do
