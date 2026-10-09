"""Structured logging for SOVEREIGN.

Uses ``structlog`` for JSON output in prod / pretty console output in dev.
A redaction processor scrubs known-secret keys from every log record so we
never accidentally emit JWT secrets, API keys, or password hashes.

Confidential document *content* is never logged by this module — that's a
caller responsibility (don't pass raw chunk text into log calls). The
redaction list below is for *credentials* and *identifiers*, not content.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from sovereign.core.config import Settings

# Keys whose values get scrubbed regardless of context.
_REDACT_KEYS: frozenset[str] = frozenset({
    "password",
    "password_hash",
    "secret",
    "api_key",
    "apikey",
    "token",
    "access_token",
    "refresh_token",
    "jwt",
    "jwt_secret",
    "authorization",
    "cookie",
    "private_key",
    "qdrant_api_key",
})

# Patterns that match inside string values; the match is replaced with ***.
_REDACT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Bearer tokens in Authorization headers
    (re.compile(r"(Bearer\s+)([A-Za-z0-9._\-]+)"), r"\1***"),
    # postgres://user:password@host
    (re.compile(r"(postgres(?:ql)?://[^:\s]+:)([^@]+)(@)"), r"\1***\3"),
    # aws-style keys AKIA...
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "***AKIA***"),
]


def _redact_value(v: Any) -> Any:
    """Redact a single value if it's a string matching known secret patterns."""
    if not isinstance(v, str):
        return v
    out = v
    for pat, repl in _REDACT_PATTERNS:
        out = pat.sub(repl, out)
    return out


def redactor(
    _logger: Any, _method: str, event_dict: EventDict
) -> EventDict:
    """structlog processor: scrub known-secret keys and patterns from the event."""
    for key in list(event_dict):
        lk = key.lower()
        if lk in _REDACT_KEYS:
            event_dict[key] = "***REDACTED***"
        else:
            event_dict[key] = _redact_structure(event_dict[key])
    return event_dict


def _redact_structure(v: Any, depth: int = 0) -> Any:
    if depth > 6:
        return v
    if isinstance(v, dict):
        out = {}
        for k, vv in v.items():
            if isinstance(k, str) and k.lower() in _REDACT_KEYS:
                out[k] = "***REDACTED***"
            else:
                out[k] = _redact_structure(vv, depth + 1)
        return out
    if isinstance(v, list | tuple):
        return type(v)(_redact_structure(x, depth + 1) for x in v)
    return _redact_value(v)


def configure_logging(settings: Settings) -> None:
    """Configure structlog + stdlib logging once at app startup.

    Idempotent. Safe to call multiple times (tests do).
    """
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Stdlib root — needed because uvicorn / sqlalchemy emit via stdlib.
    logging.basicConfig(
        format="%(message)s",
        stream=None,
        force=True,
    )
    root = logging.getLogger()
    root.setLevel(level)

    # stdlib -> structlog adapter
    processor_chain: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        redactor,
    ]
    if settings.log_format == "json" and not settings.is_dev:
        processor_chain.append(structlog.processors.JSONRenderer())
    else:
        # dev or console-mode: pretty but still structured
        processor_chain.append(structlog.dev.ConsoleRenderer(colors=settings.is_dev))

    structlog.configure(
        processors=processor_chain,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Bridge stdlib loggers (uvicorn, sqlalchemy) into structlog.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy.engine"):
        lg = logging.getLogger(name)
        lg.handlers = []
        lg.propagate = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structured logger.

    Usage::

        log = get_logger(__name__)
        log.info("document.ingested", doc_id=doc_id, project_id=project_id)
    """
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger


def bind_request_context(
    *, request_id: str, workflow_id: str | None = None, user_id: str | None = None,
    project_id: str | None = None,
) -> Callable[[], None]:
    """Bind request-scoped context to all subsequent log calls in this async task.

    Returns an unbind callable for middleware to call on response.
    """
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    if workflow_id:
        structlog.contextvars.bind_contextvars(workflow_id=workflow_id)
    if user_id:
        structlog.contextvars.bind_contextvars(user_id=user_id)
    if project_id:
        structlog.contextvars.bind_contextvars(project_id=project_id)
    return structlog.contextvars.clear_contextvars
