"""Tests for sovereign.core.config."""

from __future__ import annotations

import pytest

from sovereign.core.config import Settings, get_settings, reset_settings_cache


@pytest.fixture(autouse=True)
def _reset_settings():
    """Each test gets a fresh settings cache."""
    reset_settings_cache()
    yield
    reset_settings_cache()


def test_defaults_are_safe_for_dev() -> None:
    """Default settings must boot in dev without any env vars."""
    # Construct directly with _env_file=None so the project's .env doesn't
    # leak into this test.
    s = Settings(_env_file=None)
    assert s.env == "dev"
    assert s.log_level == "INFO"
    assert s.egress_enabled is False  # CRITICAL: egress off by default
    assert s.jwt_secret.get_secret_value()  # has *something*, even if weak
    assert s.is_dev is True
    assert s.is_prod is False


def test_env_overrides_yaml_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Env vars must beat YAML defaults."""
    monkeypatch.setenv("SOVEREIGN_ENV", "dev")
    monkeypatch.setenv("EGRESS_ENABLED", "true")
    # Construct with _env_file=None so .env doesn't interfere.
    s = Settings(_env_file=None)
    assert s.egress_enabled is True


def test_jwt_secret_is_secretstr() -> None:
    """JWT secret must be SecretStr — never accidentally logged as plain str."""
    s = Settings(jwt_secret="abc123", _env_file=None)
    assert s.jwt_secret.get_secret_value() == "abc123"
    # repr should not leak the value
    assert "abc123" not in repr(s)


def test_dev_yaml_overrides_class_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """configs/dev.yaml should be applied as defaults (above class defaults).

    To test YAML in isolation, disable .env and env vars so only the YAML
    source can provide values.
    """
    monkeypatch.setenv("SOVEREIGN_ENV", "dev")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    # _env_file=None disables .env loading; env_settings still runs but we
    # deleted DATABASE_URL so it won't override yaml.
    s = Settings(_env_file=None)
    assert "sqlite" in s.database_url  # from dev.yaml
    assert s.log_format == "console"  # dev.yaml sets this


def test_prod_yaml_loaded_when_env_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    """When SOVEREIGN_ENV=prod, prod.yaml is the YAML source."""
    monkeypatch.setenv("SOVEREIGN_ENV", "prod")
    s = Settings(_env_file=None)
    assert s.env == "prod"
    assert s.log_format == "json"  # prod.yaml sets this


def test_unknown_env_falls_back_to_no_yaml(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unknown env name → no matching YAML file → class defaults apply.

    The env field still accepts the value via AliasChoices.
    """
    monkeypatch.setenv("SOVEREIGN_ENV", "staging")
    s = Settings(_env_file=None)
    assert s.env == "staging"
    # No staging.yaml exists, so log_format falls back to class default "json"
    assert s.log_format == "json"


def test_sovereign_env_alias_works(monkeypatch: pytest.MonkeyPatch) -> None:
    """SOVEREIGN_ENV env var should populate the `env` field via AliasChoices."""
    monkeypatch.setenv("SOVEREIGN_ENV", "prod")
    monkeypatch.delenv("ENV", raising=False)
    s = Settings(_env_file=None)
    assert s.env == "prod"


def test_get_settings_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_settings() should return the same instance until cache is reset."""
    monkeypatch.setenv("SOVEREIGN_ENV", "dev")
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
    reset_settings_cache()
    s3 = get_settings()
    assert s3 is not s1
