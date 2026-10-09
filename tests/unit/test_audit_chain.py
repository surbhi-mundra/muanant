"""Tests for sovereign.audit — append-only, hash-chained log."""

from __future__ import annotations

import pytest

from sovereign.audit.chain import (
    GENESIS_HASH,
    AuditEventPayload,
    compute_hash,
)
from sovereign.audit.log import read_chain, verify_full_chain, write_event
from sovereign.storage.db.base import init_schema, reset_engine, session_scope


@pytest.fixture(autouse=True)
def _fresh_db(monkeypatch: pytest.MonkeyPatch):
    """Each test gets a fresh in-memory SQLite DB.

    Must reset the settings cache so the new DATABASE_URL env var is read
    on the next ``get_settings()`` call.
    """
    from sovereign.core.config import reset_settings_cache  # noqa: PLC0415

    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    reset_settings_cache()
    reset_engine()
    init_schema()
    yield
    reset_engine()
    reset_settings_cache()


def _payload(action: str = "test.action", **kw) -> AuditEventPayload:
    return AuditEventPayload(
        category="test",
        action=action,
        outcome="success",
        user_id="user_1",
        **kw,
    )


def test_compute_hash_is_deterministic() -> None:
    """Same input must produce the same hash."""
    p = _payload("a")
    h1 = compute_hash(GENESIS_HASH, p)
    h2 = compute_hash(GENESIS_HASH, p)
    assert h1 == h2


def test_compute_hash_changes_on_payload_change() -> None:
    """Different payload → different hash."""
    p1 = _payload("a")
    p2 = _payload("b")
    assert compute_hash(GENESIS_HASH, p1) != compute_hash(GENESIS_HASH, p2)


def test_compute_hash_changes_on_prev_hash_change() -> None:
    """Different prev_hash → different hash."""
    p = _payload("a")
    assert compute_hash(GENESIS_HASH, p) != compute_hash("abcdef", p)


def test_first_event_uses_genesis_prev_hash() -> None:
    """The first event in the chain must have prev_hash == 'genesis'."""
    with session_scope() as s:
        row = write_event(s, _payload("first"))
    assert row.prev_hash == GENESIS_HASH
    assert row.sequence == 1


def test_chain_links_correctly() -> None:
    """Each event's prev_hash must equal the previous event's hash."""
    with session_scope() as s:
        r1 = write_event(s, _payload("a"))
        r2 = write_event(s, _payload("b"))
        r3 = write_event(s, _payload("c"))
    assert r2.prev_hash == r1.hash
    assert r3.prev_hash == r2.hash
    assert r1.sequence == 1
    assert r2.sequence == 2
    assert r3.sequence == 3


def test_verify_full_chain_returns_true_for_unmodified_chain() -> None:
    """A fresh, untampered chain must verify."""
    with session_scope() as s:
        for i in range(5):
            write_event(s, _payload(f"action.{i}"))
    with session_scope() as s:
        assert verify_full_chain(s) is True


def test_verify_chain_detects_tampering() -> None:
    """Modifying a payload mid-chain must break verification."""
    with session_scope() as s:
        for i in range(5):
            write_event(s, _payload(f"action.{i}"))

    # Tamper: rewrite the payload_json of the middle row without updating the hash.
    from sqlalchemy import text  # noqa: PLC0415

    with session_scope() as s:
        s.execute(
            text("UPDATE audit_events SET payload_json = :p WHERE sequence = 3"),
            {"p": '{"action":"tampered"}'},
        )

    with session_scope() as s:
        assert verify_full_chain(s) is False


def test_read_chain_returns_ordered_rows() -> None:
    """read_chain must return rows in ascending sequence order."""
    with session_scope() as s:
        for i in range(3):
            write_event(s, _payload(f"action.{i}"))
    with session_scope() as s:
        rows = read_chain(s, since_seq=0, limit=100)
    assert len(rows) == 3
    assert [r[0] for r in rows] == [1, 2, 3]


def test_payload_canonical_json_stable_across_field_addition() -> None:
    """Adding a new optional field to AuditEventPayload must not change the
    hash of events that don't populate it (None values are dropped)."""
    p1 = AuditEventPayload(category="test", action="a")
    # Simulate a future version of the dataclass with an extra field —
    # since None values are dropped, the canonical_json is identical.
    d = p1.canonical_json()
    assert "duration_ms" not in d  # not in payload because it's None
    assert "model" not in d


def test_payload_drops_none_values() -> None:
    """None values must not appear in the canonical JSON."""
    p = AuditEventPayload(category="test", action="a", user_id=None, model=None)
    cj = p.canonical_json()
    assert "user_id" not in cj
    assert "model" not in cj
