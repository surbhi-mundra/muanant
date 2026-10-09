"""SOVEREIGN API — FastAPI app.

Phase 1 surface:
- ``GET  /healthz``  — liveness (always 200 if process is up)
- ``GET  /readyz``   — readiness (DB + ModelGateway + audit chain)
- ``GET  /``         — service info (name, version, env)

Middleware:
- ``RequestContextMiddleware`` — assigns request_id, binds structlog context
- ``LoggingMiddleware``        — structured request/response log
- Global exception handler     — translates SovereignError -> JSON, logs details

Business routes (documents, rag, agents, approvals, audit, admin) are added
in later phases. Each phase adds a router in ``routes/`` and includes it
from ``app.py``.
"""
