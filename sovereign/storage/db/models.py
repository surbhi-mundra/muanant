"""MongoDB document models — simple dict-based schemas.

MongoDB is schemaless, so these are just helper classes that define
the expected fields and provide convenience constructors. They're
plain dicts with type hints for documentation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, TypedDict


class ProjectDict(TypedDict, total=False):
    id: str
    name: str
    slug: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class UserDict(TypedDict, total=False):
    id: str
    email: str
    display_name: str
    password_hash: str
    role: str
    is_active: bool
    created_at: datetime


class DocumentDict(TypedDict, total=False):
    id: str
    project_id: str
    original_filename: str
    storage_key: str
    mime_type: str
    size_bytes: int
    sha256: str
    status: str
    version: int
    metadata_json: str | None
    created_at: datetime
    updated_at: datetime


class AuditEventDict(TypedDict, total=False):
    id: str
    sequence: int
    prev_hash: str
    hash: str
    timestamp: datetime
    user_id: str | None
    project_id: str | None
    request_id: str | None
    workflow_id: str | None
    category: str
    action: str
    outcome: str
    payload_json: str


def new_document(
    *,
    id: str,
    project_id: str,
    original_filename: str,
    storage_key: str,
    mime_type: str,
    size_bytes: int,
    sha256: str,
    status: str = "uploaded",
    version: int = 1,
    metadata_json: str | None = None,
) -> dict[str, Any]:
    """Create a new document dict with timestamps."""
    now = datetime.now(UTC)
    return {
        "id": id,
        "project_id": project_id,
        "original_filename": original_filename,
        "storage_key": storage_key,
        "mime_type": mime_type,
        "size_bytes": size_bytes,
        "sha256": sha256,
        "status": status,
        "version": version,
        "metadata_json": metadata_json,
        "created_at": now,
        "updated_at": now,
    }


def new_audit_event(
    *,
    id: str,
    sequence: int,
    prev_hash: str,
    hash: str,
    timestamp: datetime,
    user_id: str | None = None,
    project_id: str | None = None,
    request_id: str | None = None,
    workflow_id: str | None = None,
    category: str = "",
    action: str = "",
    outcome: str = "success",
    payload_json: str = "",
) -> dict[str, Any]:
    """Create a new audit event dict."""
    return {
        "id": id,
        "sequence": sequence,
        "prev_hash": prev_hash,
        "hash": hash,
        "timestamp": timestamp,
        "user_id": user_id,
        "project_id": project_id,
        "request_id": request_id,
        "workflow_id": workflow_id,
        "category": category,
        "action": action,
        "outcome": outcome,
        "payload_json": payload_json,
    }
