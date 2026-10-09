"""Stage 5 — Reranking via the Reranker protocol.

Takes the top-N retrieval results and reranks them with a cross-encoder
(or mock lexical reranker in dev). This improves precision over the
hybrid retriever's RRF-fused results.

The reranker is selected via ``configs/models.yaml``. In dev, it's the
MockReranker (Jaccard overlap). In prod, a cross-encoder like
``BAAI/bge-reranker-v2-m3``.
"""

from __future__ import annotations

from sovereign.core.logging import get_logger
from sovereign.models.gateway import ModelGateway
from sovereign.models.schemas import RerankCandidate, RerankRequest
from sovereign.retrieval.service import RetrievalResult

log = get_logger(__name__)


async def rerank_results(
    query: str,
    results: list[RetrievalResult],
    gateway: ModelGateway,
    top_k: int = 10,
) -> list[RetrievalResult]:
    """Stage 5: rerank retrieval results using the Reranker model.

    Converts RetrievalResults → RerankCandidates, calls the reranker,
    then maps back to RetrievalResults in new order.
    """
    if not results:
        return []

    candidates = [
        RerankCandidate(
            doc_id=r.chunk_id,
            text=r.text,
            metadata={
                "document_id": r.document_id,
                "page": r.page,
                "section_path": r.section_path,
                "chunk_index": r.chunk_index,
                "block_kinds": r.block_kinds,
                "original_score": r.score,
            },
        )
        for r in results
    ]

    resp = await gateway.reranker.rerank(
        RerankRequest(query=query, candidates=candidates, top_k=top_k)
    )

    # Map back to RetrievalResult using the reranked order
    result_map = {r.chunk_id: r for r in results}
    reranked: list[RetrievalResult] = []
    for scored in resp.ranked:
        original = result_map.get(scored.doc_id)
        if original is None:
            continue
        # Update the score to the reranker's score
        reranked.append(
            RetrievalResult(
                chunk_id=original.chunk_id,
                document_id=original.document_id,
                text=original.text,
                score=scored.score,
                page=original.page,
                section_path=original.section_path,
                chunk_index=original.chunk_index,
                block_kinds=original.block_kinds,
                vector_rank=original.vector_rank,
                keyword_rank=original.keyword_rank,
            )
        )

    log.info(
        "rag.rerank.complete",
        input_count=len(results),
        output_count=len(reranked),
        top_score=reranked[0].score if reranked else 0.0,
    )

    return reranked
