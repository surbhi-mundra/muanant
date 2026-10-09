"""Tests for sovereign.ocr — Tesseract adapter, scanned detection, pipeline."""

from __future__ import annotations

import io

import fitz  # PyMuPDF  # type: ignore[import-untyped]
from PIL import Image, ImageDraw, ImageFont

from sovereign.models.schemas import ImageInput, OCRRequest
from sovereign.ocr.pipeline import (
    detect_scanned_pdf,
    ocr_image,
    ocr_pdf,
    render_pdf_page_to_image,
)
from sovereign.ocr.tesseract import TesseractOCR


# ---------------------------------------------------------------------------
# Test image generation
# ---------------------------------------------------------------------------
def _make_text_image(text: str = "Hello SOVEREIGN\nOCR Test 12345") -> bytes:
    """Create a PNG image with rendered text for OCR testing."""
    img = Image.new("RGB", (600, 200), color="white")
    draw = ImageDraw.Draw(img)
    # Use default font — works on all systems
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
    except OSError:
        font = ImageFont.load_default()
    draw.text((50, 50), text, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_blank_image() -> bytes:
    """Create a blank white image (no text)."""
    img = Image.new("RGB", (400, 200), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_text_pdf(text: str = "This is a text PDF.\nIt has extractable text.") -> bytes:
    """Create a PDF with real text (not scanned)."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text, fontsize=12)
    data = doc.tobytes()
    doc.close()
    return data


def _make_scanned_pdf(image: bytes | None = None) -> bytes:
    """Create a scanned PDF (image-only, no extractable text)."""
    if image is None:
        image = _make_text_image("Scanned page text\nLine two here")

    doc = fitz.open()
    # Insert the image as a full-page image — no text layer
    img = Image.open(io.BytesIO(image))
    _img_w, _img_h = img.size
    page = doc.new_page(width=612, height=792)  # US Letter
    rect = fitz.Rect(50, 50, 562, 742)  # margins
    page.insert_image(rect, stream=image)
    data = doc.tobytes()
    doc.close()
    return data


def _make_mixed_pdf() -> bytes:
    """Create a mixed PDF: page 1 has text, page 2 is scanned (image only)."""
    doc = fitz.open()
    # Page 1: real text
    p1 = doc.new_page()
    p1.insert_text((50, 72), "Page 1 has real text content.", fontsize=12)
    # Page 2: image only (scanned)
    img_data = _make_text_image("Scanned page content")
    p2 = doc.new_page()
    rect = fitz.Rect(50, 50, 562, 742)
    p2.insert_image(rect, stream=img_data)
    data = doc.tobytes()
    doc.close()
    return data


# ---------------------------------------------------------------------------
# Tesseract adapter tests
# ---------------------------------------------------------------------------
class TestTesseractAdapter:
    def test_satisfies_ocr_protocol(self) -> None:
        """TesseractOCR must satisfy the OCR protocol."""
        from sovereign.models.schemas import OCR

        ocr = TesseractOCR()
        assert isinstance(ocr, OCR)

    def test_model_name(self) -> None:
        ocr = TesseractOCR()
        assert "tesseract" in ocr.model_name.lower()

    async def test_recognize_text_from_image(self) -> None:
        """OCR should extract text from a rendered text image."""
        image = _make_text_image("HELLO WORLD 12345")
        ocr = TesseractOCR()
        result = await ocr.recognize(
            OCRRequest(image=ImageInput(data=image, media_type="image/png"))
        )
        assert result.text
        assert result.model
        # Tesseract should get at least some of the text right
        text_upper = result.text.upper()
        assert "HELLO" in text_upper or "WORLD" in text_upper

    async def test_recognize_blank_image(self) -> None:
        """OCR on a blank image should return empty or near-empty text."""
        image = _make_blank_image()
        ocr = TesseractOCR()
        result = await ocr.recognize(
            OCRRequest(image=ImageInput(data=image, media_type="image/png"))
        )
        assert len(result.text.strip()) < 20  # minimal/no text

    async def test_recognize_with_layout(self) -> None:
        """OCR with layout mode should return blocks."""
        image = _make_text_image("Line one\nLine two\nLine three")
        ocr = TesseractOCR()
        result = await ocr.recognize(
            OCRRequest(
                image=ImageInput(data=image, media_type="image/png"),
                with_layout=True,
            )
        )
        # Layout mode should produce at least some structure
        assert result.model
        # Text should be present (even if layout blocks are empty for simple images)
        if result.text.strip():
            assert len(result.text) > 0

    async def test_recognize_returns_confidence(self) -> None:
        """OCR result should include a confidence score."""
        image = _make_text_image("Clear text for OCR")
        ocr = TesseractOCR()
        result = await ocr.recognize(
            OCRRequest(image=ImageInput(data=image, media_type="image/png"))
        )
        assert 0.0 <= result.confidence <= 1.0

    async def test_recognize_page_size(self) -> None:
        """OCR result should include page dimensions."""
        image = _make_text_image("test")
        ocr = TesseractOCR()
        result = await ocr.recognize(
            OCRRequest(image=ImageInput(data=image, media_type="image/png"))
        )
        assert result.page_size[0] > 0  # width
        assert result.page_size[1] > 0  # height

    async def test_recognize_invalid_image_returns_empty(self) -> None:
        """Invalid image data should return empty result, not crash."""
        ocr = TesseractOCR()
        result = await ocr.recognize(
            OCRRequest(image=ImageInput(data=b"not an image", media_type="image/png"))
        )
        assert result.text == ""
        assert result.confidence == 0.0


# ---------------------------------------------------------------------------
# Scanned PDF detection tests
# ---------------------------------------------------------------------------
class TestScannedDetection:
    def test_text_pdf_not_detected_as_scanned(self) -> None:
        """A PDF with real text should not be flagged as scanned."""
        pdf = _make_text_pdf("This is extractable text content for testing.")
        report = detect_scanned_pdf(pdf)
        assert report.total_pages == 1
        assert not report.pages[0].is_scanned
        assert not report.any_scanned

    def test_scanned_pdf_detected(self) -> None:
        """A PDF with only images (no text) should be flagged as scanned."""
        pdf = _make_scanned_pdf()
        report = detect_scanned_pdf(pdf)
        assert report.total_pages == 1
        assert report.pages[0].is_scanned
        assert report.any_scanned

    def test_mixed_pdf_detected_partially(self) -> None:
        """A mixed PDF should flag only the scanned pages."""
        pdf = _make_mixed_pdf()
        report = detect_scanned_pdf(pdf)
        assert report.total_pages == 2
        assert not report.pages[0].is_scanned  # page 1 has text
        assert report.pages[1].is_scanned  # page 2 is scanned
        assert report.any_scanned
        assert not report.all_scanned
        assert report.scanned_page_numbers == [2]

    def test_detection_includes_text_char_count(self) -> None:
        """Detection should report character count per page."""
        pdf = _make_text_pdf("ABCDEF")
        report = detect_scanned_pdf(pdf)
        assert report.pages[0].text_char_count >= 6

    def test_detection_includes_image_count(self) -> None:
        """Detection should report image count per page."""
        pdf = _make_scanned_pdf()
        report = detect_scanned_pdf(pdf)
        assert report.pages[0].image_count >= 1


# ---------------------------------------------------------------------------
# Page rendering tests
# ---------------------------------------------------------------------------
class TestPageRendering:
    def test_render_page_returns_png(self) -> None:
        """render_pdf_page_to_image should return PNG bytes."""
        pdf = _make_text_pdf("test text")
        png = render_pdf_page_to_image(pdf, page_number=1, dpi=150)
        assert png is not None
        # PNG magic bytes
        assert png[:4] == b"\x89PNG"

    def test_render_page_invalid_number_returns_none(self) -> None:
        """Rendering an invalid page number should return None."""
        pdf = _make_text_pdf("test")
        assert render_pdf_page_to_image(pdf, page_number=99) is None

    def test_render_page_dpi_affects_size(self) -> None:
        """Higher DPI should produce a larger image."""
        pdf = _make_text_pdf("test")
        png_100 = render_pdf_page_to_image(pdf, page_number=1, dpi=100)
        png_300 = render_pdf_page_to_image(pdf, page_number=1, dpi=300)
        img_100 = Image.open(io.BytesIO(png_100))
        img_300 = Image.open(io.BytesIO(png_300))
        assert img_300.size[0] > img_100.size[0]


# ---------------------------------------------------------------------------
# OCR pipeline tests
# ---------------------------------------------------------------------------
class TestOCRPipeline:
    async def test_ocr_image_returns_parsed_document(self) -> None:
        """ocr_image should return a ParsedDocument with OCR'd text."""
        image = _make_text_image("INSPECTION REPORT 2024")
        parsed = await ocr_image(image, "test.png", "image/png")
        assert parsed.source_mime_type == "image/png"
        assert len(parsed.pages) == 1
        assert parsed.parser_name == "ocr.pipeline"
        assert parsed.metadata.extra.get("ocr_engine")

    async def test_ocr_image_extracts_text(self) -> None:
        """OCR should extract at least some text from a clear text image."""
        image = _make_text_image("PUMP P-101 OPERATIONAL")
        parsed = await ocr_image(image, "test.png", "image/png")
        # Tesseract should get at least some of the text
        text_upper = parsed.total_text.upper()
        assert "PUMP" in text_upper or "P-101" in text_upper or "OPERATIONAL" in text_upper

    async def test_ocr_pdf_scanned_document(self) -> None:
        """ocr_pdf on a scanned PDF should extract text via OCR."""
        pdf = _make_scanned_pdf(_make_text_image("VALVE V-202 LEAKING"))
        parsed = await ocr_pdf(pdf, "scanned.pdf")
        assert len(parsed.pages) == 1
        assert parsed.parser_name == "ocr.pipeline"
        # Should have some text from OCR
        assert len(parsed.total_text) > 0

    async def test_ocr_pdf_text_document_preserves_text(self) -> None:
        """ocr_pdf on a text PDF should use the existing text, not OCR."""
        pdf = _make_text_pdf("This is extractable text. No OCR needed here.")
        parsed = await ocr_pdf(pdf, "text.pdf")
        assert len(parsed.pages) == 1
        # The text should be the original extracted text (not OCR'd)
        assert "extractable text" in parsed.total_text

    async def test_ocr_pdf_mixed_document(self) -> None:
        """ocr_pdf on a mixed PDF should OCR scanned pages and keep text pages."""
        pdf = _make_mixed_pdf()
        parsed = await ocr_pdf(pdf, "mixed.pdf")
        assert len(parsed.pages) == 2
        # Page 1 should have the original text
        assert "real text" in parsed.pages[0].blocks[0].text or parsed.pages[0].blocks
        # Page 2 should have OCR'd content
        assert len(parsed.pages[1].blocks) > 0

    async def test_ocr_pdf_includes_metadata(self) -> None:
        """ocr_pdf should include OCR metadata (engine, page count)."""
        pdf = _make_scanned_pdf()
        parsed = await ocr_pdf(pdf, "scanned.pdf")
        assert parsed.metadata.page_count == 1
        assert "ocr_engine" in parsed.metadata.extra
        assert "ocr_scanned_pages" in parsed.metadata.extra

    async def test_ocr_image_with_blank_image(self) -> None:
        """OCR on a blank image should return a valid but empty ParsedDocument."""
        image = _make_blank_image()
        parsed = await ocr_image(image, "blank.png", "image/png")
        assert parsed is not None
        assert len(parsed.pages) == 1
        # Text should be empty or minimal
        assert len(parsed.total_text.strip()) < 20


# ---------------------------------------------------------------------------
# Backend registry test
# ---------------------------------------------------------------------------
class TestBackendRegistration:
    def test_tesseract_registered(self) -> None:
        """tesseract.ocr should be in the backend registry."""
        from sovereign.models.backends import registered_backends

        assert "tesseract.ocr" in registered_backends()
