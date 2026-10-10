"""MongoDB storage layer — replaces SQLAlchemy.

Uses PyMongo (synchronous) with a simple session-like wrapper that
provides a clean API for CRUD operations on MongoDB collections.

MongoDB is schemaless, so there are no migrations. Collections are
created automatically on first insert.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from pymongo import ASCENDING, MongoClient
from pymongo.database import Database

from sovereign.core.config import Settings

# Collection names
COLLECTIONS = {
    "projects": "projects",
    "users": "users",
    "documents": "documents",
    "audit_events": "audit_events",
}

# Global client
_client: MongoClient[Any] | None = None
_db: Database[Any] | None = None


def get_client(settings: Settings | None = None) -> MongoClient[Any]:
    """Return the cached MongoDB client.

    If the URL contains ``mock``, uses mongomock for in-process testing.
    """
    global _client  # noqa: PLW0603
    if _client is None:
        if settings is None:
            from sovereign.core.config import get_settings

            settings = get_settings()
        url = settings.database_url
        # Check if we should use mongomock (for testing)
        if "mock" in url or "test" in url.lower():
            try:
                import mongomock

                # mongomock needs a valid mongodb:// URL
                mock_url = url.replace("mock://", "mongodb://")
                _client = mongomock.MongoClient(mock_url)
            except ImportError:
                _client = MongoClient(url)
        else:
            _client = MongoClient(url)
    return _client


def get_db(settings: Settings | None = None) -> Database[Any]:
    """Return the cached MongoDB database."""
    global _db  # noqa: PLW0603
    if _db is None:
        if settings is None:
            from sovereign.core.config import get_settings

            settings = get_settings()
        client = get_client(settings)
        # Extract DB name from URL, or use "sovereign" as default
        db_name = "sovereign"
        _db = client[db_name]
    return _db


@contextmanager
def session_scope() -> Iterator[Database[Any]]:
    """Context manager: yields the MongoDB database.

    MongoDB doesn't have sessions like SQLAlchemy. This is kept for
    API compatibility — it just returns the database object.
    """
    db = get_db()
    try:
        yield db
    except Exception:
        # MongoDB auto-commits each operation, so rollback isn't needed
        # in the same way. But we still want to propagate the error.
        raise


def reset_engine() -> None:
    """Test helper: drop the cached client + db."""
    global _client, _db  # noqa: PLW0603
    if _client is not None:
        _client.close()
    _client = None
    _db = None


def init_schema() -> None:
    """Create indexes and drop existing data (for test isolation).

    MongoDB is schemaless; collections auto-create. This:
    1. Drops all collections (for clean test state)
    2. Recreates indexes

    In prod, call ``ensure_indexes()`` instead (doesn't drop data).
    """
    db = get_db()

    # Drop all collections for clean state
    for col_name in COLLECTIONS.values():
        db[col_name].drop()

    # Recreate indexes
    ensure_indexes(db)


def ensure_indexes(db: Database[Any] | None = None) -> None:
    """Create indexes without dropping data. Safe to call on startup."""
    if db is None:
        db = get_db()

    # Projects
    db[COLLECTIONS["projects"]].create_index("id", unique=True)
    db[COLLECTIONS["projects"]].create_index("slug", unique=True)

    # Users
    db[COLLECTIONS["users"]].create_index("id", unique=True)
    db[COLLECTIONS["users"]].create_index("email", unique=True)

    # Documents
    db[COLLECTIONS["documents"]].create_index("id", unique=True)
    db[COLLECTIONS["documents"]].create_index("project_id")
    db[COLLECTIONS["documents"]].create_index("status")
    db[COLLECTIONS["documents"]].create_index("sha256")

    # Audit events
    db[COLLECTIONS["audit_events"]].create_index("id", unique=True)
    db[COLLECTIONS["audit_events"]].create_index("sequence", unique=True)
    db[COLLECTIONS["audit_events"]].create_index("hash", unique=True)
    db[COLLECTIONS["audit_events"]].create_index("request_id")
    db[COLLECTIONS["audit_events"]].create_index("workflow_id")
    db[COLLECTIONS["audit_events"]].create_index([("category", ASCENDING), ("timestamp", ASCENDING)])
    db[COLLECTIONS["audit_events"]].create_index([("project_id", ASCENDING), ("timestamp", ASCENDING)])
