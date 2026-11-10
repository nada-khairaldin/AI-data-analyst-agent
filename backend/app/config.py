"""Application settings — the ONLY module in the codebase that reads the
environment.

Everything else imports ``settings`` from here. That rule is what makes the
app testable (override one object instead of patching os.environ) and what
stops a second hardcoded model id from appearing somewhere nobody looks.

Values come from ``backend/.env``, resolved relative to this file rather than
to the working directory, so the app behaves the same whether it is started
from ``backend/`` by uvicorn, from the repo root by an IDE, or by pytest.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> backend/
BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        # The .env carries names this app does not know about (and Neon adds
        # more over time); ignoring them is friendlier than refusing to boot.
        extra="ignore",
    )

    # ---- Database --------------------------------------------------------
    # Pooled URL. Used by the running application only.
    database_url: str = ""

    # Direct URL. Used by Alembic only. Keeping these as two distinct fields
    # is deliberate: migrations through Neon's pooler fail in partially
    # applied ways, and a single field with a flag would make that one typo
    # away. alembic/env.py reads database_url_direct and never falls back.
    database_url_direct: str = ""

    # ---- Object storage (Neon Object Storage, S3-compatible) -------------
    aws_endpoint_url_s3: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-2"
    # The real bucket on this Neon project is "dataset", SINGULAR. A5 found
    # this by listing buckets after HeadBucket returned 404 for "datasets".
    # Neon does not inject the bucket name, so nothing would have caught it.
    neon_storage_bucket: str = "dataset"

    # ---- LLM (Google Gemini, free tier) ----------------------------------
    # Google's own SDK reads GOOGLE_API_KEY first and GEMINI_API_KEY second,
    # and there is a known failure when only GEMINI_API_KEY is set while
    # Application Default Credentials also exist. app/agent/llm.py therefore
    # passes this value EXPLICITLY rather than relying on either lookup.
    gemini_api_key: str = ""

    # Two models, because the work is two different jobs. The planner has to
    # emit a valid tool plan and is worth the stronger model; condensing,
    # explaining and summarising are cheap rewriting tasks that run more often
    # and would burn the free-tier quota on the big model for no gain.
    # Both ids were verified against the live models.list endpoint.
    #
    # NOT gemini-3.8-flash. It exists and answers correctly, but on the free
    # tier it took 548s to return a single token (with thinking disabled, so
    # this is throttling, not reasoning) and 504s at any sane timeout.
    # gemini-3.7-flash measured 154s. The 3.5/3.6 generation returns in ~1.5s.
    # Measurements in docs/PLAN.md §10 risk 1.
    llm_planner_model: str = "gemini-3.6-flash"
    llm_fast_model: str = "gemini-3.5-flash-lite"

    # Kept because the planner model is still a thinking-capable model and the
    # default budget is what made gemini-3.8-flash unusable. 0 disables
    # thinking; None uses the model default. Verified honoured: a call with 0
    # reports reasoning=0 in its usage metadata.
    llm_planner_thinking_budget: int | None = 0

    llm_streaming: bool = True
    llm_timeout_seconds: float = 60.0

    # Attempts for a 429 specifically. The free tier rate-limits per minute,
    # so a short backoff genuinely recovers; anything longer just makes the
    # user wait for a failure.
    llm_max_retries: int = 2

    # ---- Conversation memory (phase B) -----------------------------------
    condenser_enabled: bool = True
    history_window_exchanges: int = 3
    history_token_budget: int = 3000
    summary_refresh_exchanges: int = 2
    summary_max_words: int = 150

    # ---- Streaming (phase B) ---------------------------------------------
    sse_heartbeat_seconds: int = 15

    # ---- Limits ----------------------------------------------------------
    max_upload_bytes: int = 5 * 1024 * 1024
    max_dataset_rows: int = 100_000
    max_datasets_per_session: int = 20
    dataframe_cache_size: int = 3

    # ---- HTTP ------------------------------------------------------------
    cors_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ---- Runtime ---------------------------------------------------------
    environment: str = "development"
    log_level: str = "INFO"
    sentry_dsn: str = ""

    @field_validator("environment")
    @classmethod
    def _known_environment(cls, value):
        allowed = {"development", "production", "test"}
        if value not in allowed:
            raise ValueError(f"environment must be one of {sorted(allowed)}")
        return value

    @computed_field
    @property
    def cors_origins(self) -> list[str]:
        """CORS_ALLOWED_ORIGINS split into a list.

        Parsed here rather than typed as list[str] because pydantic-settings
        would expect JSON for a list field, and a comma-separated string is
        what every hosting dashboard makes it easy to paste.
        """
        return [
            origin.strip().rstrip("/")
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        ]

    @computed_field
    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached accessor, so the .env is parsed once per process.

    Tests that need different values call ``get_settings.cache_clear()``.
    """
    return Settings()


settings = get_settings()
