"""DB package — re-exports the public surface (MongoDB)."""

from sovereign.storage.db.base import (
    COLLECTIONS,
    get_client,
    get_db,
    init_schema,
    reset_engine,
    session_scope,
)
from sovereign.storage.db.models import (
    AuditEventDict,
    DocumentDict,
    ProjectDict,
    UserDict,
    new_audit_event,
    new_document,
)

__all__ = [
    "COLLECTIONS",
    "AuditEventDict",
    "DocumentDict",
    "ProjectDict",
    "UserDict",
    "get_client",
    "get_db",
    "init_schema",
    "new_audit_event",
    "new_document",
    "reset_engine",
    "session_scope",
]
