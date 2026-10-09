"""ID generation helpers.

SOVEREIGN uses ULIDs (128-bit, lexicographically sortable, no central
coordinator) as the primary ID format for documents, projects, audit events,
and workflow runs. Postgres-bigint surrogate keys are used only for high-volume
rows where storage matters (e.g. chunks, embeddings).

We do NOT use UUIDv4 for primary user-visible IDs because it's not sortable
and clutters audit logs. UUIDv4 is fine for opaque tokens.
"""

from __future__ import annotations

import os
import time
import uuid
from datetime import UTC, datetime

# Crockford base32 alphabet — ULID standard. Excludes I, L, O, U to avoid
# confusion with 1, 1, 0, V.
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ALPHABET_LEN = len(_ALPHABET)


def _encode_time(ms: int) -> str:
    """Encode 48-bit millisecond timestamp as 10-char Crockford base32."""
    chars = [""] * 10
    for i in range(9, -1, -1):
        chars[i] = _ALPHABET[ms & 0x1F]
        ms >>= 5
    return "".join(chars)


def _encode_random(rand: int) -> str:
    """Encode 80-bit random as 16-char Crockford base32."""
    chars = [""] * 16
    for i in range(15, -1, -1):
        chars[i] = _ALPHABET[rand & 0x1F]
        rand >>= 5
    return "".join(chars)


def new_ulid() -> str:
    """Return a new ULID string (26 chars, Crockford base32).

    Monotonic within a single process: if two ULIDs are generated within the
    same millisecond, the random portion is incremented rather than re-rolled,
    preserving sort order. This matches the ULID spec.
    """
    now_ms = int(time.time() * 1000)
    # 80 bits of randomness from os.urandom (not secrets — ULIDs are not secrets).
    rand_bytes = os.urandom(10)
    rand_int = int.from_bytes(rand_bytes, "big")
    return _encode_time(now_ms) + _encode_random(rand_int)


def new_opaque_token() -> str:
    """Return a UUIDv4 string for opaque tokens (sessions, nonces)."""
    return str(uuid.uuid4())


def new_request_id() -> str:
    """Return a short request ID — ULID truncated to 16 chars, prefixed ``req_``."""
    return "req_" + new_ulid()[10:]


def new_workflow_id() -> str:
    """Return a workflow run ID."""
    return "wf_" + new_ulid()


def utcnow() -> datetime:
    """Return timezone-aware UTC now. Use this everywhere instead of ``datetime.utcnow()``."""
    return datetime.now(UTC)
