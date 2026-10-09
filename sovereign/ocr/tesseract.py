"""Tesseract OCR adapter — real OCR via the tesseract binary.

Satisfies the ``OCR`` protocol from ``sovereign.models.schemas``.
Selected via ``configs/models.yaml`` when ``backend: tesseract.ocr``.

Requirements:
- ``tesseract`` binary on PATH (already installed in dev sandbox)
- ``pytesseract`` Python package
- ``Pillow`` for image handling

The adapter handles:
- PIL Images (from rendered PDF pages or direct image uploads)
- Raw image bytes (PNG/JPEG/WEBP)
- Optional language selection (e.g. ["eng", "deu"])
- Optional layout mode (with bounding boxes, reading order)

For production (Tier 2+), swap to Surya or PaddleOCR by editing
``configs/models.yaml`` — no code changes needed.
"""

from __future__ import annotations

import io
from typing import Any

import pytesseract
from PIL import Image, ImageEnhance, ImageFilter

from sovereign.core.logging import get_logger
from sovereign.models.schemas import (
    ImageInput,
    OCRBlock,
    OCRLine,
    OCRRequest,
    OCRResult,
    OCRWord,
)

log = get_logger(__name__)


class TesseractOCR:
    """Real OCR using the tesseract binary via pytesseract.

    Implements the ``OCR`` protocol from ``sovereign.models.schemas``.
    """

    def __init__(self, model_name: str = "tesseract-5.x") -> None:
        self._model_name = model_name

    @property
    def model_name(self) -> str:
        return self._model_name

    async def recognize(self, req: OCRRequest) -> OCRResult:
        """Run OCR on a single image.

        Returns an ``OCRResult`` with text, lines, words, and optional
        layout blocks. If ``with_layout`` is True, also extracts block-
        level structure (paragraphs, titles, captions).
        """
        # Load the image from the request
        pil_image = _to_pil_image(req.image)
        if pil_image is None:
            return OCRResult(text="", model=self._model_name, confidence=0.0)

        # Preprocess for better OCR accuracy
        pil_image = _preprocess_image(pil_image)

        lang = "+".join(req.languages) if req.languages else "eng"

        try:
            if req.with_layout:
                return _recognize_with_layout(pil_image, lang, self._model_name)
            # Simple text-only OCR
            return _recognize_simple(pil_image, lang, self._model_name)
        except Exception as e:
            log.error("ocr.tesseract.failed", error=str(e))
            return OCRResult(text="", model=self._model_name, confidence=0.0)


# ---------------------------------------------------------------------------
# Image loading
# ---------------------------------------------------------------------------
def _to_pil_image(img_input: ImageInput) -> Image.Image | None:
    """Convert an ImageInput to a PIL Image."""
    if img_input.data is not None:
        try:
            return Image.open(io.BytesIO(img_input.data))
        except Exception as e:
            log.error("ocr.image.load_failed", error=str(e))
            return None
    if img_input.path is not None:
        try:
            return Image.open(img_input.path)
        except Exception as e:
            log.error("ocr.image.load_failed", path=img_input.path, error=str(e))
            return None
    return None


# ---------------------------------------------------------------------------
# Image preprocessing
# ---------------------------------------------------------------------------
def _preprocess_image(img: Image.Image) -> Image.Image:
    """Preprocess image for better OCR accuracy.

    Steps:
    1. Convert to grayscale (color is noise for OCR)
    2. Upscale small images (tesseract works best >300 DPI equivalent)
    3. Increase contrast
    4. Slight sharpening
    5. Light noise reduction
    """
    # Convert to grayscale
    if img.mode != "L":
        img = img.convert("L")

    # Upscale if small (target ~2000px wide for decent OCR)
    w, h = img.size
    if w < 1000:
        scale = 1000 / w
        img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

    # Increase contrast
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.5)

    # Sharpen
    img = img.filter(ImageFilter.SHARPEN)

    return img


# ---------------------------------------------------------------------------
# Simple OCR (text only)
# ---------------------------------------------------------------------------
def _recognize_simple(
    img: Image.Image, lang: str, model_name: str
) -> OCRResult:
    """Run tesseract text-only OCR. Returns text + confidence."""
    # Get text
    text = pytesseract.image_to_string(img, lang=lang)

    # Get confidence data
    data: dict[str, Any] = pytesseract.image_to_data(
        img, lang=lang, output_type=pytesseract.Output.DICT
    )

    # Compute average confidence from word-level data
    confidences = [int(c) for c in data.get("conf", []) if int(c) > 0]
    avg_conf = sum(confidences) / len(confidences) / 100.0 if confidences else 0.0

    # Build lines from the data
    lines = _build_lines_from_tesseract_data(data)

    return OCRResult(
        text=text.strip(),
        lines=lines,
        confidence=avg_conf,
        model=model_name,
        page_size=img.size,
    )


