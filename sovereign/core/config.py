"""Typed configuration for SOVEREIGN.

Single source of truth for runtime configuration. Loaded from (lowest to
highest priority):

1. ``Settings`` class field defaults
2. ``configs/<env>.yaml`` (default values per environment)
3. ``.env`` file
4. Environment variables

NEVER hard-code secrets, paths, or model names anywhere else. If you need a new
setting, add it here, document it in ``.env.example``, and add a test in
``tests/unit/test_config.py``.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIGS_DIR = PROJECT_ROOT / "configs"


def _active_env() -> str:
    """Return the active environment name (dev/staging/prod).

    Read directly from env to break the chicken-and-egg: we need the env
    name to know which YAML file to load, but the env name itself is a
    Settings field.
    """
    return os.environ.get("SOVEREIGN_ENV") or os.environ.get("ENV") or "dev"


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
class Settings(BaseSettings):
    """SOVEREIGN runtime settings.

    All fields have safe dev defaults. Prod values come from env / ``.env``.
    The YAML file (``configs/<env>.yaml``) provides environment-specific
    defaults that sit BETWEEN the class defaults and env vars.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Runtime ---
    # Accept SOVEREIGN_ENV, ENV, or the bare field name 'env' from any source.
    env: Literal["dev", "staging", "prod"] = Field(
        default="dev",
        validation_alias=AliasChoices("SOVEREIGN_ENV", "ENV", "env"),
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    log_format: Literal["json", "console"] = Field(default="json")

    # --- Database (MongoDB) ---
    database_url: str = Field(default="mongodb://localhost:27017/sovereign")

    # --- Vector store ---
    qdrant_url: str = Field(default="")
    qdrant_api_key: SecretStr = SecretStr("")

    # --- Object storage ---
    object_store_type: Literal["fs", "s3"] = Field(default="fs")
    object_store_fs_root: Path = Field(default=Path("./storage/objects"))

    # --- Auth ---
    jwt_secret: SecretStr = Field(default=SecretStr("dev-only-not-for-prod"))
    jwt_alg: str = Field(default="HS256")
    jwt_ttl_minutes: int = Field(default=60)

    # --- Network egress ---
    egress_enabled: bool = Field(default=False)
    egress_allowlist_path: Path = Field(default=CONFIGS_DIR / "policies.yaml")

    # --- Model Gateway ---
    model_gateway_config: Path = Field(default=CONFIGS_DIR / "models.yaml")

    # --- App server ---
    sovereign_host: str = Field(default="127.0.0.1")
    sovereign_port: int = Field(default=8000)

    # --- Validators ---
    @field_validator("object_store_fs_root", "egress_allowlist_path", "model_gateway_config")
    @classmethod
    def _expand_paths(cls, v: Path) -> Path:
        return v.expanduser().resolve() if v.is_absolute() else v

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Order sources highest-priority first.

        Env vars > .env file > YAML defaults > init kwargs > class defaults.
        """
        env_name = _active_env()
        yaml_path = CONFIGS_DIR / f"{env_name}.yaml"
        yaml_source = YamlConfigSettingsSource(settings_cls, yaml_path)
        # Highest priority first.
        return (
            env_settings,
            dotenv_settings,
            yaml_source,
            init_settings,
            file_secret_settings,
        )


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings instance.

    Source priority (highest first): env vars > .env file > YAML defaults >
    class defaults. The YAML file is selected by ``SOVEREIGN_ENV`` (or
    ``ENV`` or the ``env`` field's class default).

    Does NOT mutate os.environ — the ``env`` field's ``AliasChoices`` lets
    pydantic-settings read ``SOVEREIGN_ENV`` directly.
    """
    return Settings()


def reset_settings_cache() -> None:
    """Test helper: clear the lru_cache so the next ``get_settings()`` re-reads env."""
    get_settings.cache_clear()
