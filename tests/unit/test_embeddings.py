"""Tests for sovereign.embeddings — EmbeddingService + indexing."""

from __future__ import annotations

import pytest

from sovereign.embeddings.indexing import (
    IndexingService,
    reset_indexing_service,
)
from sovereign.embeddings.service import EmbeddingService
from sovereign.models.gateway import reset_model_gateway
from sovereign.parsing.chunking import Chunk
from sovereign.parsing.model import Block, DocumentMetadata, Page, ParsedDocument
from sovereign.storage.qdrant import reset_qdrant_store


@pytest.fixture(autouse=True)
def _reset_all():
    reset_model_gateway()
    reset_qdrant_store()
    reset_indexing_service()
    yield
    reset_model_gateway()
    reset_qdrant_store()
    reset_indexing_service()


# ---------------------------------------------------------------------------
# EmbeddingService
# ---------------------------------------------------------------------------
class TestEmbeddingService:
    async def test_embed_chunks_returns_vectors(self) -> None:
        """Embedding chunks should return (chunk, vector) pairs."""
        service = EmbeddingService()
        chunks = [
            Chunk(chunk_id="c1", document_id="d1", project_id="p1", text="hello world"),
            Chunk(chunk_id="c2", document_id="d1", project_id="p1", text="another chunk"),
        ]
        result = await service.embed_chunks(chunks)
        assert len(result) == 2
        assert result[0][0].chunk_id == "c1"
        assert len(result[0][1]) == service.dim
        assert len(result[1][1]) == service.dim

    async def test_embed_chunks_empty_list(self) -> None:
        """Empty chunk list should return empty."""
        service = EmbeddingService()
        result = await service.embed_chunks([])
        assert result == []

    async def test_embed_query_returns_vector(self) -> None:
        """embed_query should return a single vector."""
        service = EmbeddingService()
        vec = await service.embed_query("test query")
        assert len(vec) == service.dim

    async def test_embedded_vectors_are_deterministic(self) -> None:
        """Same text → same vector (mock backend uses hash)."""
        service = EmbeddingService()
        chunks = [
            Chunk(chunk_id="c1", document_id="d1", project_id="p1", text="deterministic text")
        ]
        r1 = await service.embed_chunks(chunks)
        r2 = await service.embed_chunks(chunks)
        assert r1[0][1] == r2[0][1]

    def test_dim_property(self) -> None:
        """dim should return the embedding dimensionality."""
        service = EmbeddingService()
        assert service.dim > 0


# ---------------------------------------------------------------------------
# IndexingService
# ---------------------------------------------------------------------------
def _make_parsed_doc(doc_id: str = "doc_test", project_id: str = "proj_test") -> ParsedDocument:
    """Build a minimal ParsedDocument for indexing tests."""
    return ParsedDocument(
        document_id=doc_id,
        project_id=project_id,
        source_filename="test.txt",
        source_mime_type="text/plain",
        pages=[
            Page(
                page_number=1,
                blocks=[
                    Block(kind="heading", text="Introduction", level=1),
                    Block(
                        kind="paragraph",
                        text="This is a test paragraph about pump maintenance procedures.",
                    ),
                    Block(kind="heading", text="Safety", level=1),
                    Block(
                        kind="paragraph",
                        text="Always wear protective equipment when inspecting pumps.",
                    ),
                ],
            )
        ],
        metadata=DocumentMetadata(page_count=1),
    )


class TestIndexingService:
    async def test_index_document_creates_chunks(self) -> None:
        """Indexing should produce chunks and store them."""
        service = IndexingService()
        parsed = _make_parsed_doc()
        result = await service.index_document("proj_test", "doc_test", parsed)
        assert result.status == "indexed"
        assert result.chunk_count > 0
        assert result.vector_count > 0

    async def test_index_document_populates_keyword_index(self) -> None:
        """After indexing, the keyword index should have entries."""
        service = IndexingService()
        parsed = _make_parsed_doc()
        await service.index_document("proj_test", "doc_test", parsed)
        kw_index = service.get_keyword_index("proj_test")
        assert kw_index.size > 0

    async def test_index_document_populates_vector_store(self) -> None:
        """After indexing, the vector store should have points."""
        service = IndexingService()
        parsed = _make_parsed_doc()
        await service.index_document("proj_test", "doc_test", parsed)
        stats = service.get_stats("proj_test")
        assert stats["vector_count"] > 0

    async def test_remove_document_clears_indexes(self) -> None:
        """Removing a document should clear it from both indexes."""
        service = IndexingService()
        parsed = _make_parsed_doc()
        await service.index_document("proj_test", "doc_test", parsed)
        assert service.get_stats("proj_test")["vector_count"] > 0

        service.remove_document("proj_test", "doc_test")
        service.get_stats("proj_test")
        # Keyword index should be empty
        assert service.get_keyword_index("proj_test").size == 0

    async def test_reindex_document_replaces_chunks(self) -> None:
        """Re-indexing should replace, not duplicate, chunks."""
        service = IndexingService()
        parsed = _make_parsed_doc()
        await service.index_document("proj_test", "doc_test", parsed)
        size1 = service.get_keyword_index("proj_test").size

        # Index again
        await service.index_document("proj_test", "doc_test", parsed)
        size2 = service.get_keyword_index("proj_test").size

        assert size1 == size2  # no duplication

    async def test_get_stats_returns_counts(self) -> None:
        """get_stats should return keyword and vector counts."""
        service = IndexingService()
        stats = service.get_stats("proj_test")
        assert "keyword_index_size" in stats
        assert "vector_count" in stats

    async def test_index_empty_document(self) -> None:
        """Indexing a document with no content should succeed with 0 chunks."""
        service = IndexingService()
        parsed = ParsedDocument(
            document_id="doc_empty",
            project_id="proj_test",
            source_filename="empty.txt",
            source_mime_type="text/plain",
            pages=[Page(page_number=1, blocks=[])],
            metadata=DocumentMetadata(page_count=1),
        )
        result = await service.index_document("proj_test", "doc_empty", parsed)
        assert result.status == "indexed"
        assert result.chunk_count == 0

    async def test_project_isolation_keyword_index(self) -> None:
        """Keyword indexes should be isolated per project."""
        service = IndexingService()
        parsed = _make_parsed_doc(doc_id="doc1", project_id="proj_a")
        await service.index_document("proj_a", "doc1", parsed)

        parsed2 = _make_parsed_doc(doc_id="doc2", project_id="proj_b")
        await service.index_document("proj_b", "doc2", parsed2)

        kw_a = service.get_keyword_index("proj_a")
        kw_b = service.get_keyword_index("proj_b")
        # Both should have chunks, but they're separate indexes
        assert kw_a.size > 0
        assert kw_b.size > 0
        # Searching in A should not return B's chunks
        results = kw_a.search("pump maintenance")
        assert all(r.document_id == "doc1" for r in results)
