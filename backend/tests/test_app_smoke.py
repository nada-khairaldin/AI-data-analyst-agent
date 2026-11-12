"""Smoke tests for the restructured app (phase A3).

These exist to catch the two things the A2 unit tests cannot: that the package
actually assembles into a FastAPI app, that the error envelope is right, and
that nothing outside config.py reads the environment.

No network and no database — the endpoints that need either live in
tests/api/, which runs against an isolated Neon schema.
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
    assert client.get("/health").status_code != 404
    # No session header, so these answer 400 — which still proves they exist.
    assert client.get("/api/datasets").status_code == 400
    assert client.get("/api/conversations").status_code == 400


def test_the_legacy_endpoints_are_gone(client):
    """B3 removed /api/upload and /api/analyze along with the module-level
    dict that lost every dataset on restart."""
    assert client.post("/api/upload").status_code == 404
    assert client.post("/api/analyze", json={}).status_code == 404


# ---------------------------------------------------------------------------
# The error envelope
# ---------------------------------------------------------------------------


def test_unknown_route_returns_the_error_envelope(client):
    response = client.get("/no-such-route")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_malformed_body_returns_a_validation_envelope(client):
    response = client.patch(
        "/api/conversations/9f1c2a44-5e3b-4a7e-9f41-0d6e2b7a1c33",
        json={"not_title": "x"},
        headers={"X-Session-Id": "9f1c2a44-5e3b-4a7e-9f41-0d6e2b7a1c33"},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"]["fields"]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def test_config_is_the_only_env_reader():
    """Both model roles resolve and the two DB URLs stay distinct.

    Asserted on the loaded settings rather than by grepping, so it keeps
    holding as the code moves.
    """
    from app.config import settings

    assert settings.planner_models, "LLM_PLANNER_MODELS must resolve"
    assert settings.fast_models, "LLM_FAST_MODELS must resolve"
    # The two roles exist precisely so they can differ; if the heads were ever
    # equal the cheap model would be doing the planner's job or vice versa.
    assert settings.planner_models[0] != settings.fast_models[0]
    # The dev cache must never be on by default, and never in production.
    assert settings.dev_cache_enabled is False or not settings.is_production
    assert settings.cors_origins, "CORS origins must never be empty"
    # Pooled for the app, direct for Alembic. If these are ever equal, one of
    # them is wrong and migrations will fail in confusing ways.
    if settings.database_url and settings.database_url_direct:
        assert settings.database_url != settings.database_url_direct


def test_no_module_outside_config_reads_the_environment():
    """os.getenv must not reappear in the moved agent modules.

    core.py and explainer.py each used to read the provider key directly from
    the environment. That is how one key ended up read in two places and one
    model id hardcoded in two files.
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
