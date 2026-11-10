"""Liveness endpoint.

Step A3 ships the route and the response shape. Step A5 adds the real
database and object-storage probes; until then the dependency fields report
"unchecked" rather than "ok", because claiming "ok" for something that was
never tested is worse than admitting it.
"""

from fastapi import APIRouter

router = APIRouter(tags=["meta"])


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "database": "unchecked",
        "storage": "unchecked",
        "version": "0.1.0",
    }
