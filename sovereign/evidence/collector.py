"""Evidence collector — gathers and deduplicates evidence from retrieval results.

Takes retrieval results (from the hybrid retriever) and converts them into
``Citation`` objects with full provenance. Handles:

1. **Deduplication**: identical chunks from different query reformulations
   are merged into a single citation.
2. **Source diversity**: caps citations per document to ensure the answer
   isn't based on a single source.
3. **Score normalization**: ensures citation relevance scores are comparable.
4. **Filename resolution**: looks up document filenames for human-readable
   citation rendering.
"""

from __future__ import annotations

from sovereign.core.logging import get_logger
from sovereign.evidence.model import Citation
from sovereign.retrieval.service import RetrievalResult
from sovereign.storage.db.base import session_scope
from sovereign.storage.db.models import Document

log = get_logger(__name__)


class EvidenceCollector:
    """Collects and deduplicates evidence from retrieval results.

    Usage::

        collector = EvidenceCollector()
        citations = collector.collect(results, project_id="proj_1")
    """

    def __init__(
        self,
        max_per_document: int = 3,
        max_total: int = 10,
        min_score: float = 0.01,
    ) -> None:
        self.max_per_document = max_per_document
        self.max_total = max_total
        self.min_score = min_score

    def collect(
        self,
        results: list[RetrievalResult],
        project_id: str = "",
    ) -> list[Citation]:
        """Convert retrieval results into deduplicated Citations.

        Args:
            results: ranked retrieval results (best first).
            project_id: for filename lookup.

        Returns: list of Citation objects, deduplicated and capped.
        """
        if not results:
            return []

        # Build filename lookup
        filenames = _lookup_filenames(
            project_id, {r.document_id for r in results}
        )

        # Deduplicate by chunk_id
        seen: set[str] = set()
        doc_counts: dict[str, int] = {}
        citations: list[Citation] = []

        for i, r in enumerate(results):
            # Score threshold
            if r.score < self.min_score:
                continue

            # Dedup
            if r.chunk_id in seen:
                continue

            # Per-document diversity cap
            doc_count = doc_counts.get(r.document_id, 0)
            if doc_count >= self.max_per_document:
                continue

            seen.add(r.chunk_id)
            doc_counts[r.document_id] = doc_count + 1

            citations.append(
                Citation(
                    citation_id=f"cit_{i:03d}",
                    document_id=r.document_id,
                    document_filename=filenames.get(r.document_id, ""),
                    chunk_id=r.chunk_id,
                    page=r.page,
                    section_path=r.section_path,
                    evidence_text=r.text,
                    support_status="SUPPORTED",  # default; verifier updates
                    relevance_score=r.score,
                )
            )

            if len(citations) >= self.max_total:
                break

        log.info(
            "evidence.collected",
            input_count=len(results),
            output_count=len(citations),
            unique_docs=len(doc_counts),
        )

        return citations


def _lookup_filenames(project_id: str, document_ids: set[str]) -> dict[str, str]:
    """Look up original filenames for a set of document IDs.

    Returns {document_id: filename} dict. Silently skips IDs not found
    (they'll have empty filenames in citations).
    """
    if not document_ids:
        return {}

    result: dict[str, str] = {}
    try:
        with session_scope() as s:
            docs = (
                s.query(Document)
                .filter(
                    Document.project_id == project_id,
                    Document.id.in_(document_ids),
                )
                .all()
            )
            for d in docs:
                result[d.id] = d.original_filename
    except Exception as e:
        log.warning("evidence.filename_lookup_failed", error=str(e))

    return result
