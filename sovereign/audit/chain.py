"""Hash-chain primitives for the audit log.

Separated from ``log.py`` so the chain can be verified independently of the
write path. ``scripts/verify_audit_chain.py`` imports from here.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

GENESIS_HASH = "genesis"


@dataclass(slots=True)
class AuditEventPayload:
    """Structured payload. Restricted types — no opaque blobs.

    This is the canonical schema for an audit event payload. The hash is
    computed over ``canonical_json(payload)`` so byte-identical payloads
    produce identical hashes (deterministic ordering, no whitespace).
    """

    # Actor context
    user_id: str | None = None
    project_id: str | None = None
    request_id: str | None = None
    workflow_id: str | None = None
    agent: str | None = None  # which agent, if any

    # Event taxonomy
    category: str = ""        # auth | ingestion | retrieval | agent | approval | security | egress
    action: str = ""          # e.g. "document.ingest", "rag.query", "approval.grant"
    outcome: str = "success"  # success | failure | blocked

    # Freeform-but-typed details. Values must be JSON-serializable primitives
    # (str, int, float, bool, None) or nested dicts/lists of the same.
    # DO NOT put document content here.
    details: dict[str, Any] = field(default_factory=dict)

    # Optional: latency in milliseconds (for perf-sensitive events)
    duration_ms: int | None = None

    # Optional: model + token usage (for agent/LLM events)
    model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None

    def canonical_json(self) -> str:
        """Serialize as canonical JSON: sorted keys, no whitespace, no NaN.

        Datetime fields are NOT in this payload — they're stored separately
        on the AuditEvent row, so we don't need to handle them here.
        """
        d = asdict(self)
        # Drop None values to keep the canonical form stable across versions
        # where new fields are added (a missing field shouldn't change the
        # hash of an older event).
        d = _drop_none(d)
        return json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _drop_none(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _drop_none(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_drop_none(x) for x in obj]
    return obj


def compute_hash(prev_hash: str, payload: AuditEventPayload) -> str:
    """Compute SHA-256 of (prev_hash || canonical_json(payload))."""
    h = hashlib.sha256()
    h.update(prev_hash.encode("utf-8"))
    h.update(b"\n")
    h.update(payload.canonical_json().encode("utf-8"))
    return h.hexdigest()


def verify_chain(rows: list[tuple[int, str, str, AuditEventPayload]]) -> bool:
    """Verify a chain of (sequence, prev_hash, stored_hash, payload) tuples.

    Returns True iff every row's stored_hash equals the recomputed hash of
    (prev_hash, payload) AND every row's prev_hash equals the previous row's
    stored_hash (or ``"genesis"`` for the first row).
    """
    prev = GENESIS_HASH
    for _seq, prev_hash, stored_hash, payload in rows:
        if prev_hash != prev:
            return False
        expected = compute_hash(prev_hash, payload)
        if not _constant_time_eq(expected, stored_hash):
            return False
        prev = stored_hash
    return True


def _constant_time_eq(a: str, b: str) -> bool:
    """Constant-time string comparison to avoid timing-based tampering signals."""
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a, b, strict=True):
        result |= ord(x) ^ ord(y)
    return result == 0
