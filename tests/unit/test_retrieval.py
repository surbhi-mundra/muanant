"""Tests for sovereign.retrieval — BM25, RRF fusion, hybrid retriever."""

from __future__ import annotations

import pytest

from sovereign.embeddings.indexing import IndexingService, reset_indexing_service
from sovereign.models.gateway import reset_model_gateway
from sovereign.parsing.chunking import Chunk
from sovereign.parsing.model import Block, DocumentMetadata, Page, ParsedDocument
from sovereign.retrieval.fusion import reciprocal_rank_fusion
from sovereign.retrieval.keyword import BM25Index
from sovereign.retrieval.service import HybridRetriever
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
# BM25 Index
# ---------------------------------------------------------------------------
class TestBM25Index:
    def test_add_and_search(self) -> None:
        """Added chunks should be searchable."""
        index = BM25Index()
        chunks = [
            Chunk(
                chunk_id="c1", document_id="d1", project_id="p1",
                text="pump maintenance schedule",
            ),
            Chunk(
                chunk_id="c2", document_id="d1", project_id="p1",
                text="valve inspection procedure",
            ),
            Chunk(chunk_id="c3", document_id="d1", project_id="p1", text="pump operating manual"),
        ]
        index.add_chunks(chunks)
        results = index.search("pump maintenance")
        assert len(results) > 0
        # The chunk about pump maintenance should rank highly
        top = results[0]
        assert "pump" in top.text.lower()

    def test_search_empty_index(self) -> None:
        """Searching an empty index should return no results."""
        index = BM25Index()
        results = index.search("test")
        assert results == []

    def test_search_no_match(self) -> None:
        """Searching with no matching terms should return no results."""
        index = BM25Index()
        index.add_chunks([
            Chunk(chunk_id="c1", document_id="d1", project_id="p1", text="alpha beta gamma"),
        ])
        results = index.search("xyz")
        assert results == []

    def test_remove_document(self) -> None:
        """Removing a document should remove its chunks from the index."""
        index = BM25Index()
        index.add_chunks([
            Chunk(chunk_id="c1", document_id="d1", project_id="p1", text="pump alpha"),
            Chunk(chunk_id="c2", document_id="d2", project_id="p1", text="pump beta"),
        ])
        assert index.size == 2
        removed = index.remove_document("d1")
        assert removed == 1
        assert index.size == 1
        # Search should only return d2's chunk
        results = index.search("pump")
        assert len(results) == 1
        assert results[0].document_id == "d2"

    def test_remove_chunk(self) -> None:
        """Removing a single chunk should work."""
        index = BM25Index()
        index.add_chunks([
            Chunk(chunk_id="c1", document_id="d1", project_id="p1", text="alpha"),
            Chunk(chunk_id="c2", document_id="d1", project_id="p1", text="beta"),
        ])
        index.remove_chunk("c1")
        assert index.size == 1
        results = index.search("alpha")
        assert len(results) == 0

    def test_top_k_limit(self) -> None:
        """search should respect the top_k limit."""
        index = BM25Index()
        index.add_chunks([
            Chunk(chunk_id=f"c{i}", document_id="d1", project_id="p1", text=f"pump variant {i}")
            for i in range(10)
        ])
        results = index.search("pump", top_k=3)
        assert len(results) == 3

    def test_results_have_provenance(self) -> None:
        """Search results should carry page, section_path, chunk_index."""
        index = BM25Index()
        index.add_chunks([
            Chunk(
                chunk_id="c1", document_id="d1", project_id="p1",
                text="pump maintenance", page=5, section_path=["Chapter 1", "Section 2"],
                chunk_index=3, block_kinds=["paragraph"],
            ),
        ])
        results = index.search("pump")
        assert len(results) == 1
        r = results[0]
        assert r.page == 5
        assert r.section_path == ["Chapter 1", "Section 2"]
        assert r.chunk_index == 3

    def test_tokenization_removes_stopwords(self) -> None:
        """Common stopwords should not affect ranking."""
        from sovereign.retrieval.keyword import _tokenize

        tokens = _tokenize("the pump is a maintenance procedure")
        # "the", "is", "a" should be removed
        assert "the" not in tokens
        assert "is" not in tokens
        assert "a" not in tokens
        assert "pump" in tokens
        assert "maintenance" in tokens


