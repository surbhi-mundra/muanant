"""FastAPI dependencies: settings, db session, model gateway."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from sovereign.core.config import Settings, get_settings
from sovereign.models.gateway import ModelGateway, get_model_gateway
from sovereign.storage.db import session_scope


def get_app_settings() -> Settings:
    """DI for Settings (cached singleton)."""
    return get_settings()


def get_request_db(request: Request) -> Iterator[Session]:
    """Yield a Session scoped to this request.

    Uses ``session_scope()`` — commits on success, rolls back on error.
    """
    with session_scope() as s:
        yield s


def get_gateway(request: Request) -> ModelGateway:
    """DI for ModelGateway. Cached as app state on startup."""
    gw = getattr(request.app.state, "model_gateway", None)
    if gw is None:  # pragma: no cover — startup wires it
        gw = get_model_gateway()
    return gw


# Type aliases for use in route signatures
SettingsDep = Annotated[Settings, Depends(get_app_settings)]
SessionDep = Annotated[Session, Depends(get_request_db)]
GatewayDep = Annotated[ModelGateway, Depends(get_gateway)]
