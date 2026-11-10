"""The only module in the codebase that touches object storage.

Every dataset byte enters and leaves through here. That is the whole point:
Neon Object Storage is **Beta**, and if it has to be abandoned the replacement
(bytea in Postgres, or R2/S3) is a rewrite of this one file and nothing else.
Importing boto3 anywhere else breaks that guarantee — see docs/PLAN.md §4.

Three settings are not defaults and all three are required:

- ``endpoint_url`` points at Neon rather than AWS.
- **Path-style addressing.** The default is virtual-host style,
  ``https://<bucket>.<host>/<key>``, which needs a wildcard DNS record Neon
  does not publish, so requests fail to resolve. Path-style keeps the bucket
  in the path: ``https://<host>/<bucket>/<key>``.
- **SigV4.** The only signature version Neon accepts.

Step A5 establishes the client and the health probe. Step A7 adds save/load.
"""

import logging
import time

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.config import settings

logger = logging.getLogger(__name__)

# Objects live under a flat prefix keyed by dataset id. The key is also stored
# in dataset_files.object_key rather than recomputed, so that changing this
# pattern later does not orphan every existing object.
KEY_PREFIX = "datasets"


class StorageNotConfigured(RuntimeError):
    """Raised when credentials or an endpoint are missing.

    Distinct from a storage *failure*: this one is a deployment mistake, and
    retrying will never fix it.
    """


class StorageError(RuntimeError):
    """A storage operation failed for a reason the caller cannot fix."""


def object_key_for(dataset_id) -> str:
    return f"{KEY_PREFIX}/{dataset_id}.parquet"


_client = None


def get_client():
    """The shared S3 client. Built once; botocore pools connections."""
    global _client
    if _client is not None:
        return _client

    missing = [
        name
        for name, value in (
            ("AWS_ENDPOINT_URL_S3", settings.aws_endpoint_url_s3),
            ("AWS_ACCESS_KEY_ID", settings.aws_access_key_id),
            ("AWS_SECRET_ACCESS_KEY", settings.aws_secret_access_key),
            ("NEON_STORAGE_BUCKET", settings.neon_storage_bucket),
        )
        if not value
    ]
    if missing:
        raise StorageNotConfigured(
            "Object storage is not configured. Missing: " + ", ".join(missing)
        )

    _client = boto3.client(
        "s3",
        endpoint_url=settings.aws_endpoint_url_s3,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=5,
            read_timeout=30,
        ),
    )
    return _client


def reset_client() -> None:
    """Drop the cached client. For tests that change configuration."""
    global _client
    _client = None


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

# HeadBucket is billed as a request and keeps the Neon compute awake, so the
# result is cached. /health can be polled by an uptime monitor every few
# seconds; without this, that monitor alone would stop the compute ever
# autosuspending, which is a real cost on a free tier.
_HEALTH_TTL_SECONDS = 30
_health_cache = {"checked_at": 0.0, "status": None, "detail": None}


def check_storage(force: bool = False):
    """Return ``(status, detail)`` where status is "ok" or "unreachable".

    Never raises: /health must answer even when storage is down, because the
    whole point of the endpoint is to report that.
    """
    now = time.monotonic()
    if (
        not force
        and _health_cache["status"] is not None
        and now - _health_cache["checked_at"] < _HEALTH_TTL_SECONDS
    ):
        return _health_cache["status"], _health_cache["detail"]

    status, detail = "unreachable", None
    try:
        get_client().head_bucket(Bucket=settings.neon_storage_bucket)
        status = "ok"
    except StorageNotConfigured as error:
        detail = str(error)
    except ClientError as error:
        code = error.response.get("Error", {}).get("Code", "Unknown")
        detail = f"HeadBucket failed: {code}"
        logger.warning("Storage health check failed: %s", detail)
    except (BotoCoreError, OSError) as error:
        detail = f"{type(error).__name__}: {error}"
        logger.warning("Storage health check failed: %s", detail)

    _health_cache.update(checked_at=now, status=status, detail=detail)
    return status, detail
