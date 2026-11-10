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
    neon_storage_bucket: str = "datasets"

    # ---- LLM -------------------------------------------------------------
    # Preferred name. Falls back to HUGGINGFACE_API_KEY, which is what the
    # original agent/core.py and agent/explainer.py read directly, so an
    # existing .env keeps working through the transition.
    llm_api_key: str = ""
    huggingface_api_key: str = ""

    llm_base_url: str = "https://router.huggingface.co/v1"

    # Default is the id that agent/core.py and agent/explainer.py previously
    # hardcoded, so removing those literals does not change behaviour for an
    # .env that has no LLM_MODEL. It is a default, not a recommendation: step
    # A4 checks whether it actually resolves on LLM_BASE_URL, and
    # docs/PLAN.md risk 1 is about exactly this string.
    llm_model: str = "Qwen/Qwen3.8-Flash-Next:featherless-ai"
    llm_streaming: bool = True
    llm_timeout_seconds: float = 60.0
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
    def resolved_llm_api_key(self) -> str:
        """LLM_API_KEY if set, else the legacy HUGGINGFACE_API_KEY."""
        return self.llm_api_key or self.huggingface_api_key

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
