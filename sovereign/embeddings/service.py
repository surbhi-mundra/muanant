"""Embeddings — embed chunks via the EmbeddingModel protocol.

This package is the bridge between the chunker (Phase 2) and the vector
store (Qdrant). It takes ``Chunk`` objects, calls the ModelGateway's
``EmbeddingModel`` to get vectors, and returns them for storage.
"""

from __future__ import annotations

from sovereign.core.logging import get_logger
from sovereign.models.gateway import ModelGateway, get_model_gateway
from sovereign.models.schemas import EmbeddingRequest, EmbeddingResponse
from sovereign.parsing.chunking import Chunk

log = get_logger(__name__)


class EmbeddingService:
    """Embeds chunks using the ModelGateway's EmbeddingModel.

    In dev, this uses the MockEmbeddingModel (hash-based, deterministic).
    In prod, swap to sentence-transformers or TEI via configs/models.yaml.
    """

    def __init__(self, gateway: ModelGateway | None = None) -> None:
        self._gateway = gateway

    @property
    def gateway(self) -> ModelGateway:
        if self._gateway is None:
            self._gateway = get_model_gateway()
        return self._gateway

    @property
    def dim(self) -> int:
        """Return the embedding dimensionality."""
        return self.gateway.embedding.dim

    async def embed_chunks(self, chunks: list[Chunk]) -> list[tuple[Chunk, list[float]]]:
        """Embed a list of chunks. Returns (chunk, vector) pairs.

        Embeds in batches to avoid overwhelming the model. The batch size
        is controlled by the EmbeddingRequest's ``batch_size`` field.
        """
        if not chunks:
            return []

        texts = [c.text for c in chunks]
        log.info("embedding.embed_chunks", count=len(chunks), dim=self.dim)

        resp: EmbeddingResponse = await self.gateway.embedding.embed(
            EmbeddingRequest(texts=texts)
        )

        if len(resp.vectors) != len(chunks):
            msg = (
                f"embedding count mismatch: requested {len(chunks)} "
                f"got {len(resp.vectors)}"
            )
            raise RuntimeError(msg)

        return list(zip(chunks, resp.vectors, strict=True))

    async def embed_query(self, query: str) -> list[float]:
        """Embed a single search query. Returns the vector."""
        resp = await self.gateway.embedding.embed(
            EmbeddingRequest(texts=[query])
        )
        return resp.vectors[0]
