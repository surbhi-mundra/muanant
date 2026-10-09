"""Tests for sovereign.core.logging redaction."""

from __future__ import annotations

import io
import logging

import pytest

from sovereign.core.config import Settings
from sovereign.core.logging import configure_logging, get_logger, redactor


def _setup_capture() -> io.StringIO:
    """Capture structlog output to a StringIO for assertions."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.DEBUG)
    return stream


def test_redactor_scrubs_known_secret_keys() -> None:
    """Keys in _REDACT_KEYS must be replaced with ***REDACTED***."""
    event_dict = {
        "event": "test",
        "password": "hunter2",
        "api_key": "sk-abc123",
        "token": "Bearer xyz",
        "ok_field": "fine",
    }
    out = redactor(None, "info", event_dict)
    assert out["password"] == "***REDACTED***"
    assert out["api_key"] == "***REDACTED***"
    assert out["token"] == "***REDACTED***"
    assert out["ok_field"] == "fine"


def test_redactor_scrubs_nested_dicts() -> None:
    """Redaction must descend into nested dicts and lists."""
    event_dict = {
        "event": "test",
        "headers": {
            "Authorization": "Bearer s3cr3t",
            "Content-Type": "application/json",
        },
        "rows": [
            {"password": "p1"},
            {"name": "alice"},
        ],
    }
    out = redactor(None, "info", event_dict)
    assert out["headers"]["Authorization"] == "***REDACTED***"
    assert out["headers"]["Content-Type"] == "application/json"
    assert out["rows"][0]["password"] == "***REDACTED***"
    assert out["rows"][1]["name"] == "alice"


def test_redactor_masks_postgres_url_passwords() -> None:
    """postgres://user:pass@host must have the password masked."""
    event_dict = {
        "event": "db.connect",
        "url": "postgresql://sovereign:supersecret@db:5432/sovereign",
    }
    out = redactor(None, "info", event_dict)
    assert "supersecret" not in out["url"]
    assert "***" in out["url"]


def test_redactor_masks_bearer_tokens() -> None:
    """Bearer token values must be masked when the key is not in _REDACT_KEYS.

    Note: the `authorization` key is in _REDACT_KEYS and gets FULL redaction
    (safer — don't even leak that it's a Bearer token). For other keys that
    happen to contain a Bearer token, only the token part is masked.
    """
    event_dict = {
        "event": "http.request",
        # 'authorization' triggers full redaction (key in _REDACT_KEYS)
        "authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig",
        # 'header_value' is not a known-secret key, so pattern-masking applies
        "header_value": "Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig",
    }
    out = redactor(None, "info", event_dict)
    # authorization key → full redaction
    assert out["authorization"] == "***REDACTED***"
    # non-secret key → pattern-masking, "Bearer" kept, token replaced
    assert "Bearer" in out["header_value"]
    assert "eyJhbGciOiJIUzI1NiJ9.payload.sig" not in out["header_value"]
    assert "***" in out["header_value"]


def test_logger_emits_redacted_output(capsys: pytest.CaptureFixture[str]) -> None:
    """End-to-end: a log call with a secret key must not leak the value."""
    settings = Settings(env="dev", log_format="json")
    configure_logging(settings)

    log = get_logger("test")
    log.info("test.event", password="hunter2", api_key="sk-live-12345")
    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert "hunter2" not in output
    assert "sk-live-12345" not in output
    assert "***REDACTED***" in output
