"""The single error envelope from docs/API_CONTRACT.md, and its handlers.

Every failure leaves the API as:

    {"error": {"code": "...", "message": "...", "details": {...}}}

with a real HTTP status code. The legacy endpoints in routers/legacy.py still
return ``{"status": "error"}`` with HTTP 200; they are frozen on purpose and
phase B replaces them.

Raise ``ApiError`` (or a subclass) from anywhere; the handler does the rest.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """An error with a contract code, an HTTP status and a safe message.

    ``message`` is shown to the user, so it must never carry internals.
    """

    status_code = 500
    code = "INTERNAL_ERROR"

    def __init__(self, message=None, details=None, *, code=None, status_code=None):
        super().__init__(message or self.code)
        self.message = message or "Something went wrong."
        self.details = details
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code


class SessionRequired(ApiError):
    status_code = 400
    code = "SESSION_REQUIRED"


class ValidationFailed(ApiError):
    status_code = 400
    code = "VALIDATION_ERROR"


class UnsupportedFile(ApiError):
    status_code = 400
    code = "UNSUPPORTED_FILE"


class NotFound(ApiError):
    status_code = 404
    code = "NOT_FOUND"


class DatasetLimitReached(ApiError):
    status_code = 409
    code = "DATASET_LIMIT_REACHED"


class FileTooLarge(ApiError):
    status_code = 413
    code = "FILE_TOO_LARGE"


class TooManyRows(ApiError):
    status_code = 413
    code = "TOO_MANY_ROWS"


class DatasetRejected(ApiError):
    status_code = 422
    code = "DATASET_REJECTED"


class LLMUnavailable(ApiError):
    status_code = 502
    code = "LLM_UNAVAILABLE"


class ServiceUnavailable(ApiError):
    status_code = 503
    code = "SERVICE_UNAVAILABLE"


def envelope(code, message, details=None):
    body = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    return {"error": body}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError):
        # 5xx is ours to explain, so log it with the traceback; 4xx is the
        # caller's and would only be noise.
        if exc.status_code >= 500:
            logger.exception("ApiError on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=exc.status_code,
            content=envelope(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _request_validation(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=400,
            content=envelope(
                "VALIDATION_ERROR",
                "The request body is not valid.",
                # exc.errors() can contain non-JSON-serialisable values, so
                # it is reduced to location + message pairs.
                {
                    "fields": [
                        {
                            "field": ".".join(str(p) for p in err.get("loc", [])),
                            "message": err.get("msg", ""),
                        }
                        for err in exc.errors()
                    ]
                },
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception(request: Request, exc: StarletteHTTPException):
        """Covers 404s on unknown routes and anything raising HTTPException."""
        code = {
            400: "VALIDATION_ERROR",
            404: "NOT_FOUND",
            405: "VALIDATION_ERROR",
            413: "FILE_TOO_LARGE",
        }.get(exc.status_code, "INTERNAL_ERROR")
        return JSONResponse(
            status_code=exc.status_code,
            content=envelope(code, str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        """Last resort: never let a traceback reach the client in production."""
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)

        message = "Something went wrong."
        details = None
        if not settings.is_production:
            # In development the exception type and text are far more useful
            # in the response than in a log the caller cannot see.
            details = {"exception": type(exc).__name__, "error": str(exc)}

        return JSONResponse(
            status_code=500,
            content=envelope("INTERNAL_ERROR", message, details),
        )
