"""The 9-stage RAG pipeline — the sole entry point for grounded Q&A.

Orchestrates: understand → rewrite → retrieve → filter → rerank → select
→ reason → verify → respond.

Usage::

    pipeline = RAGPipeline(gateway, retriever)
    response = await pipeline.query("proj_1", "What is the maintenance schedule for pump P-101?")
    if response.is_answered:
        print(response.answer)
        for claim in response.claims:
            print(f"  [{claim.support_status}] {claim.text}")
    else:
        print(response.verdict.message)
"""

from __future__ import annotations

from dataclasses import dataclass

from sovereign.core.logging import get_logger
from sovereign.embeddings.indexing import IndexingService, get_indexing_service
from sovereign.evidence.collector import EvidenceCollector
from sovereign.evidence.contradictions import ContradictionDetector
from sovereign.evidence.model import EvidenceReport
from sovereign.models.gateway import ModelGateway, get_model_gateway
from sovereign.rag.model import Claim, RAGResponse, Verdict
from sovereign.rag.reason import generate_answer
from sovereign.rag.rewrite import expand_query
from sovereign.rag.select import select_evidence
from sovereign.rag.understand import understand_query
from sovereign.rag.verify import verify_answer
from sovereign.reranking.service import rerank_results
from sovereign.retrieval.service import HybridRetriever, RetrievalResult

log = get_logger(__name__)


@dataclass(slots=True)
class RAGConfig:
    """Configuration for the RAG pipeline."""

    # Retrieval
    retrieval_top_k: int = 20  # fetch N candidates before reranking
    # Reranking
    rerank_top_k: int = 10  # rerank top N
    # Evidence selection
    evidence_top_k: int = 5  # feed top N to the LLM
    evidence_min_score: float = 0.01  # minimum reranker score
    max_per_document: int | None = 3  # diversity: max evidence per doc
    # Verification
    verify_claims: bool = True  # run stage 8 (evidence verification)
    # Verdict thresholds
    min_evidence_count: int = 1  # need at least this many evidence chunks
    min_supported_claims_ratio: float = 0.3  # <30% supported → insufficient


