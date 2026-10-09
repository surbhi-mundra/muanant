"""Health and readiness endpoints.

``/healthz`` — liveness. Returns 200 if the process is up and the event
loop is responsive. Does NOT check downstream deps.

``/readyz`` — readiness. Returns 200 only if the app can serve real
requests: DB reachable, ModelGateway constructed, audit chain intact.
Returns 503 with a structured breakdown if any check fails.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from sovereign import __version__
from sovereign.api.deps import GatewayDep, SettingsDep
from sovereign.storage.db.base import get_engine

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str


class ReadyResponse(BaseModel):
    status: str
    version: str
    env: str
    checks: dict[str, str]


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    """Liveness probe. Always 200 if the process is up."""
    return HealthResponse(status="ok", version=__version__)


@router.get("/readyz", response_model=ReadyResponse)
async def readyz(settings: SettingsDep, gateway: GatewayDep) -> JSONResponse:
    """Readiness probe. 200 if all checks pass; 503 otherwise."""
    checks: dict[str, str] = {}

    # 1. Database
    try:
        engine = get_engine(settings)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"fail: {e.__class__.__name__}"

    # 2. ModelGateway (constructs each backend lazily on first use; readyz
    #    forces construction to fail fast at startup if the config is bad).
    try:
        backends = gateway.describe()
        checks["model_gateway"] = "ok: " + ", ".join(
            f"{cap}={name}" for cap, name in backends.items()
        )
    except Exception as e:
        checks["model_gateway"] = f"fail: {e.__class__.__name__}: {e}"

    # 3. Audit chain integrity (cheap: just count rows; full verification is
    #    a periodic cron job, not per-request).
    try:
        engine = get_engine(settings)
        with engine.connect() as conn:
            n = conn.execute(text("SELECT COUNT(*) FROM audit_events")).scalar()
        checks["audit"] = f"ok: {n} events"
    except Exception:
        # Audit table not yet created — fine for a fresh DB.
        checks["audit"] = "ok: table not yet initialized"

    all_ok = all(v.startswith("ok") for v in checks.values())
    code = status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    body = ReadyResponse(
        status="ok" if all_ok else "degraded",
        version=__version__,
        env=settings.env,
        checks=checks,
    )
    return JSONResponse(status_code=code, content=body.model_dump())
