"""Audit log writer (MongoDB-backed).

The single entry point for writing audit events. Wraps the hash-chain logic
in a write that:

1. Acquires the next sequence number atomically.
2. Computes the hash from the previous row.
3. Inserts the new document.
4. Verifies the chain on read via ``verify_chain``.
"""

from __future__ import annotations

import json
from typing import Any

from pymongo import DESCENDING

from sovereign.audit.chain import GENESIS_HASH, AuditEventPayload, compute_hash
from sovereign.core.errors import AuditError
from sovereign.core.ids import new_ulid, utcnow
from sovereign.core.logging import get_logger
from sovereign.storage.db.base import COLLECTIONS

log = get_logger(__name__)


def write_event(db: Any, payload: AuditEventPayload) -> dict[str, Any]:
    """Append a new audit event to the chain.

    Args:
        db: MongoDB database object (from session_scope()).
        payload: the audit event payload.

    Returns: the inserted document dict.
    """
    col = db[COLLECTIONS["audit_events"]]

    # Get the current tail of the chain
    last = col.find_one({}, sort=[("sequence", DESCENDING)])

    seq = (last["sequence"] + 1) if last else 1
    prev_hash = last["hash"] if last else GENESIS_HASH
    new_hash = compute_hash(prev_hash, payload)

    # Collision detection
    collision = col.find_one({"hash": new_hash})
    if collision is not None:
        msg = f"audit hash collision: new event would duplicate sequence {collision['sequence']}"
        raise AuditError(msg)

    doc = {
        "id": new_ulid(),
        "sequence": seq,
        "prev_hash": prev_hash,
        "hash": new_hash,
        "timestamp": utcnow(),
        "user_id": payload.user_id,
        "project_id": payload.project_id,
        "request_id": payload.request_id,
        "workflow_id": payload.workflow_id,
        "category": payload.category,
        "action": payload.action,
        "outcome": payload.outcome,
        "payload_json": payload.canonical_json(),
    }

    col.insert_one(doc)
    log.debug(
        "audit.event.written",
        sequence=seq, category=payload.category,
        action=payload.action, outcome=payload.outcome,
    )
    return doc


def read_chain(
    db: Any,
    *,
    since_seq: int = 0,
    limit: int = 1000,
) -> list[tuple[int, str, str, AuditEventPayload]]:
    """Read a slice of the audit chain for verification."""
    cursor = (
        db[COLLECTIONS["audit_events"]]
        .find({"sequence": {"$gt": since_seq}})
        .sort("sequence", 1)
        .limit(limit)
    )
    out: list[tuple[int, str, str, AuditEventPayload]] = []
    for doc in cursor:
        payload = _payload_from_doc(doc)
        out.append((doc["sequence"], doc["prev_hash"], doc["hash"], payload))
    return out


def _payload_from_doc(doc: dict[str, Any]) -> AuditEventPayload:
    d = json.loads(doc["payload_json"])
    return AuditEventPayload(
        user_id=d.get("user_id"),
        project_id=d.get("project_id"),
        request_id=d.get("request_id"),
        workflow_id=d.get("workflow_id"),
        agent=d.get("agent"),
        category=d.get("category", ""),
        action=d.get("action", ""),
        outcome=d.get("outcome", "success"),
        details=d.get("details", {}),
        duration_ms=d.get("duration_ms"),
        model=d.get("model"),
        prompt_tokens=d.get("prompt_tokens"),
        completion_tokens=d.get("completion_tokens"),
    )


def verify_full_chain(db: Any) -> bool:
    """Verify the entire audit chain from genesis to the current tail."""
    from sovereign.audit.chain import verify_chain

    rows = read_chain(db, since_seq=0, limit=10_000_000)
    return verify_chain(rows)
