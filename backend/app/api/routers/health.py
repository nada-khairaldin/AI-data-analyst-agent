"""Liveness and dependency reachability.

Contract: docs/API_CONTRACT.md endpoint 1. Returns 200 when every dependency
answers and 503 when any does not, with each dependency reported separately so
the response says *which* one broke rather than just "unhealthy".

Both probes are cached for 30 seconds. That is not a micro-optimisation: Neon
autosuspends an idle compute, and an uptime monitor polling /health every few
seconds would keep both the database and the storage endpoint permanently
awake, burning free-tier quota for no information. The contract's own note
asks for this endpoint to stay cheap.
"""

import asyncio
import logging
import time

from fastapi import APIRouter, Response
from sqlalchemy import text

from app.db.session import engine
from app.services.dataframe_store import check_storage

logger = logging.getLogger(__name__)

router = APIRouter(tags=["meta"])

VERSION = "0.1.0"

_DB_TTL_SECONDS = 30

# Measured against this Neon project: a COLD connection (compute autosuspended)
# took 4.89s; warm ones 1.63s and 1.67s. A 5s timeout sat right on that
# boundary and reported a perfectly healthy database as "unreachable", so the
# limit is set well clear of a cold start rather than near it. The cost of
# being wrong in this direction is a slow 200; the other direction is a false
# alarm that fails a deploy.
_DB_TIMEOUT_SECONDS = 15.0
_db_cache = {"checked_at": 0.0, "status": None}


async def check_database(force: bool = False) -> str:
    """"ok" or "unreachable". Never raises.

    A bounded timeout matters more here than anywhere else: a suspended Neon
    compute takes a few seconds to wake, and without a cap a health check can
    hang for the whole platform timeout and be recorded as a hard failure
    instead of a slow success.
    """
    now = time.monotonic()
    if (
        not force
        and _db_cache["status"] is not None
        and now - _db_cache["checked_at"] < _DB_TTL_SECONDS
    ):
        return _db_cache["status"]

    status = "unreachable"
    try:
        async with asyncio.timeout(_DB_TIMEOUT_SECONDS):
            async with engine.connect() as conn:
                # SELECT 1, exactly as the contract asks.
                await conn.execute(text("select 1"))
        status = "ok"
    except TimeoutError:
        logger.warning(
            "Database health check timed out after %ss", _DB_TIMEOUT_SECONDS
        )
    except Exception as error:
        logger.warning(
            "Database health check failed: %s: %s", type(error).__name__, error
        )

    _db_cache.update(checked_at=now, status=status)
    return status


@router.get("/health")
async def health(response: Response, force: bool = False):
    """``?force=true`` bypasses the cache, for debugging a live deployment."""
    database = await check_database(force=force)
    storage, storage_detail = check_storage(force=force)

    healthy = database == "ok" and storage == "ok"
    if not healthy:
        response.status_code = 503

    body = {
        "status": "ok" if healthy else "degraded",
        "database": database,
        "storage": storage,
        "version": VERSION,
    }
    # Only ever populated for a failure, and it carries a botocore error code
    # or an exception name — never a credential or a connection string.
    if storage_detail:
        body["storageDetail"] = storage_detail
    return body
