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


def _split_models(value: str) -> list[str]:
    """Parse a comma-separated model chain, preserving order.

    Duplicates are dropped rather than tolerated: the same model twice in a
    chain means the second attempt burns a call against a quota that has
    already been refused.
    """
    seen = []
    for part in (value or "").split(","):
        name = part.strip()
        if name and name not in seen:
            seen.append(name)
    return seen


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

    # FALLBACK CHAINS, not single models. The free tier's 20-requests-per-day
    # quota is per MODEL, so a chain of three is three times the daily
    # capacity; on a 429 the next model is tried immediately, because a daily
    # quota will not recover from a backoff no matter how long it waits.
    #
    # Comma-separated, highest preference first.
    #
    # Dropped from the planner chain: gemini-3-flash-preview. It exists in
    # v1beta but NOT in v1, and langchain-google-genai 4.4.3 calls v1
    # (observed: POST /v1/models/<id>:generateContent), so it would 404.
    # gemini-3.5-flash is a verified v1 alternative if a third is wanted.
    llm_planner_models: str = "gemini-3.6-flash,gemini-2.5-flash"
    llm_fast_models: str = (
        "gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemini-2.5-flash-lite"
    )

    # Thinking is configured per MODEL, never per role: capability belongs to
    # the model. 0 disables thinking where that is allowed; blank uses each
    # model's default.
    #
    # Note that "supports thinking" and "can have thinking turned off" are
    # different things and the API does not expose the second one. models.list
    # reports thinking=True for every model in both chains, yet
    # gemini-3.5-flash-lite accepts a budget of 512 or -1 and REJECTS 0 with a
    # bare INVALID_ARGUMENT. So llm.py probes it: a model that rejects the
    # budget is remembered and retried without it.
    llm_thinking_budget: int | None = 0

    # Ask Gemini for JSON directly (response_mime_type) for the planner. The
    # planner used to wrap its JSON in a ```json fence on attempt 1 of every
    # question, which failed json.loads and burned a second planner call on
    # the retry — doubling consumption against a 20/day quota.
    llm_planner_json_mode: bool = True

    # Cache LLM responses on disk, keyed by (model, full prompt). A
    # DEVELOPMENT tool: it makes repeated verification runs free, which
    # matters when the daily quota is 20. Refused in production by
    # app/agent/llm.py regardless of this value.
    llm_dev_cache: bool = False
    llm_dev_cache_dir: str = ".llm_cache"

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
    def planner_models(self) -> list[str]:
        return _split_models(self.llm_planner_models)

    @computed_field
    @property
    def fast_models(self) -> list[str]:
        return _split_models(self.llm_fast_models)

    @computed_field
    @property
    def dev_cache_enabled(self) -> bool:
        """The cache is never on in production, whatever the env file says.

        Serving a cached answer to a real user would be wrong in a way that is
        very hard to notice: the answer looks fine, it is just stale and was
        computed for a different dataset. So the environment wins over the
        flag, rather than the other way round.
        """
        return self.llm_dev_cache and not self.is_production

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