class RAGPipeline:
    """The 9-stage grounded retrieval pipeline.

    Depends on:
    - ModelGateway (for LLM, reranker, embeddings)
    - HybridRetriever (stages 3-4)
    - IndexingService (for the keyword index)
    """

    def __init__(
        self,
        gateway: ModelGateway | None = None,
        retriever: HybridRetriever | None = None,
        indexing: IndexingService | None = None,
        config: RAGConfig | None = None,
    ) -> None:
        self._gateway = gateway
        self._retriever = retriever
        self._indexing = indexing
        self._config = config or RAGConfig()

    @property
    def gateway(self) -> ModelGateway:
        if self._gateway is None:
            self._gateway = get_model_gateway()
        return self._gateway

    @property
    def indexing(self) -> IndexingService:
        if self._indexing is None:
            self._indexing = get_indexing_service()
        return self._indexing

    @property
    def retriever(self) -> HybridRetriever:
        if self._retriever is None:
            self._retriever = HybridRetriever(
                keyword_index=self.indexing.get_keyword_index(_current_project_id())
            )
        return self._retriever

    async def query(
        self,
        project_id: str,
        query: str,
        document_filter: dict[str, str] | None = None,
    ) -> RAGResponse:
        """Run the full 9-stage RAG pipeline.

        Args:
            project_id: project to search in (isolation enforced).
            query: the user's question.
            document_filter: optional metadata filter.

        Returns: a RAGResponse with verdict, answer, claims, and evidence.
        """
        trace: dict[str, object] = {}
        _set_current_project_id(project_id)

        # --- Stage 1: Query understanding ---
        analysis = await understand_query(query, self.gateway)
        trace["stage1_intent"] = analysis.intent
        trace["stage1_key_terms"] = analysis.key_terms
        log.info("rag.stage1.complete", intent=analysis.intent, key_terms=analysis.key_terms)

        # --- Stage 2: Query rewriting / expansion ---
        expanded_queries = expand_query(query, analysis)
        trace["stage2_expanded_queries"] = expanded_queries
        log.info("rag.stage2.complete", query_count=len(expanded_queries))

        # --- Stages 3-4: Hybrid retrieval + metadata filtering ---
        all_results: list[RetrievalResult] = []
        seen_chunk_ids: set[str] = set()
        for eq in expanded_queries:
            results = await self.retriever.retrieve(
                project_id=project_id,
                query=eq,
                top_k=self._config.retrieval_top_k,
                document_filter=document_filter,
            )
            for r in results:
                if r.chunk_id not in seen_chunk_ids:
                    all_results.append(r)
                    seen_chunk_ids.add(r.chunk_id)

        trace["stage3_candidates"] = len(all_results)
        log.info("rag.stage3.complete", candidates=len(all_results))

        # --- Stage 5: Reranking ---
        reranked = await rerank_results(
            query=query,
            results=all_results,
            gateway=self.gateway,
            top_k=self._config.rerank_top_k,
        )
        trace["stage5_reranked"] = len(reranked)
        log.info("rag.stage5.complete", reranked=len(reranked))

        # --- Stage 6: Evidence selection ---
        evidence = select_evidence(
            reranked,
            top_k=self._config.evidence_top_k,
            min_score=self._config.evidence_min_score,
            max_per_document=self._config.max_per_document,
        )
        trace["stage6_evidence_count"] = len(evidence)
        log.info("rag.stage6.complete", evidence_count=len(evidence))

        # --- Phase 6: Build EvidenceReport (citations + contradictions) ---
        collector = EvidenceCollector(
            max_per_document=self._config.max_per_document or 3,
            max_total=self._config.evidence_top_k,
            min_score=self._config.evidence_min_score,
        )
        citations = collector.collect(reranked, project_id=project_id)

        # Detect contradictions
        detector = ContradictionDetector()
        contradictions = detector.detect(citations)

        evidence_report = EvidenceReport(
            query=query,
            citations=citations,
            contradictions=contradictions,
        )
        trace["evidence_citations"] = len(citations)
        trace["evidence_contradictions"] = len(contradictions)
        if contradictions:
            log.info(
                "rag.evidence.contradictions_found",
                count=len(contradictions),
                types=[c.conflict_type for c in contradictions],
            )

        # Check: do we have enough evidence?
        if len(evidence) < self._config.min_evidence_count:
            log.info("rag.verdict.insufficient_evidence", reason="not enough evidence chunks")
            return RAGResponse(
                query=query,
                verdict=Verdict.insufficient_evidence(),
                evidence=evidence,
                evidence_report=evidence_report,
                pipeline_trace=trace,
            )

        # --- Stage 7: LLM reasoning ---
        answer = await generate_answer(query, evidence, self.gateway)
        trace["stage7_answer_length"] = len(answer)
        log.info("rag.stage7.complete", answer_length=len(answer))

        # Check: did the LLM say "insufficient evidence"?
        if "don't have sufficient evidence" in answer.lower():
            log.info("rag.verdict.insufficient_evidence", reason="LLM self-reported insufficient")
            return RAGResponse(
                query=query,
                verdict=Verdict.insufficient_evidence(),
                answer=answer,
                evidence=evidence,
                evidence_report=evidence_report,
                pipeline_trace=trace,
            )

        # --- Stage 8: Evidence verification ---
        claims: list[Claim] = []
        if self._config.verify_claims:
            claims = await verify_answer(answer, evidence, self.gateway)
            trace["stage8_claims"] = len(claims)
            supported = sum(1 for c in claims if c.support_status == "SUPPORTED")
            trace["stage8_supported_claims"] = supported
            log.info("rag.stage8.complete", claims=len(claims), supported=supported)

            # Update citation support statuses based on verification
            for cit in citations:
                cit.support_status = "SUPPORTED"  # default for cited evidence
            # Mark conflicting citations if contradictions were detected
            if contradictions:
                for con in contradictions:
                    for cit_id in con.citation_ids:
                        for cit in citations:
                            if cit.citation_id == cit_id:
                                cit.support_status = "CONFLICTING"
                                cit.support_note = con.description
                                break

            # Check: are enough claims supported?
            if claims:
                ratio = supported / len(claims)
                if ratio < self._config.min_supported_claims_ratio:
                    log.info(
                        "rag.verdict.insufficient_evidence",
                        reason="too few supported claims",
                        ratio=ratio,
                    )
                    return RAGResponse(
                        query=query,
                        verdict=Verdict.insufficient_evidence(),
                        answer=answer,
                        claims=claims,
                        evidence=evidence,
                        evidence_report=evidence_report,
                        pipeline_trace=trace,
                    )

        # --- Stage 9: Final response ---
        log.info("rag.verdict.answered")
        return RAGResponse(
            query=query,
            verdict=Verdict.answered(),
            answer=answer,
            claims=claims,
            evidence=evidence,
            evidence_report=evidence_report,
            pipeline_trace=trace,
        )


# ---------------------------------------------------------------------------
# Project ID context (for the retriever to get the right keyword index)
# ---------------------------------------------------------------------------
_current_pid: str = ""


def _set_current_project_id(pid: str) -> None:
    global _current_pid  # noqa: PLW0603
    _current_pid = pid


def _current_project_id() -> str:
    return _current_pid


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
_pipeline: RAGPipeline | None = None


def get_rag_pipeline() -> RAGPipeline:
    """Return the cached RAGPipeline singleton."""
    global _pipeline  # noqa: PLW0603
    if _pipeline is None:
        _pipeline = RAGPipeline()
    return _pipeline


def reset_rag_pipeline() -> None:
    """Test helper: drop the cached pipeline."""
    global _pipeline  # noqa: PLW0603
    _pipeline = None
