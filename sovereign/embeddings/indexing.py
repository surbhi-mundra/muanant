"""Indexing service — the bridge between parsing and retrieval.

Takes a ``ParsedDocument``, chunks it, embeds the chunks, and stores
them in:
- Qdrant (vector store) for semantic retrieval
- BM25 keyword index for keyword retrieval

This is the "index" step of the knowledge base. It's called automatically
after ingestion (Phase 2's ``ingest_document``), and can also be called
manually to re-index a document after parser/model changes.

The service manages a per-project BM25 index in memory. On startup,
the index is empty; it gets populated as documents are indexed. For
production with large corpora, the BM25 index would be persisted to
disk and loaded on startup (Phase 14).
"""

from __future__ import annotations

from dataclasses import dataclass

from sovereign.core.logging import get_logger
from sovereign.embeddings.service import EmbeddingService
from sovereign.parsing.chunking import Chunker
from sovereign.parsing.model import ParsedDocument
from sovereign.retrieval.keyword import BM25Index
from sovereign.storage.qdrant import QdrantStore, get_qdrant_store

log = get_logger(__name__)


@dataclass(slots=True)
class IndexResult:
    """Result of indexing a document."""

    document_id: str
    project_id: str
    chunk_count: int
    vector_count: int
    keyword_count: int
    status: str  # "indexed" | "failed"
    error: str | None = None


class IndexingService:
    """Indexes documents into the knowledge base (vectors + keyword index).

    Maintains a per-project BM25 index in memory. The Qdrant store is
    shared (project isolation via collection naming).
    """

    def __init__(
        self,
        qdrant: QdrantStore | None = None,
        embedding_service: EmbeddingService | None = None,
        chunker: Chunker | None = None,
    ) -> None:
        self._qdrant = qdrant
        self._embedding_service = embedding_service
        self._chunker = chunker or Chunker()
        # Per-project keyword indexes
        self._keyword_indexes: dict[str, BM25Index] = {}

    @property
    def qdrant(self) -> QdrantStore:
        if self._qdrant is None:
            self._qdrant = get_qdrant_store()
        return self._qdrant

    @property
    def embedding_service(self) -> EmbeddingService:
        if self._embedding_service is None:
            self._embedding_service = EmbeddingService()
        return self._embedding_service

    def get_keyword_index(self, project_id: str) -> BM25Index:
        """Get (or create) the BM25 keyword index for a project."""
        if project_id not in self._keyword_indexes:
            self._keyword_indexes[project_id] = BM25Index()
        return self._keyword_indexes[project_id]

    async def index_document(
        self,
        project_id: str,
        document_id: str,
        parsed: ParsedDocument,
    ) -> IndexResult:
        """Index a parsed document into the knowledge base.

        1. Chunk the ParsedDocument
        2. Embed the chunks
        3. Ensure the Qdrant collection exists
        4. Upsert vectors + payloads into Qdrant
        5. Add chunks to the BM25 keyword index
        """
        try:
            # Set IDs on the parsed doc if not already set
            if not parsed.document_id:
                parsed.document_id = document_id
            if not parsed.project_id:
                parsed.project_id = project_id

            # 1. Chunk
            chunks = self._chunker.chunk(parsed)
            log.info(
                "index.chunks_created",
                document_id=document_id,
                chunk_count=len(chunks),
            )

            if not chunks:
                return IndexResult(
                    document_id=document_id,
                    project_id=project_id,
                    chunk_count=0,
                    vector_count=0,
                    keyword_count=0,
                    status="indexed",
                )

            # 2. Embed
            chunks_with_vectors = await self.embedding_service.embed_chunks(chunks)

            # 3. Ensure collection exists
            dim = self.embedding_service.dim
            self.qdrant.ensure_collection(project_id, dim)

            # 4. Upsert into Qdrant
            vector_count = self.qdrant.upsert_chunks(project_id, chunks_with_vectors)

            # 5. Add to BM25 keyword index
            keyword_index = self.get_keyword_index(project_id)
            # Remove old chunks for this document first (re-index support)
            keyword_index.remove_document(document_id)
            keyword_index.add_chunks(chunks)
            keyword_count = keyword_index.size

            log.info(
                "index.complete",
                document_id=document_id,
                chunks=len(chunks),
                vectors=vector_count,
                keyword_index_size=keyword_count,
            )

            return IndexResult(
                document_id=document_id,
                project_id=project_id,
                chunk_count=len(chunks),
                vector_count=vector_count,
                keyword_count=keyword_count,
                status="indexed",
            )

        except Exception as e:
            log.error(
                "index.failed",
                document_id=document_id,
                error=str(e),
            )
            return IndexResult(
                document_id=document_id,
                project_id=project_id,
                chunk_count=0,
                vector_count=0,
                keyword_count=0,
                status="failed",
                error=str(e),
            )

    def remove_document(self, project_id: str, document_id: str) -> None:
        """Remove a document from both the vector store and keyword index."""
        # Remove from Qdrant
        self.qdrant.delete_by_document(project_id, document_id)

        # Remove from BM25
        keyword_index = self.get_keyword_index(project_id)
        keyword_index.remove_document(document_id)

        log.info(
            "index.document_removed",
            project_id=project_id,
            document_id=document_id,
        )

    def get_stats(self, project_id: str) -> dict[str, int]:
        """Return knowledge base stats for a project."""
        keyword_index = self.get_keyword_index(project_id)
        return {
            "keyword_index_size": keyword_index.size,
            "vector_count": self.qdrant.count_points(project_id),
        }


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
_service: IndexingService | None = None


def get_indexing_service() -> IndexingService:
    """Return the cached IndexingService singleton."""
    global _service  # noqa: PLW0603
    if _service is None:
        _service = IndexingService()
    return _service


def reset_indexing_service() -> None:
    """Test helper: drop the cached service."""
    global _service  # noqa: PLW0603
    _service = None
