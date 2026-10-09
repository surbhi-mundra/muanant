"""Scanned-PDF detection and OCR pipeline.

A PDF is "scanned" if its pages contain little or no extractable text —
the content is images of text, not actual text. This module:

1. Detects scanned PDFs by checking text density per page.
2. Renders scanned pages to images (via PyMuPDF).
3. Runs OCR on each image (via the OCR protocol).
4. Merges OCR results back into a ParsedDocument, preserving page numbers
   and adding provenance metadata (source = "ocr").

The pipeline is designed to be selective: only pages with low text density
get OCR'd. Mixed PDFs (some text pages, some scanned pages) are handled
correctly — text pages keep their extracted text, scanned pages get OCR.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

import fitz  # PyMuPDF
from PIL import Image

from sovereign.core.logging import get_logger
from sovereign.models.schemas import ImageInput, OCRRequest
from sovereign.ocr.tesseract import TesseractOCR
from sovereign.parsing.model import (
    Block,
    BoundingBox,
    DocumentMetadata,
    Page,
    ParsedDocument,
)

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------
@dataclass
class ScanDetectionResult:
    """Result of scanned-PDF detection on a single page."""

    page_number: int
    is_scanned: bool
    text_char_count: int
    image_count: int
    text_density: float  # chars per 1000 pixels²


@dataclass
class DocumentScanReport:
    """Detection result for an entire document."""

    pages: list[ScanDetectionResult] = field(default_factory=list)
    any_scanned: bool = False
    all_scanned: bool = False
    total_pages: int = 0

    @property
    def scanned_page_numbers(self) -> list[int]:
        """1-indexed page numbers that are scanned."""
        return [p.page_number for p in self.pages if p.is_scanned]


# Threshold: if a page has fewer than this many characters per 1000 px²,
# it's considered scanned. Tunable — typical text pages have 50+ chars/1000px².
TEXT_DENSITY_THRESHOLD = 5.0
# Minimum absolute char count below which a page is definitely scanned.
MIN_TEXT_CHARS = 10


def detect_scanned_pdf(data: bytes) -> DocumentScanReport:
    """Detect which pages of a PDF are scanned (image-only).

    A page is "scanned" if:
    - It has very little extractable text (< MIN_TEXT_CHARS chars), AND
    - It contains at least one image, OR
    - Its text density is below TEXT_DENSITY_THRESHOLD

    Returns a per-page report.
    """
    report = DocumentScanReport()

    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as e:
        log.error("ocr.scan_detection.open_failed", error=str(e))
        return report

    report.total_pages = len(doc)

    for page_num in range(len(doc)):
        page = doc[page_num]
        page_width = page.rect.width
        page_height = page.rect.height
        page_area = page_width * page_height

        # Extract text
        text = page.get_text("text")
        char_count = len(text.strip())

        # Count images
        image_list = page.get_images()
        image_count = len(image_list)

        # Text density
        density = (char_count / page_area * 1000) if page_area > 0 else 0.0

        is_scanned = char_count < MIN_TEXT_CHARS and (image_count > 0 or char_count == 0)
        # Also flag low-density pages that have images (partially scanned)
        if not is_scanned and density < TEXT_DENSITY_THRESHOLD and image_count > 0:
            is_scanned = True

        result = ScanDetectionResult(
            page_number=page_num + 1,
            is_scanned=is_scanned,
            text_char_count=char_count,
            image_count=image_count,
            text_density=density,
        )
        report.pages.append(result)

    doc.close()

    report.any_scanned = any(p.is_scanned for p in report.pages)
    report.all_scanned = len(report.pages) > 0 and all(p.is_scanned for p in report.pages)

    return report


# ---------------------------------------------------------------------------
# PDF page rendering
# ---------------------------------------------------------------------------
def render_pdf_page_to_image(
    pdf_data: bytes, page_number: int, dpi: int = 200
) -> bytes | None:
    """Render a PDF page to PNG bytes.

    ``page_number`` is 1-indexed. Returns None on failure.
    200 DPI is a good balance between OCR accuracy and speed.
    """
    try:
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        if page_number < 1 or page_number > len(doc):
            return None
        page = doc[page_number - 1]
        # zoom = dpi / 72 (PDF default DPI)
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        png_bytes: bytes = pix.tobytes("png")
        doc.close()
        return png_bytes
    except Exception as e:
        log.error(
            "ocr.render_page.failed",
            page_number=page_number,
            error=str(e),
        )
        return None


# ---------------------------------------------------------------------------
# OCR pipeline
# ---------------------------------------------------------------------------
@dataclass
class OCROptions:
    """Configuration for the OCR pipeline."""

    # DPI for rendering scanned pages to images
    render_dpi: int = 200
    # Languages for OCR (BCP-47 codes: eng, deu, fra, etc.)
    languages: list[str] | None = None
    # Whether to extract layout blocks (slower, more structure)
    with_layout: bool = True
    # Confidence threshold: OCR results below this are flagged as low-confidence
    min_confidence: float = 0.5

    def __post_init__(self) -> None:
        if self.languages is None:
            self.languages = ["eng"]


async def ocr_pdf(
    pdf_data: bytes,
    filename: str,
    ocr_engine: TesseractOCR | None = None,
    options: OCROptions | None = None,
) -> ParsedDocument:
    """Run OCR on a scanned PDF and return a ParsedDocument.

    This is the main entry point for OCR processing. It:
    1. Detects which pages are scanned.
    2. Renders scanned pages to images.
    3. Runs OCR on each.
    4. Merges results into a ParsedDocument with provenance.

    Pages that already have extractable text are NOT re-OCR'd — their
    original text is preserved. This handles mixed text/scanned PDFs.
    """
    if ocr_engine is None:
        ocr_engine = TesseractOCR()
    if options is None:
        options = OCROptions()

    # 1. Detect scanned pages
    report = detect_scanned_pdf(pdf_data)
    log.info(
        "ocr.pdf.detect",
        filename=filename,
        total_pages=report.total_pages,
        scanned_pages=len(report.scanned_page_numbers),
    )

    pages: list[Page] = []
    parse_warnings: list[str] = []
    total_words = 0

    try:
        doc = fitz.open(stream=pdf_data, filetype="pdf")
    except Exception as e:
        return ParsedDocument(
            source_filename=filename,
            source_mime_type="application/pdf",
            parser_name="ocr.pipeline",
            parse_warnings=[f"failed to open PDF: {e}"],
        )

    for page_num in range(len(doc)):
        page = doc[page_num]
        page_number = page_num + 1
        page_width = page.rect.width
        page_height = page.rect.height

        detection = report.pages[page_num] if page_num < len(report.pages) else None

        if detection and not detection.is_scanned:
            # Page has extractable text — use it directly
            blocks = _extract_text_blocks(page, page_number)
            for b in blocks:
                total_words += len(b.text.split())
            pages.append(
                Page(
                    page_number=page_number,
                    blocks=blocks,
                    width=page_width,
                    height=page_height,
                )
            )
            continue

        # Scanned page — render and OCR
        png_bytes = render_pdf_page_to_image(pdf_data, page_number, dpi=options.render_dpi)
        if png_bytes is None:
            parse_warnings.append(f"failed to render page {page_number}")
            pages.append(
                Page(page_number=page_number, width=page_width, height=page_height)
            )
            continue

        # Run OCR
        req = OCRRequest(
            image=ImageInput(data=png_bytes, media_type="image/png"),
            languages=options.languages or ["eng"],
            with_layout=options.with_layout,
        )
        result = await ocr_engine.recognize(req)

        if result.confidence < options.min_confidence:
            parse_warnings.append(
                f"page {page_number}: low OCR confidence ({result.confidence:.2f})"
            )

        # Convert OCR result to blocks
        blocks = _ocr_result_to_blocks(result, page_number)
        for b in blocks:
            total_words += len(b.text.split())

        pages.append(
            Page(
                page_number=page_number,
                blocks=blocks,
                width=page_width,
                height=page_height,
            )
        )

    doc.close()

    metadata = DocumentMetadata(
        page_count=len(pages),
        word_count=total_words,
        char_count=sum(len(b.text) for p in pages for b in p.blocks),
        producer=f"ocr.pipeline ({ocr_engine.model_name})",
        extra={
            "ocr_scanned_pages": str(len(report.scanned_page_numbers)),
            "ocr_total_pages": str(report.total_pages),
            "ocr_engine": ocr_engine.model_name,
        },
    )

    return ParsedDocument(
        source_filename=filename,
        source_mime_type="application/pdf",
        pages=pages,
        metadata=metadata,
        parser_name="ocr.pipeline",
        parse_warnings=parse_warnings,
    )


async def ocr_image(
    image_data: bytes,
    filename: str,
    media_type: str,
    ocr_engine: TesseractOCR | None = None,
    options: OCROptions | None = None,
) -> ParsedDocument:
    """Run OCR on a standalone image (PNG/JPG/WEBP).

    Returns a ParsedDocument with a single page containing the OCR'd text.
    """
    if ocr_engine is None:
        ocr_engine = TesseractOCR()
    if options is None:
        options = OCROptions()

    req = OCRRequest(
        image=ImageInput(data=image_data, media_type=_normalize_media_type(media_type)),  # type: ignore[arg-type]
        languages=options.languages or ["eng"],
        with_layout=options.with_layout,
    )
    result = await ocr_engine.recognize(req)

    blocks = _ocr_result_to_blocks(result, page_number=1)
    total_words = sum(len(b.text) for b in blocks)

    # Get image dimensions
    try:
        img = Image.open(io.BytesIO(image_data))
        width, height = img.size
    except Exception:
        width, height = 0, 0

    page = Page(page_number=1, blocks=blocks, width=float(width), height=float(height))

    metadata = DocumentMetadata(
        page_count=1,
        word_count=total_words,
        char_count=sum(len(b.text) for b in blocks),
        producer=f"ocr.pipeline ({ocr_engine.model_name})",
        extra={
            "ocr_engine": ocr_engine.model_name,
            "ocr_confidence": f"{result.confidence:.3f}",
            "image_dimensions": f"{width}x{height}",
        },
    )

    parse_warnings: list[str] = []
    if result.confidence < (options.min_confidence if options else 0.5):
        parse_warnings.append(f"low OCR confidence: {result.confidence:.2f}")

    return ParsedDocument(
        source_filename=filename,
        source_mime_type=media_type,
        pages=[page],
        metadata=metadata,
        parser_name="ocr.pipeline",
        parse_warnings=parse_warnings,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _normalize_media_type(media_type: str) -> str:
    """Normalize a media type string to the OCR-accepted set."""
    mt = media_type.lower().strip()
    if "png" in mt:
        return "image/png"
    if "jpeg" in mt or "jpg" in mt:
        return "image/jpeg"
    if "webp" in mt:
        return "image/webp"
    return "image/png"  # default


def _extract_text_blocks(page: fitz.Page, page_number: int) -> list[Block]:
    """Extract text blocks from a PDF page that has real text."""
    blocks: list[Block] = []
    text_dict = page.get_text("dict")

    for b in text_dict.get("blocks", []):
        if b.get("type", 0) != 0:  # skip image blocks
            continue
        parts: list[str] = []
        for line in b.get("lines", []):
            line_text = ""
            for span in line.get("spans", []):
                line_text += span.get("text", "")
            parts.append(line_text)
        text = "\n".join(parts).strip()
        if not text:
            continue
        bbox = b.get("bbox", [0, 0, 0, 0])
        blocks.append(
            Block(
                kind="paragraph",
                text=text,
                page=page_number,
                bbox=BoundingBox(
                    x0=bbox[0], y0=bbox[1], x1=bbox[2], y1=bbox[3]
                ),
            )
        )
    return blocks


def _ocr_result_to_blocks(
    result: object, page_number: int
) -> list[Block]:
    """Convert an OCRResult to a list of Blocks.

    If the OCR result has layout blocks, use them. Otherwise, create
    paragraph blocks from the raw text.
    """
    from sovereign.models.schemas import OCRResult

    if not isinstance(result, OCRResult):
        return []

    blocks: list[Block] = []

    if result.blocks:
        for ocr_block in result.blocks:
            blocks.append(
                Block(
                    kind="paragraph",
                    text=ocr_block.text,
                    page=page_number,
                    bbox=BoundingBox(
                        x0=ocr_block.bbox[0],
                        y0=ocr_block.bbox[1],
                        x1=ocr_block.bbox[2],
                        y1=ocr_block.bbox[3],
                    ),
                )
            )
    elif result.lines:
        # Group lines into a single paragraph block
        text = "\n".join(ln.text for ln in result.lines)
        if text.strip():
            blocks.append(
                Block(
                    kind="paragraph",
                    text=text,
                    page=page_number,
                )
            )
    elif result.text.strip():
        # Fallback: just the raw text
        blocks.append(
            Block(
                kind="paragraph",
                text=result.text,
                page=page_number,
            )
        )

    return blocks
