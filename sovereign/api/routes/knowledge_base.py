"""Knowledge base API routes.

- POST   /documents/{id}/index  — manually (re)index a document
- POST   /search                — hybrid retrieval search
- GET    /kb/stats              — knowledge base statistics
- DELETE /documents/{id}/index  — remove a document from the index
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from sovereign.embeddings.indexing import get_indexing_service
from sovereign.ingestion.service import get_document, get_parsed_document
from sovereign.retrieval.service import HybridRetriever

router = APIRouter(tags=["knowledge-base"])

_DEV_PROJECT_ID = "01JQTESTPROJECT0000000001"


class IndexResponse(BaseModel):
    document_id: str
    status: str
    chunk_count: int
    vector_count: int
    keyword_count: int
    error: str | None = None


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=10, ge=1, le=100)
    document_id: str | None = None  # optional filter


class SearchHit(BaseModel):
    chunk_id: str
    document_id: str
    text: str
    score: float
    page: int | None
    section_path: list[str]
    chunk_index: int
    block_kinds: list[str]
    vector_rank: int | None = None
    keyword_rank: int | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchHit]
    total: int


class KBStatsResponse(BaseModel):
    project_id: str
    keyword_index_size: int
    vector_count: int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.post("/documents/{document_id}/index", response_model=IndexResponse)
async def index_document(document_id: str) -> JSONResponse:
    """Manually (re)index a document into the knowledge base."""
    project_id = _DEV_PROJECT_ID
    get_document(project_id, document_id)
    parsed = get_parsed_document(project_id, document_id)

    indexing = get_indexing_service()
    result = await indexing.index_document(
        project_id=project_id,
        document_id=document_id,
        parsed=parsed,
    )

    # Update document status
    from sovereign.storage.db.base import COLLECTIONS, session_scope

    if result.status == "indexed":
        with session_scope() as db:
            db[COLLECTIONS["documents"]].update_one(
                {"id": document_id}, {"$set": {"status": "indexed"}}
            )

    return JSONResponse(
        status_code=200,
        content=IndexResponse(
            document_id=result.document_id,
            status=result.status,
            chunk_count=result.chunk_count,
            vector_count=result.vector_count,
            keyword_count=result.keyword_count,
            error=result.error,
        ).model_dump(),
    )


@router.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest) -> SearchResponse:
    """Hybrid retrieval search across the knowledge base."""
    project_id = _DEV_PROJECT_ID

    indexing = get_indexing_service()
    keyword_index = indexing.get_keyword_index(project_id)

    retriever = HybridRetriever(keyword_index=keyword_index)

    document_filter = {"document_id": req.document_id} if req.document_id else None
    results = await retriever.retrieve(
        project_id=project_id,
        query=req.query,
        top_k=req.top_k,
        document_filter=document_filter,
    )

    return SearchResponse(
        query=req.query,
        results=[
            SearchHit(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                text=r.text,
                score=r.score,
                page=r.page,
                section_path=r.section_path,
                chunk_index=r.chunk_index,
                block_kinds=r.block_kinds,
                vector_rank=r.vector_rank,
                keyword_rank=r.keyword_rank,
            )
            for r in results
        ],
        total=len(results),
    )


@router.get("/kb/stats", response_model=KBStatsResponse)
async def kb_stats() -> KBStatsResponse:
    """Return knowledge base statistics for the current project."""
    project_id = _DEV_PROJECT_ID
    indexing = get_indexing_service()
    stats = indexing.get_stats(project_id)
    return KBStatsResponse(
        project_id=project_id,
        keyword_index_size=stats["keyword_index_size"],
        vector_count=stats["vector_count"],
    )


@router.delete("/documents/{document_id}/index", status_code=204)
async def remove_from_index(document_id: str) -> None:
    """Remove a document from the knowledge base index."""
    project_id = _DEV_PROJECT_ID
    # Verify the document exists
    get_document(project_id, document_id)

    indexing = get_indexing_service()
    indexing.remove_document(project_id, document_id)
