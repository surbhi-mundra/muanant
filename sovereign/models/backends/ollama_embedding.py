"""Ollama embedding adapter — real local embeddings via Ollama.

Pull embedding model:
    ollama pull nomic-embed-text

Satisfies the EmbeddingModel protocol.
"""

from __future__ import annotations

import httpx

from sovereign.core.logging import get_logger
from sovereign.models.schemas import EmbeddingRequest, EmbeddingResponse

log = get_logger(__name__)


class OllamaEmbeddingModel:
    """Real embedding model via Ollama."""

    def __init__(
        self,
        model_name: str = "nomic-embed-text",
        server_url: str = "http://127.0.0.1:11434",
        dim: int = 768,
    ) -> None:
        self._model_name = model_name
        self._server_url = server_url.rstrip("/")
        self._dim = dim

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dim(self) -> int:
        return self._dim

    async def embed(self, req: EmbeddingRequest) -> EmbeddingResponse:
        """Call Ollama's /api/embeddings endpoint."""
        model = req.model or self._model_name
        vectors: list[list[float]] = []

        async with httpx.AsyncClient(timeout=60.0) as client:
            for text in req.texts:
                try:
                    resp = await client.post(
                        f"{self._server_url}/api/embeddings",
                        json={"model": model, "prompt": text},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    vec = data.get("embedding", [])
                    vectors.append(vec)
                except Exception as e:
                    log.error("ollama.embed.failed", error=str(e))
                    vectors.append([0.0] * self._dim)

        actual_dim = len(vectors[0]) if vectors else self._dim
        return EmbeddingResponse(vectors=vectors, dim=actual_dim, model=model)