# ---------------------------------------------------------------------------
# RRF Fusion
# ---------------------------------------------------------------------------
class TestRRFFusion:
    def test_fuse_two_lists(self) -> None:
        """RRF should combine two ranked lists."""
        fused = reciprocal_rank_fusion({
            "vector": ["a", "b", "c"],
            "keyword": ["b", "c", "d"],
        })
        # "b" and "c" appear in both lists — should rank higher
        ids = [f.item_id for f in fused]
        assert "b" in ids[:2]  # b is rank 1 in keyword, rank 2 in vector
        assert "c" in ids[:3]  # c is in both

    def test_fuse_single_list(self) -> None:
        """RRF with one list should return that list's order."""
        fused = reciprocal_rank_fusion({"vector": ["a", "b", "c"]})
        assert [f.item_id for f in fused] == ["a", "b", "c"]

    def test_fuse_empty_lists(self) -> None:
        """RRF with no lists should return empty."""
        fused = reciprocal_rank_fusion({})
        assert fused == []

    def test_fuse_item_in_one_list_only(self) -> None:
        """Items in only one list should still appear in results."""
        fused = reciprocal_rank_fusion({
            "vector": ["a", "b"],
            "keyword": ["c", "d"],
        })
        ids = {f.item_id for f in fused}
        assert ids == {"a", "b", "c", "d"}

    def test_fuse_scores_are_sorted_descending(self) -> None:
        """Fused results should be sorted by score descending."""
        fused = reciprocal_rank_fusion({
            "vector": ["a", "b", "c"],
            "keyword": ["b", "a", "c"],
        })
        scores = [f.rrf_score for f in fused]
        assert scores == sorted(scores, reverse=True)

    def test_fuse_ranks_included(self) -> None:
        """Each fused result should include per-ranker ranks."""
        fused = reciprocal_rank_fusion({
            "vector": ["a", "b"],
            "keyword": ["b", "a"],
        })
        for f in fused:
            assert "vector" in f.ranks or "keyword" in f.ranks


# ---------------------------------------------------------------------------
# Hybrid Retriever
# ---------------------------------------------------------------------------
class TestHybridRetriever:
    async def test_retrieve_returns_results(self) -> None:
        """Hybrid retrieval should return results for indexed content."""
        # First, index a document
        indexing = IndexingService()
        parsed = ParsedDocument(
            document_id="doc1", project_id="proj_test",
            source_filename="test.txt", source_mime_type="text/plain",
            pages=[Page(page_number=1, blocks=[
                Block(
                    kind="paragraph",
                    text="Pump P-101 requires immediate maintenance due to bearing wear.",
                ),
                Block(
                    kind="paragraph",
                    text="The inspection report recommends scheduling repair within 7 days.",
                ),
            ])],
            metadata=DocumentMetadata(page_count=1),
        )
        await indexing.index_document("proj_test", "doc1", parsed)

        # Now search
        retriever = HybridRetriever(
            keyword_index=indexing.get_keyword_index("proj_test"),
        )
        results = await retriever.retrieve("proj_test", "pump maintenance", top_k=5)
        assert len(results) > 0
        assert any("pump" in r.text.lower() for r in results)

    async def test_retrieve_empty_kb(self) -> None:
        """Searching an empty KB should return no results."""
        retriever = HybridRetriever(keyword_index=BM25Index())
        results = await retriever.retrieve("proj_empty", "test query", top_k=5)
        assert results == []

    async def test_retrieve_respects_top_k(self) -> None:
        """Retrieval should respect the top_k limit."""
        indexing = IndexingService()
        # Create a doc with many chunks
        blocks = [
            Block(kind="paragraph", text=f"pump maintenance content number {i}")
            for i in range(20)
        ]
        parsed = ParsedDocument(
            document_id="doc1", project_id="proj_test",
            source_filename="test.txt", source_mime_type="text/plain",
            pages=[Page(page_number=1, blocks=blocks)],
            metadata=DocumentMetadata(page_count=1),
        )
        await indexing.index_document("proj_test", "doc1", parsed)

        retriever = HybridRetriever(keyword_index=indexing.get_keyword_index("proj_test"))
        results = await retriever.retrieve("proj_test", "pump maintenance", top_k=3)
        assert len(results) <= 3

    async def test_retrieve_results_have_provenance(self) -> None:
        """Retrieval results should carry page, section_path, document_id."""
        indexing = IndexingService()
        parsed = ParsedDocument(
            document_id="doc1", project_id="proj_test",
            source_filename="test.txt", source_mime_type="text/plain",
            pages=[Page(page_number=3, blocks=[
                Block(
                    kind="paragraph", text="critical pump bearing failure analysis",
                    page=3, section_path=["Chapter 2", "Findings"],
                ),
            ])],
            metadata=DocumentMetadata(page_count=1),
        )
        await indexing.index_document("proj_test", "doc1", parsed)

        retriever = HybridRetriever(keyword_index=indexing.get_keyword_index("proj_test"))
        results = await retriever.retrieve("proj_test", "pump bearing failure", top_k=5)
        assert len(results) > 0
        r = results[0]
        assert r.document_id == "doc1"
        assert r.page == 3
        assert "Chapter 2" in r.section_path

    async def test_retrieve_document_filter(self) -> None:
        """Document filter should restrict results to one document."""
        indexing = IndexingService()
        for doc_id in ["doc_a", "doc_b"]:
            parsed = ParsedDocument(
                document_id=doc_id, project_id="proj_test",
                source_filename=f"{doc_id}.txt", source_mime_type="text/plain",
                pages=[Page(page_number=1, blocks=[
                    Block(kind="paragraph", text="pump maintenance procedure details"),
                ])],
                metadata=DocumentMetadata(page_count=1),
            )
            await indexing.index_document("proj_test", doc_id, parsed)

        retriever = HybridRetriever(keyword_index=indexing.get_keyword_index("proj_test"))
        results = await retriever.retrieve(
            "proj_test", "pump maintenance", top_k=10,
            document_filter={"document_id": "doc_a"},
        )
        assert len(results) > 0
        assert all(r.document_id == "doc_a" for r in results)
