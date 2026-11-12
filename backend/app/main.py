"""Application factory.

Start with, from ``backend/``:

    uvicorn app.main:app --reload

The old entry point was ``backend/main.py`` with flat imports, which meant it
only ran when the working directory happened to be ``backend/`` — not how any
hosting platform starts a process. Everything is now importable as
``app.*`` from the ``backend/`` root.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_exception_handlers
from app.api.routers import conversations, datasets, health
from app.config import settings

__version__ = "0.1.0"


def create_app() -> FastAPI:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    app = FastAPI(
        title="Data Analysis Agent API",
        version=__version__,
        # Interactive docs are a development tool; in production they
        # advertise the whole surface to anyone who finds the URL.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        # No cookies are used — the session travels in the X-Session-Id
        # header — so credentials stay off. This also keeps the door shut on
        # the allow_origins=["*"] + credentials combination that browsers
        # reject outright.
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        # X-Session-Id is a custom header: if it is missing from this list,
        # every preflight fails and nothing works in a browser while curl
        # keeps succeeding. See docs/PLAN.md §8.
        allow_headers=["Content-Type", "X-Session-Id", "Accept"],
    )

    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(datasets.router)
    app.include_router(conversations.router)

    @app.get("/", tags=["meta"])
    def read_root():
        return {"message": "Welcome to the Data Analysis Agent API!"}

    return app


app = create_app()
