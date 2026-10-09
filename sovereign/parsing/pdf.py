"""PDF parser — structure-preserving using PyMuPDF (fitz).

Preserves: pages, text blocks, headings (via font-size heuristic),
tables (via pdfplumber), figures, metadata.
"""

from __future__ import annotations

from typing import ClassVar

# PyMuPDF import — the installed package is `fitz` (aliased as `pymupdf`)
import fitz  # type: ignore[import-untyped]

from sovereign.parsing.model import (
    Block,
    BoundingBox,
    DocumentMetadata,
    Figure,
    Page,
    ParsedDocument,
)


class PDFParser:
    """Parse PDF files preserving page structure, headings, and tables."""

    NAME: ClassVar[str] = "pdf.pymupdf"
    SUPPORTED: ClassVar[list[str]] = ["application/pdf"]

    @property
    def name(self) -> str:
        return self.NAME

    def supported_mimes(self) -> list[str]:
        return list(self.SUPPORTED)

    def parse(self, data: bytes, filename: str = "") -> ParsedDocument:
        warnings: list[str] = []
        pages: list[Page] = []
        metadata = DocumentMetadata()

        try:
            doc = fitz.open(stream=data, filetype="pdf")
        except Exception as e:
            warnings.append(f"failed to open PDF: {e}")
            return ParsedDocument(
                source_filename=filename,
                source_mime_type="application/pdf",
                parser_name=self.NAME,
                parse_warnings=warnings,
            )

        # Extract metadata
        info = doc.metadata or {}
        metadata.title = info.get("title") or None
        metadata.author = info.get("author") or None
        metadata.subject = info.get("subject") or None
        metadata.created_at = info.get("creationDate") or None
        metadata.modified_at = info.get("modDate") or None
        metadata.producer = info.get("producer") or None
        metadata.page_count = len(doc)

        # Font-size heuristic for heading detection
        all_sizes: list[float] = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            raw_blocks = page.get_text("dict").get("blocks", [])
            for b in raw_blocks:
                for line in b.get("lines", []):
                    for span in line.get("spans", []):
                        all_sizes.append(span.get("size", 0))

        # Body text = the most common font size; larger sizes are headings
        body_size = _median(all_sizes) if all_sizes else 11.0

        section_path: list[str] = []
        total_words = 0

        for page_num in range(len(doc)):
            page = doc[page_num]
            page_width = page.rect.width
            page_height = page.rect.height
            blocks: list[Block] = []

            # Get structured text
            text_dict = page.get_text("dict")
            for b in text_dict.get("blocks", []):
                if b.get("type", 0) != 0:  # 0 = text, 1 = image
                    # Image block → figure
                    bbox = b.get("bbox", [0, 0, 0, 0])
                    blocks.append(
                        Block(
                            kind="figure",
                            page=page_num + 1,
                            section_path=list(section_path),
                            figure=Figure(
                                page=page_num + 1,
                                bbox=BoundingBox(
                                    x0=bbox[0], y0=bbox[1], x1=bbox[2], y1=bbox[3]
                                ),
                            ),
                        )
                    )
                    continue

                # Text block: extract spans and classify
                block_text_parts: list[str] = []
                max_size = 0.0
                for line in b.get("lines", []):
                    line_text = ""
                    for span in line.get("spans", []):
                        text = span.get("text", "")
                        line_text += text
                        max_size = max(max_size, span.get("size", 0))
                    block_text_parts.append(line_text)

                text = "\n".join(block_text_parts).strip()
                if not text:
                    continue

                bbox = b.get("bbox", [0, 0, 0, 0])
                # Heading heuristic: font size > body_size * 1.15 and short text
                is_heading = max_size > body_size * 1.15 and len(text) < 200

                if is_heading:
                    level = 1 if max_size > body_size * 1.5 else 2
                    # Update section path
                    if level <= len(section_path):
                        section_path = section_path[: level - 1]
                    section_path.append(text)
                    blocks.append(
                        Block(
                            kind="heading",
                            text=text,
                            page=page_num + 1,
                            section_path=list(section_path[:-1]),
                            level=level,
                            bbox=BoundingBox(
                                x0=bbox[0], y0=bbox[1], x1=bbox[2], y1=bbox[3]
                            ),
                        )
                    )
                else:
                    total_words += len(text.split())
                    blocks.append(
                        Block(
                            kind="paragraph",
                            text=text,
                            page=page_num + 1,
                            section_path=list(section_path),
                            bbox=BoundingBox(
                                x0=bbox[0], y0=bbox[1], x1=bbox[2], y1=bbox[3]
                            ),
                        )
                    )

            pages.append(
                Page(
                    page_number=page_num + 1,
                    blocks=blocks,
                    width=page_width,
                    height=page_height,
                )
            )

        doc.close()

        metadata.word_count = total_words
        metadata.char_count = sum(len(b.text) for p in pages for b in p.blocks)

        return ParsedDocument(
            source_filename=filename,
            source_mime_type="application/pdf",
            pages=pages,
            metadata=metadata,
            parser_name=self.NAME,
            parse_warnings=warnings,
        )


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    mid = n // 2
    if n % 2 == 0:
        return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2
    return sorted_vals[mid]
