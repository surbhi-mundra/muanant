"""Backend registry.

Each real backend module (vllm, ollama, sentence_transformers, tesseract, ...)
registers itself here via ``register_backend(name, factory)``. The
``ModelGateway`` looks up backends by name from ``configs/models.yaml``.

Phase 1 only ships the mock backend. Real backends are added in later phases
as the relevant subsystems need them. They register themselves on import,
and the gateway imports them lazily based on what's in the config file.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

# A backend factory takes a config dict and returns the backend instance.
BackendFactory = Callable[[dict[str, Any]], Any]


class BackendType(Protocol):
    name: str
    capabilities: tuple[str, ...]  # e.g. ("text", "vision")


_REGISTRY: dict[str, BackendFactory] = {}


def register_backend(name: str, factory: BackendFactory) -> None:
    """Register a backend factory under ``name``.

    Idempotent: re-registering the same name overwrites the previous factory.
    This is intentional — it lets test setups swap a backend without monkey-
    patching.
    """
    _REGISTRY[name] = factory


def get_backend(name: str) -> BackendFactory:
    """Look up a registered backend factory by name."""
    if name not in _REGISTRY:
        msg = (
            f"unknown model backend '{name}'. "
            f"Registered: {sorted(_REGISTRY)}"
        )
        raise KeyError(msg)
    return _REGISTRY[name]


def registered_backends() -> list[str]:
    return sorted(_REGISTRY)


# ---------------------------------------------------------------------------
# Built-in backends
# ---------------------------------------------------------------------------
# Mock backend is always available — it has no external deps and is the
# default for the dev sandbox / CI. The import is below the registry
# definition so the registry helpers are visible to readers first.
from sovereign.models.backends.mock import (  # noqa: E402
    MockEmbeddingModel,
    MockOCR,
    MockReranker,
    MockTextLLM,
    MockVisionLLM,
)


def _mock_text(cfg: dict[str, Any]) -> MockTextLLM:
    return MockTextLLM(model_name=cfg.get("model_name", "mock-text-llm"))


def _mock_vision(cfg: dict[str, Any]) -> MockVisionLLM:
    return MockVisionLLM(model_name=cfg.get("model_name", "mock-vision-llm"))


def _mock_embedding(cfg: dict[str, Any]) -> MockEmbeddingModel:
    return MockEmbeddingModel(
        dim=cfg.get("dim", 384), model_name=cfg.get("model_name", "mock-embeddings")
    )


def _mock_reranker(cfg: dict[str, Any]) -> MockReranker:
    return MockReranker(model_name=cfg.get("model_name", "mock-reranker"))


def _mock_ocr(cfg: dict[str, Any]) -> MockOCR:
    return MockOCR(model_name=cfg.get("model_name", "mock-ocr"))


register_backend("mock.text", _mock_text)
register_backend("mock.vision", _mock_vision)
register_backend("mock.embedding", _mock_embedding)
register_backend("mock.reranker", _mock_reranker)
register_backend("mock.ocr", _mock_ocr)


# Real backends register themselves on import — but we do NOT import them
# eagerly here. They're imported lazily by the gateway based on config, so
# that the dev sandbox (which lacks torch/transformers/etc.) can boot.
#
# When a real backend is added in a later phase, it should be added to the
# optional-dependencies list in pyproject.toml AND registered here:
#
#   try:
#       from sovereign.models.backends import vllm as _vllm
#   except ImportError:
#       pass

# Tesseract OCR is CPU-only and the binary is always available, so we
# register it eagerly. The adapter imports pytesseract + PIL, both of
# which are in the core dependencies.
try:
    from sovereign.ocr.tesseract import TesseractOCR

    def _tesseract_ocr(cfg: dict[str, Any]) -> TesseractOCR:
        return TesseractOCR(model_name=cfg.get("model_name", "tesseract-5.x"))

    register_backend("tesseract.ocr", _tesseract_ocr)
except ImportError:
    pass

# Ollama backends (local LLM + embeddings via Ollama — works on Mac/Linux/Windows)
# Ollama only needs httpx (already a core dep), so we register eagerly.
try:
    from sovereign.models.backends.ollama import OllamaTextLLM
    from sovereign.models.backends.ollama_embedding import OllamaEmbeddingModel

    def _ollama_text(cfg: dict[str, Any]) -> OllamaTextLLM:
        return OllamaTextLLM(
            model_name=cfg.get("model_name", "qwen2.5:7b-instruct"),
            server_url=cfg.get("server_url", "http://127.0.0.1:11434"),
        )

    def _ollama_embedding(cfg: dict[str, Any]) -> OllamaEmbeddingModel:
        return OllamaEmbeddingModel(
            model_name=cfg.get("model_name", "nomic-embed-text"),
            server_url=cfg.get("server_url", "http://127.0.0.1:11434"),
            dim=cfg.get("dim", 768),
        )

    register_backend("ollama.text", _ollama_text)
    register_backend("ollama.embedding", _ollama_embedding)
except ImportError:
    pass
