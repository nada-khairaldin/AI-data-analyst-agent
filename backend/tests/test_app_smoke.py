"""Smoke tests for the restructured app (phase A3).

These exist to catch the two things the A2 unit tests cannot: that the package
actually assembles into a FastAPI app, and that the legacy endpoints still
behave exactly as they did before the move.

No network and no database: /api/upload is in-memory, and /api/analyze is only
exercised on paths that return before any LLM call.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# The app assembles
# ---------------------------------------------------------------------------


def test_root_responds(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "Data Analysis Agent" in response.json()["message"]


def test_health_reports_its_dependencies(client):
    """Shape only. The status depends on whether Neon is reachable right now.

    Asserting "ok" here would make the suite fail offline for a reason that
    has nothing to do with the code. tests/test_health.py stubs the probes and
    asserts both outcomes properly.
    """
    response = client.get("/health")
    body = response.json()

    assert response.status_code in (200, 503)
    assert body["status"] in ("ok", "degraded")
    assert body["database"] in ("ok", "unreachable")
    assert body["storage"] in ("ok", "unreachable")
    assert body["version"]


def test_routers_are_registered(client):
    """Guards against a silently un-included router.

    Note: FastAPI 0.142 wraps included routers in an internal object rather
    than flattening them into app.routes, so inspecting app.routes is NOT a
    valid check. Issuing a request is.
    """
    for path in ("/health", "/api/upload", "/api/analyze"):
        response = client.request("POST" if path.startswith("/api") else "GET", path)
        assert response.status_code != 404, f"{path} is not registered"


# ---------------------------------------------------------------------------
# The error envelope
# ---------------------------------------------------------------------------


def test_unknown_route_returns_the_error_envelope(client):
    response = client.get("/no-such-route")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_malformed_body_returns_a_validation_envelope(client):
    response = client.post("/api/analyze", json={"query": "no session_id"})

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"]["fields"]


# ---------------------------------------------------------------------------
# Legacy behaviour is preserved
# ---------------------------------------------------------------------------


def test_legacy_upload_still_works(client):
    csv = b"Product,Quantity\nLaptop,10\nMouse,5\n"

    response = client.post(
        "/api/upload", files={"file": ("orders.csv", csv, "text/csv")}
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "success"
    assert body["row_count"] == 2
    assert body["column_count"] == 2
    assert body["session_id"]
    assert body["schema"] == {"Product": "str", "Quantity": "int64"}


def test_legacy_upload_rejects_a_low_quality_dataset(client):
    # Every column 50% missing -> above the 40% dataset limit.
    csv = b"A,B,C\n1,1,1\n,,\n3,3,3\n,,\n"

    response = client.post(
        "/api/upload", files={"file": ("bad.csv", csv, "text/csv")}
    )
    body = response.json()

    # Still HTTP 200 with status:error — the legacy shape, frozen on purpose.
    # docs/API_CONTRACT.md moves this to 422; that is phase B.
    assert response.status_code == 200
    assert body["status"] == "error"
    assert body["details"]


def test_legacy_analyze_rejects_an_unknown_session(client):
    response = client.post(
        "/api/analyze", json={"session_id": "not-a-real-session", "query": "hi"}
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "error"
    assert "Session not found" in body["message"]


def test_legacy_analyze_rejects_a_blank_question(client):
    """Returns before any LLM call, so this is safe to run offline."""
    csv = b"Product,Quantity\nLaptop,10\nMouse,5\n"
    upload = client.post(
        "/api/upload", files={"file": ("orders.csv", csv, "text/csv")}
    ).json()

    response = client.post(
        "/api/analyze", json={"session_id": upload["session_id"], "query": "   "}
    )
    body = response.json()

    assert body["status"] == "error"
    assert body["message"] == "Please enter a question."


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def test_config_is_the_only_env_reader():
    """The hardcoded model ids are gone and the two DB URLs stay distinct.

    Asserted on the loaded settings rather than by grepping, so it keeps
    holding as the code moves.
    """
    from app.config import settings

    assert settings.llm_model, "LLM_MODEL must always resolve to something"
    assert settings.llm_base_url.startswith("http")
    assert settings.cors_origins, "CORS origins must never be empty"
    # Pooled for the app, direct for Alembic. If these are ever equal, one of
    # them is wrong and migrations will fail in confusing ways.
    if settings.database_url and settings.database_url_direct:
        assert settings.database_url != settings.database_url_direct


def test_no_module_outside_config_reads_the_environment():
    """os.getenv must not reappear in the moved agent modules.

    core.py and explainer.py each used to read HUGGINGFACE_API_KEY directly.
    That is how one key ended up read in two places and one model id hardcoded
    in two files.
    """
    import pathlib

    app_dir = pathlib.Path(__file__).resolve().parent.parent / "app"
    offenders = []

    for path in app_dir.rglob("*.py"):
        if path.name == "config.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "os.getenv" in text or "os.environ" in text:
            offenders.append(path.name)

    assert not offenders, f"these modules read the environment directly: {offenders}"
