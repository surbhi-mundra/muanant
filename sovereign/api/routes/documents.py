"""Document upload and management routes."""

from __future__ import annotations

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from sovereign.ingestion.service import (
    delete_document,
    get_document,
    get_parsed_document,
    ingest_document,
    list_documents,
)

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentResponse(BaseModel):
    id: str
    project_id: str
    original_filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    status: str
    version: int
    created_at: str


class IngestResponse(BaseModel):
    document_id: str
    project_id: str
    status: str
    mime_type: str
    sha256: str
    size_bytes: int
    version: int
    is_duplicate: bool
    parse_warnings: list[str]
    quarantine_reason: str | None = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int


# TODO Phase 11: replace with real auth. For now, a hardcoded dev project.
_DEV_PROJECT_ID = "01JQTESTPROJECT0000000001"


@router.post("", response_model=IngestResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
) -> JSONResponse:
    """Upload a document for ingestion.

    Accepts multipart/form-data with a single file field.
    Validates, stores, parses, and indexes the document.
    """
    project_id = _DEV_PROJECT_ID
    data = await file.read()
    result = await ingest_document(
        project_id=project_id,
        filename=file.filename or "upload",
        data=data,
        client_mime=file.content_type or "",
    )
    return JSONResponse(
        status_code=201 if result.status in ("parsed", "stored") else 200,
        content=IngestResponse(
            document_id=result.document_id,
            project_id=result.project_id,
            status=result.status,
            mime_type=result.mime_type,
            sha256=result.sha256,
            size_bytes=result.size_bytes,
            version=result.version,
            is_duplicate=result.is_duplicate,
            parse_warnings=result.parse_warnings,
            quarantine_reason=result.quarantine_reason,
        ).model_dump(),
    )


@router.get("", response_model=DocumentListResponse)
async def list_project_documents(limit: int = 100, offset: int = 0) -> DocumentListResponse:
    """List documents in the current project."""
    project_id = _DEV_PROJECT_ID
    docs = list_documents(project_id, limit=limit, offset=offset)
    return DocumentListResponse(
        documents=[
            DocumentResponse(
                id=d.id,
                project_id=d.project_id,
                original_filename=d.original_filename,
                mime_type=d.mime_type,
                size_bytes=d.size_bytes,
                sha256=d.sha256,
                status=d.status,
                version=d.version,
                created_at=d.created_at.isoformat() if d.created_at else "",
            )
            for d in docs
        ],
        total=len(docs),
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document_info(document_id: str) -> DocumentResponse:
    """Get document metadata."""
    project_id = _DEV_PROJECT_ID
    doc = get_document(project_id, document_id)
    return DocumentResponse(
        id=doc.id,
        project_id=doc.project_id,
        original_filename=doc.original_filename,
        mime_type=doc.mime_type,
        size_bytes=doc.size_bytes,
        sha256=doc.sha256,
        status=doc.status,
        version=doc.version,
        created_at=doc.created_at.isoformat() if doc.created_at else "",
    )


@router.get("/{document_id}/parsed")
async def get_parsed(document_id: str) -> JSONResponse:
    """Get the parsed document structure (pages, blocks, tables, metadata)."""
    project_id = _DEV_PROJECT_ID
    parsed = get_parsed_document(project_id, document_id)
    return JSONResponse(content=parsed.model_dump())


@router.delete("/{document_id}", status_code=204)
async def remove_document(document_id: str) -> None:
    """Delete a document and its parsed structure."""
    project_id = _DEV_PROJECT_ID
    delete_document(project_id, document_id)
