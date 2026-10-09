"""Vision and OCR API routes.

- POST /vision/describe   — describe an image via the vision model
- POST /vision/diagram    — describe an engineering diagram
- POST /vision/inspect    — describe an inspection photo
- POST /ocr/image         — OCR a standalone image
- POST /documents/{id}/re-ocr — re-run OCR on a document
"""

from __future__ import annotations

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel

from sovereign.core.errors import NotFoundError
from sovereign.ingestion.service import get_document
from sovereign.models.gateway import get_model_gateway
from sovereign.storage.objects import get_object_store
from sovereign.vision.service import VisionService

router = APIRouter(tags=["vision-ocr"])

_DEV_PROJECT_ID = "01JQTESTPROJECT0000000001"


class VisionResponse(BaseModel):
    text: str
    model: str
    image_count: int


# ---------------------------------------------------------------------------
# Vision routes
# ---------------------------------------------------------------------------
@router.post("/vision/describe", response_model=VisionResponse)
async def describe_image(file: UploadFile = File(...)) -> VisionResponse:
    """Describe an image using the vision model."""
    gateway = get_model_gateway()
    data = await file.read()
    service = VisionService(gateway)
    result = await service.describe_image(data, media_type=file.content_type or "image/png")
    return VisionResponse(
        text=result.text, model=result.model, image_count=result.image_count
    )


@router.post("/vision/diagram", response_model=VisionResponse)
async def describe_diagram(file: UploadFile = File(...)) -> VisionResponse:
    """Describe an engineering diagram or schematic."""
    gateway = get_model_gateway()
    data = await file.read()
    service = VisionService(gateway)
    result = await service.describe_diagram(data, media_type=file.content_type or "image/png")
    return VisionResponse(
        text=result.text, model=result.model, image_count=result.image_count
    )


@router.post("/vision/inspect", response_model=VisionResponse)
async def describe_inspection(file: UploadFile = File(...)) -> VisionResponse:
    """Describe an industrial inspection photograph."""
    gateway = get_model_gateway()
    data = await file.read()
    service = VisionService(gateway)
    result = await service.describe_inspection_image(
        data, media_type=file.content_type or "image/png"
    )
    return VisionResponse(
        text=result.text, model=result.model, image_count=result.image_count
    )


# ---------------------------------------------------------------------------
# OCR route
# ---------------------------------------------------------------------------
@router.post("/ocr/image", response_model=VisionResponse)
async def ocr_image_endpoint(file: UploadFile = File(...)) -> VisionResponse:
    """Run OCR on a standalone image (PNG/JPG/WEBP)."""
    from sovereign.ocr.pipeline import OCROptions, ocr_image

    data = await file.read()
    media_type = file.content_type or "image/png"
    parsed = await ocr_image(
        image_data=data,
        filename=file.filename or "image",
        media_type=media_type,
        options=OCROptions(),
    )
    return VisionResponse(
        text=parsed.total_text,
        model=parsed.metadata.extra.get("ocr_engine", "tesseract"),
        image_count=1,
    )


@router.post("/documents/{document_id}/re-ocr", response_model=VisionResponse)
async def reocr_document(document_id: str) -> VisionResponse:
    """Re-run OCR on an already-ingested document (e.g. after OCR engine upgrade)."""
    from sovereign.ocr.pipeline import OCROptions, ocr_image, ocr_pdf

    project_id = _DEV_PROJECT_ID
    doc = get_document(project_id, document_id)
    store = get_object_store()
    data = store.get(project_id, doc.storage_key)

    if doc.mime_type.startswith("image/"):
        parsed = await ocr_image(
            image_data=data,
            filename=doc.original_filename,
            media_type=doc.mime_type,
            options=OCROptions(),
        )
    elif doc.mime_type == "application/pdf":
        parsed = await ocr_pdf(
            pdf_data=data,
            filename=doc.original_filename,
            options=OCROptions(),
        )
    else:
        msg = f"document {document_id} is not an image or PDF (got {doc.mime_type})"
        raise NotFoundError(msg)

    return VisionResponse(
        text=parsed.total_text,
        model=parsed.metadata.extra.get("ocr_engine", "tesseract"),
        image_count=1,
    )
