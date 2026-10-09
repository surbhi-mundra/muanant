"""Hybrid retriever — combines vector + keyword search with RRF fusion.

The hybrid retriever is the retrieval layer's public entry point. It:

1. Runs vector search (Qdrant) and keyword search (BM25) in parallel.
2. Fuses the two ranked lists using Reciprocal Rank Fusion (RRF).
3. Returns unified ``RetrievalResult`` objects with provenance intact.

This is NOT the RAG pipeline (that's Phase 5, with query rewriting,
reranking, and evidence verification). This is the raw retrieval layer
that the RAG pipeline builds on.
"""

from __future__ import annotations

from dataclasses import dataclass

from sovereign.core.logging import get_logger
from sovereign.embeddings.service import EmbeddingService
from sovereign.retrieval.fusion import reciprocal_rank_fusion
from sovereign.retrieval.keyword import BM25Index, KeywordSearchResult
from sovereign.storage.qdrant import QdrantStore, get_qdrant_store

log = get_logger(__name__)


@dataclass(slots=True)
class RetrievalResult:
    """A unified retrieval result from the hybrid retriever."""

    chunk_id: str
    document_id: str
    text: str
    score: float  # fused RRF score
    page: int | None
    section_path: list[str]
    chunk_index: int
    block_kinds: list[str]
    # Per-ranker ranks for debugging
    vector_rank: int | None = None
    keyword_rank: int | None = None

    @property
    def section_label(self) -> str:
        return " > ".join(self.section_path) if self.section_path else "(no section)"


@dataclass(slots=True)
class HybridRetrievalConfig:
    """Configuration for the hybrid retriever."""

    top_k: int = 10
    vector_weight: float = 1.0  # implicit in RRF
    keyword_weight: float = 1.0  # implicit in RRF
    rrf_k: int = 60  # RRF smoothing constant
    # If True, run keyword search even when vector returns enough results
    always_run_keyword: bool = True


class HybridRetriever:
    """Combines vector + keyword search with RRF fusion.

    Usage::

        retriever = HybridRetriever()
        results = await retriever.retrieve("proj_1", "pump maintenance", top_k=10)
    """

    def __init__(
        self,
        qdrant: QdrantStore | None = None,
        embedding_service: EmbeddingService | None = None,
        keyword_index: BM25Index | None = None,
        config: HybridRetrievalConfig | None = None,
    ) -> None:
        self._qdrant = qdrant
        self._embedding_service = embedding_service
        self._keyword_index = keyword_index
        self._config = config or HybridRetrievalConfig()

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

    @property
    def keyword_index(self) -> BM25Index | None:
        return self._keyword_index

    def set_keyword_index(self, index: BM25Index) -> None:
        """Set the keyword index for a project. Called after indexing."""
        self._keyword_index = index

    async def retrieve(
        self,
        project_id: str,
        query: str,
        top_k: int | None = None,
        document_filter: dict[str, str] | None = None,
    ) -> list[RetrievalResult]:
        """Hybrid retrieval: vector + keyword → RRF fusion.

        Args:
            project_id: the project to search in (isolation enforced).
            query: the search query.
            top_k: number of results to return (default from config).
            document_filter: optional metadata filter (e.g. {"document_id": "doc_1"}).
        """
        k = top_k or self._config.top_k

        # 1. Embed the query
        query_vector = await self.embedding_service.embed_query(query)

        # 2. Vector search (fetch more than top_k for better fusion)
        vector_fetch = max(k * 3, 20)
        vector_results = self.qdrant.search(
            project_id=project_id,
            query_vector=query_vector,
            top_k=vector_fetch,
            document_filter=document_filter,
        )

        # 3. Keyword search (if index is available)
        keyword_results: list[KeywordSearchResult] = []
        if self._keyword_index is not None and self._config.always_run_keyword:
            keyword_results = self._keyword_index.search(query, top_k=vector_fetch)
            # Apply document filter to keyword results too
            if document_filter and "document_id" in document_filter:
                doc_id = document_filter["document_id"]
                keyword_results = [r for r in keyword_results if r.document_id == doc_id]

        # 4. Fuse with RRF
        vector_ids = [r.chunk_id for r in vector_results]
        keyword_ids = [r.chunk_id for r in keyword_results]

        ranked_lists: dict[str, list[str]] = {}
        if vector_ids:
            ranked_lists["vector"] = vector_ids
        if keyword_ids:
            ranked_lists["keyword"] = keyword_ids

        if not ranked_lists:
            return []

        fused = reciprocal_rank_fusion(ranked_lists, k=self._config.rrf_k)

        # 5. Build unified results, looking up full data from both sources
        vector_map = {r.chunk_id: r for r in vector_results}
        keyword_map = {r.chunk_id: r for r in keyword_results}

        results: list[RetrievalResult] = []
        for f in fused[:k]:
            # Prefer vector result (has more metadata), fall back to keyword
            vr = vector_map.get(f.item_id)
            kr = keyword_map.get(f.item_id)

            if vr:
                results.append(
                    RetrievalResult(
                        chunk_id=vr.chunk_id,
                        document_id=vr.document_id,
                        text=vr.text,
                        score=f.rrf_score,
                        page=vr.page,
                        section_path=vr.section_path,
                        chunk_index=vr.chunk_index,
                        block_kinds=vr.block_kinds,
                        vector_rank=f.ranks.get("vector"),
                        keyword_rank=f.ranks.get("keyword"),
                    )
                )
            elif kr:
                results.append(
                    RetrievalResult(
                        chunk_id=kr.chunk_id,
                        document_id=kr.document_id,
                        text=kr.text,
                        score=f.rrf_score,
                        page=kr.page,
                        section_path=kr.section_path,
                        chunk_index=kr.chunk_index,
                        block_kinds=kr.block_kinds,
                        vector_rank=f.ranks.get("vector"),
                        keyword_rank=f.ranks.get("keyword"),
                    )
                )

        log.info(
            "retrieval.hybrid.complete",
            project_id=project_id,
            query_len=len(query),
            vector_count=len(vector_results),
            keyword_count=len(keyword_results),
            fused_count=len(results),
        )

        return results
