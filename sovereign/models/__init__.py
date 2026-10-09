"""ModelGateway — the model-agnosticism guarantee.

This package defines the *protocol interfaces* every model backend must
implement, plus a registry/factory that picks the right adapter based on
``configs/models.yaml``.

The dev sandbox uses ``MockBackend`` (recorded fixtures, zero ML deps, runs
on CPU). GPU tiers use real adapters (vLLM, Ollama, sentence-transformers,
Tesseract, Surya, etc.) — but agents and capabilities never import those
adapters directly. They depend only on the protocols below.

See ``adrs/0002-model-gateway-abstraction.md`` for the rationale.
"""
