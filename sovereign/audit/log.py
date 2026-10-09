"""Audit log writer.

The single entry point for writing audit events. Wraps the hash-chain logic
in a transactional write that:

1. Acquires the next sequence number atomically (with a row lock on the
   highest-sequence row, or a sequence-coalesced insert).
2. Computes the hash from the previous row.
3. Inserts the new row.
4. Verifies the chain on read via ``verify_chain``.

For SQLite (dev), the "row lock" is serialized via the connection's
``BEGIN IMMEDIATE``. For Postgres (prod), it's a ``SELECT ... FOR UPDATE``
on the max-sequence row.
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from sovereign.audit.chain import (
    GENESIS_HASH,
    AuditEventPayload,
    compute_hash,
    verify_chain,
)
from sovereign.core.errors import AuditError
from sovereign.core.ids import new_ulid, utcnow
from sovereign.core.logging import get_logger
from sovereign.storage.db.models import AuditEvent

log = get_logger(__name__)


def write_event(session: Session, payload: AuditEventPayload) -> AuditEvent:
    """Append a new audit event to the chain.

    Must be called inside a ``session_scope()`` context. The caller is
    responsible for committing (or rolling back on failure).

    Returns the persisted ``AuditEvent`` row.
    """
    # Get the current tail of the chain.
    stmt = select(AuditEvent).order_by(AuditEvent.sequence.desc()).limit(1)
    if session.bind and session.bind.dialect.name == "postgresql":
        stmt = stmt.with_for_update()
    last = session.execute(stmt).scalar_one_or_none()

    seq = (last.sequence + 1) if last else 1
    prev_hash = last.hash if last else GENESIS_HASH
    new_hash = compute_hash(prev_hash, payload)

    # Sanity: collision detection (should never happen, but cheap to check).
    collision = session.execute(
        select(AuditEvent).where(AuditEvent.hash == new_hash)
    ).scalar_one_or_none()
    if collision is not None:
        msg = f"audit hash collision: new event would duplicate sequence {collision.sequence}"
        raise AuditError(msg)

    row = AuditEvent(
        id=new_ulid(),
        sequence=seq,
        prev_hash=prev_hash,
        hash=new_hash,
        timestamp=utcnow(),
        user_id=payload.user_id,
        project_id=payload.project_id,
        request_id=payload.request_id,
        workflow_id=payload.workflow_id,
        category=payload.category,
        action=payload.action,
        outcome=payload.outcome,
        payload_json=payload.canonical_json(),
    )
    session.add(row)
    session.flush()
    log.debug(
        "audit.event.written",
        sequence=seq,
        category=payload.category,
        action=payload.action,
        outcome=payload.outcome,
    )
    return row


def read_chain(
    session: Session,
    *,
    since_seq: int = 0,
    limit: int = 1000,
) -> list[tuple[int, str, str, AuditEventPayload]]:
    """Read a slice of the audit chain for verification.

    Returns tuples of (sequence, prev_hash, stored_hash, payload).
    """
    stmt = (
        select(AuditEvent)
        .where(AuditEvent.sequence > since_seq)
        .order_by(AuditEvent.sequence.asc())
        .limit(limit)
    )
    rows = session.execute(stmt).scalars().all()
    out: list[tuple[int, str, str, AuditEventPayload]] = []
    for r in rows:
        payload = _payload_from_row(r)
        out.append((r.sequence, r.prev_hash, r.hash, payload))
    return out


def _payload_from_row(r: AuditEvent) -> AuditEventPayload:
    """Reconstruct the payload from a stored row.

    For chain verification, only the canonical JSON matters — it's what was
    hashed. We deserialize the stored ``payload_json`` back into the dataclass
    so callers can inspect it.
    """
    d = json.loads(r.payload_json)
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


def verify_full_chain(session: Session) -> bool:
    """Verify the entire audit chain from genesis to the current tail."""
    rows = read_chain(session, since_seq=0, limit=10_000_000)
    return verify_chain(rows)
