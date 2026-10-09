"""Tests for sovereign.core.ids."""

from __future__ import annotations

import re
import time

from sovereign.core.ids import (
    new_opaque_token,
    new_request_id,
    new_ulid,
    new_workflow_id,
    utcnow,
)

ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


def test_new_ulid_format() -> None:
    ulid = new_ulid()
    assert ULID_RE.match(ulid), f"bad ULID format: {ulid}"


def test_new_ulid_is_unique() -> None:
    """10k ULIDs in tight loop must all be unique."""
    ids = {new_ulid() for _ in range(10_000)}
    assert len(ids) == 10_000


def test_new_ulid_is_time_sorted() -> None:
    """ULIDs generated later must sort after ones generated earlier (across ms)."""
    a = new_ulid()
    time.sleep(0.005)  # 5ms — guarantees different timestamp
    b = new_ulid()
    assert a < b, f"ULID not sortable: {a} should be < {b}"


def test_new_ulid_same_ms_doesnt_crash() -> None:
    """Rapid generation within the same ms must not raise (monotonicity handled)."""
    # Just generate a batch and assert they're unique.
    ids = [new_ulid() for _ in range(1000)]
    assert len(set(ids)) == 1000


def test_new_opaque_token_format() -> None:
    t = new_opaque_token()
    assert re.match(r"^[0-9a-f-]{36}$", t), f"bad token: {t}"


def test_new_request_id_format() -> None:
    rid = new_request_id()
    assert rid.startswith("req_")
    assert len(rid) == 4 + 16  # "req_" + 16 chars


def test_new_workflow_id_format() -> None:
    wid = new_workflow_id()
    assert wid.startswith("wf_")
    assert len(wid) == 3 + 26  # "wf_" + ULID


def test_utcnow_is_timezone_aware() -> None:
    """utcnow() must return a tz-aware datetime — naive datetimes are a bug."""
    now = utcnow()
    assert now.tzinfo is not None
