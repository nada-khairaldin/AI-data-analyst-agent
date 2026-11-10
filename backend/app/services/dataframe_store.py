"""The only module in the codebase that touches object storage.

Every dataset byte enters and leaves through here. That is the whole point:
Neon Object Storage is **Beta**, and if it has to be abandoned the replacement
(bytea in Postgres, or R2/S3) is a rewrite of this one file and nothing else.
Importing boto3 anywhere else breaks that guarantee — see docs/PLAN.md §4.

Three client settings are not defaults and all three are required:

- ``endpoint_url`` points at Neon rather than AWS.
- **Path-style addressing.** The default is virtual-host style,
  ``https://<bucket>.<host>/<key>``, which needs a wildcard DNS record Neon
  does not publish, so requests fail to resolve. Path-style keeps the bucket
  in the path: ``https://<host>/<bucket>/<key>``.
- **SigV4.** The only signature version Neon accepts.
"""

import io
import logging
import time
from collections import OrderedDict

import boto3
import pandas as pd
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.config import settings

logger = logging.getLogger(__name__)

# Objects live under a flat prefix keyed by dataset id. The key is also stored
# in dataset_files.object_key rather than recomputed, so that changing this
# pattern later does not orphan every existing object.
#
# Note the prefix is plural while the BUCKET is "dataset", singular. That is
# not a typo: the bucket name is what already exists on this Neon project.
KEY_PREFIX = "datasets"


class StorageNotConfigured(RuntimeError):
    """Raised when credentials or an endpoint are missing.

    Distinct from a storage *failure*: this one is a deployment mistake, and
    retrying will never fix it.
    """


class StorageError(RuntimeError):
    """A storage operation failed for a reason the caller cannot fix."""


class ObjectMissing(StorageError):
    """A dataset_files row points at an object that is not in the bucket.

    Its own class because it is the one storage failure with a sensible user
    response — re-upload — rather than "try again later".
    """


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


# ---------------------------------------------------------------------------
# The LRU cache
# ---------------------------------------------------------------------------

# Parsing a few MB of Parquet on every question is pure waste when the same
# dataset is asked about repeatedly, which is the normal pattern. The cache is
# small on purpose: each entry is a whole DataFrame in memory, and the plan
# budgets three (docs/PLAN.md §11 Q4).
#
# IMPORTANT CONTRACT: load() returns the CACHED object, not a copy. Copying a
# 100k-row frame on every request would defeat the point of caching. Callers
# must not mutate it. execute_plan() already copies before doing anything and
# normalize_dataframe() never mutates its input, so nothing in this codebase
# violates that today — but a future caller that did would corrupt every later
# answer for the same dataset, which is why it is stated here and asserted in
# the tests.
_frame_cache = OrderedDict()


def _cache_get(key):
    if key in _frame_cache:
        _frame_cache.move_to_end(key)
        return _frame_cache[key]
    return None


def _cache_put(key, frame):
    _frame_cache[key] = frame
    _frame_cache.move_to_end(key)
    while len(_frame_cache) > max(1, settings.dataframe_cache_size):
        evicted, _ = _frame_cache.popitem(last=False)
        logger.debug("Evicted %s from the dataframe cache", evicted)


def invalidate(object_key: str) -> None:
    """Drop one entry. Called on overwrite and on delete.

    Without this, deleting a dataset and uploading a new one that reused the
    key would serve the old frame from memory.
    """
    _frame_cache.pop(object_key, None)


def cache_info() -> dict:
    """For tests, and for a future metrics line."""
    return {
        "size": len(_frame_cache),
        "maxsize": max(1, settings.dataframe_cache_size),
        "keys": list(_frame_cache),
    }


def clear_cache() -> None:
    _frame_cache.clear()


# ---------------------------------------------------------------------------
# Save and load
# ---------------------------------------------------------------------------


