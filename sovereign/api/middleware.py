"""FastAPI middleware: request ID, structured logging, error handling."""

from __future__ import annotations

import time
import traceback
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from sovereign.core.errors import SovereignError
from sovereign.core.ids import new_request_id
from sovereign.core.logging import bind_request_context, get_logger

log = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign a request ID and bind it to the structlog contextvars.

    If the client sent ``X-Request-ID``, we honor it (capped at 64 chars)
    so upstream proxies can correlate. Otherwise we generate a new one.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        client_rid = request.headers.get("X-Request-ID", "").strip()[:64]
        request_id = client_rid or new_request_id()
        request.state.request_id = request_id

        unbind = bind_request_context(request_id=request_id)
        try:
            response = await call_next(request)
        finally:
            unbind()

        response.headers["X-Request-ID"] = request_id
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with method, path, status, latency, request_id."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Skip health probes — they're noisy and contain no signal.
        path = request.url.path
        if path in ("/healthz", "/readyz"):
            return await call_next(request)

        start = time.perf_counter()
        status_code = 500
        error_code: str | None = None
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except SovereignError as e:
            status_code = e.http_status
            error_code = e.code
            raise
        except Exception:
            error_code = "unhandled"
            raise
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            log.info(
                "http.request",
                method=request.method,
                path=path,
                status=status_code,
                duration_ms=duration_ms,
                error_code=error_code,
                client=request.client.host if request.client else None,
            )


async def sovereign_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Translate SovereignError into a structured JSON response.

    Non-SovereignError exceptions fall through to the unhandled handler
    (registered separately). This handler is registered for
    ``SovereignError`` only, but the signature accepts ``Exception`` to
    satisfy Starlette's type contract.
    """
    if not isinstance(exc, SovereignError):
        # Shouldn't happen — registered for SovereignError only — but be safe.
        return await unhandled_exception_handler(request, exc)

    request_id = getattr(request.state, "request_id", None)
    log.warning(
        "http.error",
        request_id=request_id,
        code=exc.code,
        message=exc.message,
        http_status=exc.http_status,
    )
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "request_id": request_id,
            }
        },
        headers=({"X-Request-ID": request_id} if request_id else {}),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last-resort handler. Logs full traceback, returns generic 500."""
    request_id = getattr(request.state, "request_id", None)
    # Capture traceback string for the log; do NOT put it in the response body.
    tb = traceback.format_exc()
    log.error(
        "http.unhandled",
        request_id=request_id,
        error=str(exc),
        traceback=tb,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "sovereign.unhandled",
                "message": "An unexpected error occurred.",
                "request_id": request_id,
            }
        },
        headers=({"X-Request-ID": request_id} if request_id else {}),
    )
