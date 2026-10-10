"""SOVEREIGN FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from sovereign import __version__
from sovereign.api.middleware import (
    LoggingMiddleware,
    RequestContextMiddleware,
    sovereign_exception_handler,
    unhandled_exception_handler,
)
from sovereign.api.routes.agents import router as agents_router
from sovereign.api.routes.deliverables import router as deliverables_router
from sovereign.api.routes.documents import router as documents_router
from sovereign.api.routes.health import router as health_router
from sovereign.api.routes.knowledge_base import router as kb_router
from sovereign.api.routes.rag import router as rag_router
from sovereign.api.routes.vision_ocr import router as vision_ocr_router
from sovereign.core.config import get_settings
from sovereign.core.errors import SovereignError
from sovereign.core.logging import configure_logging, get_logger
from sovereign.models.gateway import get_model_gateway
from sovereign.storage.db.base import get_db, init_schema


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """App startup/shutdown lifecycle."""
    settings = get_settings()
    configure_logging(settings)
    log = get_logger(__name__)
    log.info("sovereign.startup", env=settings.env, version=__version__)

    # In dev, create indexes (no migrations needed for MongoDB). Prod uses ensure_indexes.
    if settings.is_dev:
        try:
            init_schema()
            log.info("sovereign.schema.initialized", backend="mongodb")
        except Exception as e:
            log.warning("sovereign.schema.init_failed", error=str(e))

    # Pre-construct the ModelGateway so misconfig fails fast at startup.
    try:
        gw = get_model_gateway(settings)
        app.state.model_gateway = gw
        log.info("sovereign.model_gateway.ready", backends=gw.describe())
    except Exception as e:
        log.error("sovereign.model_gateway.failed", error=str(e))
        # Don't crash — let /readyz report the failure so ops can fix config.

    # Pre-warm the MongoDB connection
    get_db(settings)

    yield

    log.info("sovereign.shutdown")


def create_app() -> FastAPI:
    """Build the FastAPI app. Called by uvicorn entrypoint."""
    settings = get_settings()
    app = FastAPI(
        title="SOVEREIGN",
        description=(
            "On-Premise Agentic AI Workbench Using Open-Weight Multimodal LLMs "
            "for Confidential Industrial Work."
        ),
        version=__version__,
        docs_url="/docs" if settings.is_dev else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.is_dev else None,
        lifespan=lifespan,
    )

    # Middleware (order matters: outermost first)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestContextMiddleware)

    # CORS — allow the Next.js workbench to call the API directly
    from starlette.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    app.add_exception_handler(SovereignError, sovereign_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # Routers
    app.include_router(health_router)
    app.include_router(documents_router)
    app.include_router(vision_ocr_router)
    app.include_router(kb_router)
    app.include_router(rag_router)
    app.include_router(agents_router)
    app.include_router(deliverables_router)

    @app.get("/", tags=["root"])
    async def root() -> dict[str, str]:
        return {
            "name": "SOVEREIGN",
            "version": __version__,
            "env": settings.env,
            "docs": "/docs" if settings.is_dev else "disabled",
        }

    return app


# Module-level instance for `uvicorn sovereign.api.app:app`
app = create_app()
