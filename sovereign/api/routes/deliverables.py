"""Deliverable generation API routes.

- POST /deliverables  — generate a deliverable from agent outputs
- GET  /deliverables/{id}/export?format=pdf|docx|xlsx|csv|json|md
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel, Field

from sovereign.deliverables.builder import DeliverableBuilder
from sovereign.deliverables.exporter import DeliverableExporter
from sovereign.deliverables.renderer import DeliverableRenderer

router = APIRouter(prefix="/deliverables", tags=["deliverables"])

_DEV_PROJECT_ID = "01JQTESTPROJECT0000000001"


class DeliverableRequest(BaseModel):
    deliverable_type: str = Field(default="summary")
    query: str = Field(..., min_length=1)
    project_id: str = Field(default="")
    rag_response: dict[str, Any] | None = None
    findings: list[dict[str, Any]] | None = None
    evidence_report: dict[str, Any] | None = None
    risk_report: dict[str, Any] | None = None
    document_analysis: dict[str, Any] | None = None
    vision_description: str | None = None


class DeliverableResponse(BaseModel):
    deliverable_id: str
    title: str
    type: str
    section_count: int
    finding_count: int
    citation_count: int
    markdown: str


@router.post("", response_model=DeliverableResponse)
async def create_deliverable(req: DeliverableRequest) -> DeliverableResponse:
    """Generate a deliverable from agent outputs.

    Returns the deliverable metadata + rendered markdown.
    Use the export endpoint to get PDF/DOCX/XLSX/CSV/JSON.
    """
    builder = DeliverableBuilder()
    deliverable = builder.build(
        deliverable_type=req.deliverable_type,  # type: ignore[arg-type]
        query=req.query,
        project_id=req.project_id or _DEV_PROJECT_ID,
        rag_response=req.rag_response or {},
        findings=req.findings or [],
        evidence_report=req.evidence_report or {},
        risk_report=req.risk_report or {},
        document_analysis=req.document_analysis or {},
        vision_description=req.vision_description,
    )

    renderer = DeliverableRenderer()
    markdown = renderer.render_markdown(deliverable)

    return DeliverableResponse(
        deliverable_id=deliverable.metadata_extra.get("deliverable_id", ""),
        title=deliverable.metadata.title,
        type=deliverable.metadata.deliverable_type,
        section_count=deliverable.section_count,
        finding_count=len(deliverable.findings),
        citation_count=len(deliverable.citations),
        markdown=markdown,
    )


@router.post("/export")
async def export_deliverable(
    req: DeliverableRequest,
    format: str = "json",
) -> Response:
    """Generate and export a deliverable in the specified format.

    Formats: json, markdown, html, csv, xlsx, docx, pdf
    """
    builder = DeliverableBuilder()
    deliverable = builder.build(
        deliverable_type=req.deliverable_type,  # type: ignore[arg-type]
        query=req.query,
        project_id=req.project_id or _DEV_PROJECT_ID,
        rag_response=req.rag_response or {},
        findings=req.findings or [],
        evidence_report=req.evidence_report or {},
        risk_report=req.risk_report or {},
        document_analysis=req.document_analysis or {},
        vision_description=req.vision_description,
    )

    exporter = DeliverableExporter()

    if format == "json":
        content = exporter.to_json(deliverable)
        return Response(content=content, media_type="application/json")
    if format == "markdown" or format == "md":
        content = exporter.to_markdown(deliverable)
        return Response(content=content, media_type="text/markdown")
    if format == "html":
        content = exporter.to_html(deliverable)
        return Response(content=content, media_type="text/html")
    if format == "csv":
        content = exporter.to_csv(deliverable)
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=findings.csv"},
        )
    if format == "xlsx":
        content_bytes: bytes | str = exporter.to_xlsx(deliverable)
        return Response(
            content=content_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=report.xlsx"},
        )
    if format == "docx":
        content_bytes = exporter.to_docx(deliverable)
        return Response(
            content=content_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": "attachment; filename=report.docx"},
        )
    if format == "pdf":
        content_bytes = exporter.to_pdf(deliverable)
        return Response(
            content=content_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=report.pdf"},
        )

    return Response(content=f"Unsupported format: {format}", status_code=400)