def save(dataset_id, frame: pd.DataFrame) -> tuple[str, int]:
    """Write the normalised frame as Parquet. Returns (object_key, byte_size).

    Parquet rather than CSV because it carries the dtypes that
    normalize_dataframe() worked out. Re-reading a CSV would mean redoing type
    inference and risking a different answer to the same question.

    ``index=False`` because the stored frame is the normalised working
    dataframe, whose index is a meaningless RangeIndex. Writing it would add a
    phantom ``__index_level_0__`` column that then appears in the schema the
    planner sees.
    """
    key = object_key_for(dataset_id)

    buffer = io.BytesIO()
    try:
        frame.to_parquet(buffer, engine="pyarrow", index=False, compression="snappy")
    except Exception as error:
        raise StorageError(f"Could not serialise the dataset to Parquet: {error}")

    payload = buffer.getvalue()

    try:
        get_client().put_object(
            Bucket=settings.neon_storage_bucket,
            Key=key,
            Body=payload,
            ContentType="application/vnd.apache.parquet",
        )
    except StorageNotConfigured:
        raise
    except (ClientError, BotoCoreError, OSError) as error:
        raise StorageError(f"Could not store the dataset: {_describe(error)}")

    # An overwrite must not leave the previous frame cached.
    invalidate(key)
    _cache_put(key, frame)

    logger.info("Stored %s (%d bytes)", key, len(payload))
    return key, len(payload)


def load(object_key: str) -> pd.DataFrame:
    """Read a stored frame, from cache when possible.

    Raises ``ObjectMissing`` when the row points at an object that is not
    there. That is the *recoverable* half of the delete ordering in
    docs/PLAN.md §4: the dataset can be re-uploaded, and the error says so
    instead of surfacing as an empty result.
    """
    cached = _cache_get(object_key)
    if cached is not None:
        return cached

    try:
        response = get_client().get_object(
            Bucket=settings.neon_storage_bucket, Key=object_key
        )
        payload = response["Body"].read()
    except StorageNotConfigured:
        raise
    except ClientError as error:
        code = str(error.response.get("Error", {}).get("Code", ""))
        if code in ("NoSuchKey", "404", "NotFound"):
            raise ObjectMissing(
                f"The stored dataset {object_key!r} is missing. It was deleted "
                "or never finished uploading; the dataset must be re-uploaded."
            )
        raise StorageError(f"Could not read the dataset: {_describe(error)}")
    except (BotoCoreError, OSError) as error:
        raise StorageError(f"Could not read the dataset: {_describe(error)}")

    try:
        frame = pd.read_parquet(io.BytesIO(payload), engine="pyarrow")
    except Exception as error:
        raise StorageError(
            f"The stored dataset {object_key!r} is not readable Parquet: {error}"
        )

    _cache_put(object_key, frame)
    return frame


def delete(object_key: str) -> bool:
    """Remove an object. Returns True on success, False on failure.

    Deliberately does NOT raise. The caller deletes the object *before* the
    database row (docs/PLAN.md §4), and a failure here must not abort that:
    the user asked for the dataset to be gone, and a row pointing at a live
    object is recoverable while an object with no row is invisible.

    Two honest limits, both from Neon's current behaviour:

    - This is a **soft delete**: the storage is not reclaimed. It is still a
      real delete as far as readers are concerned — verified against the live
      bucket, a subsequent GetObject returns NoSuchKey and load() raises
      ObjectMissing — but because nothing confirms the bytes are gone,
      "deleted" should not be presented to a user as erasure.
    - Lifecycle rules are accepted but **not enforced**, so a TTL cannot clean
      up after a failure here either. A failed delete is logged as a warning
      so the orphan is at least discoverable.
    """
    invalidate(object_key)
    try:
        get_client().delete_object(Bucket=settings.neon_storage_bucket, Key=object_key)
        return True
    except (StorageNotConfigured, ClientError, BotoCoreError, OSError) as error:
        logger.warning(
            "ORPHANED OBJECT: failed to delete %s: %s", object_key, _describe(error)
        )
        return False


def exists(object_key: str) -> bool:
    try:
        get_client().head_object(Bucket=settings.neon_storage_bucket, Key=object_key)
        return True
    except ClientError:
        return False
    except (StorageNotConfigured, BotoCoreError, OSError):
        return False


def _describe(error) -> str:
    """A short, safe description. Never includes credentials or the endpoint."""
    if isinstance(error, ClientError):
        detail = error.response.get("Error", {})
        return f"{detail.get('Code', 'Unknown')}: {detail.get('Message', '')}".strip()
    return f"{type(error).__name__}: {error}"
