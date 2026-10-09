"""ModelGateway — the single entry point for all model calls in SOVEREIGN.

Loads ``configs/models.yaml`` once at startup, instantiates the configured
backends, and exposes them through the 5 protocol interfaces
(``TextLLM``, ``VisionLLM``, ``EmbeddingModel``, ``Reranker``, ``OCR``).

Every agent and capability in SOVEREIGN depends on ``ModelGateway``, never
on a concrete adapter. This is the architectural guarantee that makes the
system model-agnostic — see ``adrs/0002-model-gateway-abstraction.md``.

Config schema (``configs/models.yaml``)::

    text:
      backend: mock.text              # or vllm.text, ollama.text, ...
      model_name: mock-text-llm       # forwarded to the backend factory
      # ...any backend-specific options...
    vision:
      backend: mock.vision
      model_name: mock-vision-llm
    embedding:
      backend: mock.embedding
      model_name: mock-embeddings
      dim: 384
    reranker:
      backend: mock.reranker
      model_name: mock-reranker
    ocr:
      backend: mock.ocr
      model_name: mock-ocr
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from sovereign.core.config import Settings
from sovereign.core.errors import ConfigError, ModelUnavailableError
from sovereign.models.backends import get_backend, registered_backends
from sovereign.models.schemas import (
    OCR,
    EmbeddingModel,
    Reranker,
    TextLLM,
    VisionLLM,
)


@dataclass(slots=True)
class GatewayConfig:
    text: dict[str, Any]
    vision: dict[str, Any]
    embedding: dict[str, Any]
    reranker: dict[str, Any]
    ocr: dict[str, Any]


class ModelGateway:
    """The model-agnosticism guarantee.

    Construct once at app startup (FastAPI dependency) and reuse. Holds
    references to the 5 instantiated backends. All agent/capability code
    receives this object via DI and asks for the capability it needs.
    """

    def __init__(self, cfg: GatewayConfig) -> None:
        self._cfg = cfg
        self._text: TextLLM | None = None
        self._vision: VisionLLM | None = None
        self._embedding: EmbeddingModel | None = None
        self._reranker: Reranker | None = None
        self._ocr: OCR | None = None

    # --- Lazy accessors (each backend is created on first use) ---
    @property
    def text(self) -> TextLLM:
        if self._text is None:
            self._text = self._build("text", TextLLM)
        return self._text

    @property
    def vision(self) -> VisionLLM:
        if self._vision is None:
            self._vision = self._build("vision", VisionLLM)
        return self._vision

    @property
    def embedding(self) -> EmbeddingModel:
        if self._embedding is None:
            self._embedding = self._build("embedding", EmbeddingModel)
        return self._embedding

    @property
    def reranker(self) -> Reranker:
        if self._reranker is None:
            self._reranker = self._build("reranker", Reranker)
        return self._reranker

    @property
    def ocr(self) -> OCR:
        if self._ocr is None:
            self._ocr = self._build("ocr", OCR)
        return self._ocr

    def _build(self, capability: str, protocol: type[Any]) -> Any:
        cfg = getattr(self._cfg, capability)
        backend_name = cfg.get("backend")
        if not backend_name:
            msg = f"models.yaml: capability '{capability}' missing 'backend' key"
            raise ConfigError(msg)
        try:
            factory = get_backend(backend_name)
        except KeyError as e:
            msg = (
                f"models.yaml: backend '{backend_name}' for capability "
                f"'{capability}' is not registered. Available: {registered_backends()}"
            )
            raise ModelUnavailableError(msg) from e

        instance = factory(cfg)
        # Runtime check that the backend actually satisfies the protocol.
        if not isinstance(instance, protocol):
            msg = (
                f"backend '{backend_name}' for capability '{capability}' does "
                f"not implement {protocol.__name__}"
            )
            raise ConfigError(msg)
        return instance

    # --- Health ---
    def describe(self) -> dict[str, str]:
        """Return the configured backend name for each capability.

        Used by ``/readyz`` for startup checks.
        """
        return {
            "text": self._cfg.text.get("backend", "?"),
            "vision": self._cfg.vision.get("backend", "?"),
            "embedding": self._cfg.embedding.get("backend", "?"),
            "reranker": self._cfg.reranker.get("backend", "?"),
            "ocr": self._cfg.ocr.get("backend", "?"),
        }


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------
def _load_gateway_config(path: Path) -> GatewayConfig:
    if not path.exists():
        msg = f"ModelGateway config not found: {path}"
        raise ConfigError(msg)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"{path}: expected a YAML mapping"
        raise ConfigError(msg)

    required = {"text", "vision", "embedding", "reranker", "ocr"}
    missing = required - raw.keys()
    if missing:
        msg = f"{path}: missing capabilities: {sorted(missing)}"
        raise ConfigError(msg)

    return GatewayConfig(
        text=raw["text"],
        vision=raw["vision"],
        embedding=raw["embedding"],
        reranker=raw["reranker"],
        ocr=raw["ocr"],
    )


_gateway: ModelGateway | None = None


def get_model_gateway(settings: Settings | None = None) -> ModelGateway:
    """Return the cached ModelGateway singleton.

    Constructs one on first call using the path from settings. Subsequent
    calls return the same instance. Tests can call ``reset_model_gateway()``
    to force re-construction.
    """
    global _gateway  # noqa: PLW0603 — singleton pattern, intentional
    if _gateway is None:
        if settings is None:
            from sovereign.core.config import get_settings  # noqa: PLC0415

            settings = get_settings()
        cfg = _load_gateway_config(settings.model_gateway_config)
        _gateway = ModelGateway(cfg)
    return _gateway


def reset_model_gateway() -> None:
    """Test helper: drop the cached gateway."""
    global _gateway  # noqa: PLW0603 — singleton pattern, intentional
    _gateway = None
