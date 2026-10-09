"""Stage 6 — Evidence selection.

Takes the reranked results and selects the top-k pieces of evidence to
feed to the LLM. Applies a minimum score threshold to avoid feeding
low-relevance noise.

Also deduplicates by document (keeping the highest-scoring chunk per
document when ``max_per_document`` is set) to ensure evidence diversity.
"""

from __future__ import annotations

from sovereign.rag.model import EvidenceRef
from sovereign.retrieval.service import RetrievalResult


def select_evidence(
    results: list[RetrievalResult],
    *,
    top_k: int = 5,
    min_score: float = 0.01,
    max_per_document: int | None = None,
) -> list[EvidenceRef]:
    """Stage 6: select evidence chunks for the LLM context.

    Args:
        results: reranked retrieval results (best first).
        top_k: maximum number of evidence chunks to select.
        min_score: minimum reranker score to include (filters noise).
        max_per_document: if set, cap evidence per document (diversity).

    Returns: list of EvidenceRef objects ready for LLM context.
    """
    selected: list[EvidenceRef] = []
    doc_counts: dict[str, int] = {}

    for r in results:
        # Score threshold
        if r.score < min_score:
            continue

        # Per-document cap
        if max_per_document is not None:
            count = doc_counts.get(r.document_id, 0)
            if count >= max_per_document:
                continue

        selected.append(
            EvidenceRef(
                document_id=r.document_id,
                chunk_id=r.chunk_id,
                page=r.page,
                section_path=r.section_path,
                text=r.text,
            )
        )
        doc_counts[r.document_id] = doc_counts.get(r.document_id, 0) + 1

        if len(selected) >= top_k:
            break

    return selected
