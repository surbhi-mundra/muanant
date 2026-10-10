"""RAG API routes.

- POST /rag/query          — ask a grounded question, get an answer with citations
- POST /rag/query/markdown — same as /query but returns citations as rendered markdown
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from sovereign.evidence.renderer import CitationRenderer
from sovereign.rag.model import RAGResponse
from sovereign.rag.pipeline import get_rag_pipeline

router = APIRouter(prefix="/rag", tags=["rag"])

_DEV_PROJECT_ID = "01JQTESTPROJECT0000000001"


class RAGQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    document_id: str | None = None  # optional: restrict to one document


class ClaimResponse(BaseModel):
    text: str
    support_status: str
    evidence_count: int


class EvidenceResponse(BaseModel):
    document_id: str
    chunk_id: str
    page: int | None
    section_path: list[str]
    text: str


class CitationResponse(BaseModel):
    citation_id: str
    document_id: str
    document_filename: str
    chunk_id: str
    page: int | None
    section_path: list[str]
    source_label: str
    evidence_text: str
    support_status: str
    support_note: str
    relevance_score: float


class ContradictionResponse(BaseModel):
    conflict_type: str
    description: str
    citation_ids: list[str]
    conflicting_texts: list[str]


class EvidenceReportResponse(BaseModel):
    query: str
    summary: dict[str, int]
    citations: list[CitationResponse]
    contradictions: list[ContradictionResponse]
    has_contradictions: bool


class RAGQueryResponse(BaseModel):
    query: str
    verdict: str
    verdict_message: str
    answer: str
    claims: list[ClaimResponse]
    evidence: list[EvidenceResponse]
    evidence_report: EvidenceReportResponse | None = None
    is_answered: bool
    has_contradictions: bool


def _build_evidence_report(response: RAGResponse) -> EvidenceReportResponse | None:
    """Extract the EvidenceReport from a RAGResponse, if present."""
    if response.evidence_report is None:
        return None

    from typing import Any, cast

    from sovereign.evidence.model import EvidenceReport

    report: EvidenceReport = response.evidence_report  # type: ignore[assignment]
    renderer = CitationRenderer()
    structured: dict[str, Any] = renderer.render_structured(report)

    citations_raw: list[dict[str, Any]] = structured.get("citations", [])
    contradictions_raw: list[dict[str, Any]] = structured.get("contradictions", [])

    return EvidenceReportResponse(
        query=str(structured.get("query", "")),
        summary=cast(dict[str, int], structured.get("summary", {})),
        citations=[CitationResponse(**c) for c in citations_raw],
        contradictions=[ContradictionResponse(**c) for c in contradictions_raw],
        has_contradictions=bool(contradictions_raw),
    )


@router.post("/query", response_model=RAGQueryResponse)
async def rag_query(req: RAGQueryRequest) -> RAGQueryResponse:
    """Ask a grounded question. The pipeline retrieves evidence, generates
    an answer, verifies claims, and returns citations.

    If insufficient evidence is found, returns verdict="insufficient_evidence"
    with the message "I don't have sufficient evidence to answer this."
    """
    try:
        pipeline = get_rag_pipeline()
        document_filter = {"document_id": req.document_id} if req.document_id else None

        response: RAGResponse = await pipeline.query(
            project_id=_DEV_PROJECT_ID,
            query=req.query,
            document_filter=document_filter,
        )

        # Build evidence report safely — don't let it crash the whole response
        evidence_report = None
        try:
            evidence_report = _build_evidence_report(response)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("evidence_report_build_failed", error=str(e))

        return RAGQueryResponse(
            query=response.query,
            verdict=response.verdict.kind,
            verdict_message=response.verdict.message,
            answer=response.answer,
            claims=[
                ClaimResponse(
                    text=c.text,
                    support_status=c.support_status,
                    evidence_count=len(c.evidence),
                )
                for c in response.claims
            ],
            evidence=[
                EvidenceResponse(
                    document_id=e.document_id,
                    chunk_id=e.chunk_id,
                    page=e.page,
                    section_path=e.section_path,
                    text=e.text,
                )
                for e in response.evidence
            ],
            evidence_report=evidence_report,
            is_answered=response.is_answered,
            has_contradictions=response.has_contradictions,
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("rag_query_failed", error=str(e), exc_info=True)
        from sovereign.core.errors import SovereignError
        raise SovereignError(f"RAG query failed: {e}") from e


@router.post("/query/markdown")
async def rag_query_markdown(req: RAGQueryRequest) -> PlainTextResponse:
    """Same as /query but returns the evidence report as rendered markdown.

    Useful for workbench UI rendering and deliverable generation.
    """
    pipeline = get_rag_pipeline()
    document_filter = {"document_id": req.document_id} if req.document_id else None

    response: RAGResponse = await pipeline.query(
        project_id=_DEV_PROJECT_ID,
        query=req.query,
        document_filter=document_filter,
    )

    parts: list[str] = []

    # Answer
    if response.answer:
        parts.append(f"## Answer\n\n{response.answer}\n")
    else:
        parts.append(f"## {response.verdict.message}\n")

    # Claims
    if response.claims:
        parts.append("## Claims\n")
        for c in response.claims:
            parts.append(f"- [{c.support_status}] {c.text}")
        parts.append("")

    # Evidence report
    if response.evidence_report is not None:
        renderer = CitationRenderer()
        parts.append(renderer.render_markdown(response.evidence_report))  # type: ignore[arg-type]

    return PlainTextResponse(
        content="\n".join(parts),
        media_type="text/markdown",
    )
