"""SQLAlchemy 2.0 declarative base + session factory."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from sovereign.core.config import Settings


class Base(DeclarativeBase):
    """Declarative base for all SOVEREIGN tables."""


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine(settings: Settings | None = None) -> Engine:
    global _engine  # noqa: PLW0603
    if _engine is None:
        if settings is None:
            from sovereign.core.config import get_settings  # noqa: PLC0415

            settings = get_settings()
        kwargs: dict[str, Any] = {"future": True}
        if settings.database_url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
            if ":memory:" in settings.database_url:
                kwargs["poolclass"] = StaticPool
        _engine = create_engine(settings.database_url, **kwargs)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal  # noqa: PLW0603
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    factory = get_session_factory()
    s = factory()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def reset_engine() -> None:
    global _engine, _SessionLocal  # noqa: PLW0603
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def init_schema() -> None:
    from sovereign.storage.db import models  # noqa: F401, PLC0415

    Base.metadata.drop_all(get_engine())
    Base.metadata.create_all(get_engine())
