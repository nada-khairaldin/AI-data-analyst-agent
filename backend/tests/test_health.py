"""Tests for /health (phase A5).

The probes are stubbed rather than called for real. A test suite that opens a
Neon connection is slow, fails on a plane, and — because Neon autosuspends —
would itself keep the compute awake and burn the free-tier quota it is
supposed to be protecting.

The live checks were run by hand and are recorded in the commit: 200 with
database/storage both "ok" against real Neon, and 503 with
"database": "unreachable" against a dead host, with no traceback in the body.
"""

import pytest
from fastapi.testclient import TestClient

from app.api.routers import health as health_module
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_caches():
    """Both probes cache for 30s, which would leak state between tests."""
    health_module._db_cache.update(checked_at=0.0, status=None)
    yield
    health_module._db_cache.update(checked_at=0.0, status=None)


def stub_probes(monkeypatch, database="ok", storage="ok", detail=None):
    async def fake_db(force=False):
        return database

    monkeypatch.setattr(health_module, "check_database", fake_db)
    monkeypatch.setattr(
        health_module, "check_storage", lambda force=False: (storage, detail)
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_everything_healthy_is_200(client, monkeypatch):
    stub_probes(monkeypatch)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "ok",
        "storage": "ok",
        "version": "0.1.0",
    }


# ---------------------------------------------------------------------------
# Failure paths — each dependency is reported separately
# ---------------------------------------------------------------------------


def test_unreachable_database_is_503(client, monkeypatch):
    stub_probes(monkeypatch, database="unreachable")

    response = client.get("/health")
    body = response.json()

    assert response.status_code == 503
    assert body["status"] == "degraded"
    assert body["database"] == "unreachable"
    # Storage is still reported as fine: the point of this endpoint is to say
    # WHICH dependency broke, not just that something did.
    assert body["storage"] == "ok"


def test_unreachable_storage_is_503(client, monkeypatch):
    stub_probes(monkeypatch, storage="unreachable", detail="HeadBucket failed: 404")

    response = client.get("/health")
    body = response.json()

    assert response.status_code == 503
    assert body["database"] == "ok"
    assert body["storage"] == "unreachable"
    assert body["storageDetail"] == "HeadBucket failed: 404"


def test_storage_detail_is_omitted_when_healthy(client, monkeypatch):
    stub_probes(monkeypatch)

    assert "storageDetail" not in client.get("/health").json()


def test_a_404_bucket_name_is_the_likeliest_storage_failure(client, monkeypatch):
    """Recorded because it already happened, and the symptom is unhelpful.

    The bucket on this project is "dataset", singular. Configured as
    "datasets", HeadBucket returns a bare 404 with nothing to suggest the name
    is wrong. Surfacing the botocore code in storageDetail is what makes that
    diagnosable from a deployed instance.
    """
    stub_probes(monkeypatch, storage="unreachable", detail="HeadBucket failed: 404")

    body = client.get("/health").json()

    assert "404" in body["storageDetail"]


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------


def test_the_database_probe_is_cached(monkeypatch, client):
    """An uptime monitor must not be able to keep the Neon compute awake."""
    calls = []

    async def counting_db(force=False):
        calls.append(force)
        return "ok"

    monkeypatch.setattr(health_module, "check_database", counting_db)
    monkeypatch.setattr(health_module, "check_storage", lambda force=False: ("ok", None))

    for _ in range(5):
        client.get("/health")

    # The endpoint always delegates; the caching lives inside the probe, so
    # what this asserts is that nothing asked for a forced check.
    assert calls == [False] * 5


def test_force_bypasses_the_cache(monkeypatch, client):
    calls = []

    async def counting_db(force=False):
        calls.append(force)
        return "ok"

    monkeypatch.setattr(health_module, "check_database", counting_db)
    monkeypatch.setattr(health_module, "check_storage", lambda force=False: ("ok", None))

    client.get("/health?force=true")

    assert calls == [True]


def test_real_db_probe_caches_its_result(monkeypatch):
    """Exercises the actual cache in check_database, not the stub."""
    import asyncio

    attempts = []

    class FakeConn:
        async def execute(self, *a, **k):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class FakeEngine:
        def connect(self):
            attempts.append(1)
            return FakeConn()

    monkeypatch.setattr(health_module, "engine", FakeEngine())
    health_module._db_cache.update(checked_at=0.0, status=None)

    async def run():
        first = await health_module.check_database()
        second = await health_module.check_database()
        return first, second

    first, second = asyncio.run(run())

    assert (first, second) == ("ok", "ok")
    assert len(attempts) == 1, "the second call should have been served from cache"
