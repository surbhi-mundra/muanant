"""RAG API routes.

- POST /rag/query  — ask a grounded question, get an answer with citations
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

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


class RAGQueryResponse(BaseModel):
    query: str
    verdict: str
    verdict_message: str
    answer: str
    claims: list[ClaimResponse]
    evidence: list[EvidenceResponse]
    is_answered: bool


@router.post("/query", response_model=RAGQueryResponse)
async def rag_query(req: RAGQueryRequest) -> RAGQueryResponse:
    """Ask a grounded question. The pipeline retrieves evidence, generates
    an answer, verifies claims, and returns citations.

    If insufficient evidence is found, returns verdict="insufficient_evidence"
    with the message "I don't have sufficient evidence to answer this."
    """
    pipeline = get_rag_pipeline()
    document_filter = {"document_id": req.document_id} if req.document_id else None

    response: RAGResponse = await pipeline.query(
        project_id=_DEV_PROJECT_ID,
        query=req.query,
        document_filter=document_filter,
    )

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
        is_answered=response.is_answered,
    )