# ---------------------------------------------------------------------------
# Layout OCR (with block structure)
# ---------------------------------------------------------------------------
def _recognize_with_layout(
    img: Image.Image, lang: str, model_name: str
) -> OCRResult:
    """Run tesseract with layout analysis. Returns blocks + lines + words."""
    # Get full data with bounding boxes
    data: dict[str, Any] = pytesseract.image_to_data(
        img, lang=lang, output_type=pytesseract.Output.DICT
    )

    # Group words into lines, then lines into blocks
    lines = _build_lines_from_tesseract_data(data)
    blocks = _build_blocks_from_lines(lines)

    # Plain text
    text = pytesseract.image_to_string(img, lang=lang)

    # Confidence
    confidences = [int(c) for c in data.get("conf", []) if int(c) > 0]
    avg_conf = sum(confidences) / len(confidences) / 100.0 if confidences else 0.0

    return OCRResult(
        text=text.strip(),
        lines=lines,
        blocks=blocks,
        confidence=avg_conf,
        model=model_name,
        page_size=img.size,
    )


def _build_lines_from_tesseract_data(data: dict[str, Any]) -> list[OCRLine]:
    """Group tesseract word-level data into OCRLine objects."""
    lines_map: dict[tuple[int, int], list[OCRWord]] = {}

    n = len(data.get("text", []))
    for i in range(n):
        text_val = data["text"][i].strip()
        if not text_val:
            continue
        conf = int(data["conf"][i])
        if conf < 0:
            continue

        block_num = data["block_num"][i]
        line_num = data["line_num"][i]
        key = (block_num, line_num)

        x = data["left"][i]
        y = data["top"][i]
        w = data["width"][i]
        h = data["height"][i]

        word = OCRWord(
            text=text_val,
            bbox=(float(x), float(y), float(x + w), float(y + h)),
            confidence=conf / 100.0,
        )
        lines_map.setdefault(key, []).append(word)

    result: list[OCRLine] = []
    for key in sorted(lines_map):
        words = lines_map[key]
        # Build line text from words
        line_text = " ".join(w.text for w in words)
        # Line bbox = union of word bboxes
        x0 = min(w.bbox[0] for w in words)
        y0 = min(w.bbox[1] for w in words)
        x1 = max(w.bbox[2] for w in words)
        y1 = max(w.bbox[3] for w in words)
        line_conf = sum(w.confidence for w in words) / len(words) if words else 0.0

        result.append(
            OCRLine(
                text=line_text,
                bbox=(x0, y0, x1, y1),
                confidence=line_conf,
                words=words,
            )
        )

    return result


def _build_blocks_from_lines(lines: list[OCRLine]) -> list[OCRBlock]:
    """Group lines into blocks (paragraphs). Simple heuristic: lines with
    similar y-coordinates and small vertical gaps form a block.
    """
    if not lines:
        return []

    blocks: list[OCRBlock] = []
    current_lines: list[OCRLine] = [lines[0]]

    for line in lines[1:]:
        prev = current_lines[-1]
        # If vertical gap is > 1.5x line height, start a new block
        prev_height = prev.bbox[3] - prev.bbox[1]
        gap = line.bbox[1] - prev.bbox[3]
        if gap > prev_height * 0.8:
            blocks.append(_lines_to_block(current_lines, "text"))
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        blocks.append(_lines_to_block(current_lines, "text"))

    return blocks


def _lines_to_block(lines: list[OCRLine], kind: str) -> OCRBlock:
    """Build an OCRBlock from a list of OCRLines."""
    text = "\n".join(ln.text for ln in lines)
    x0 = min(ln.bbox[0] for ln in lines)
    y0 = min(ln.bbox[1] for ln in lines)
    x1 = max(ln.bbox[2] for ln in lines)
    y1 = max(ln.bbox[3] for ln in lines)
    conf = sum(ln.confidence for ln in lines) / len(lines) if lines else 0.0

    return OCRBlock(
        kind=kind,  # type: ignore[arg-type]
        text=text,
        bbox=(x0, y0, x1, y1),
        confidence=conf,
        lines=lines,
    )
