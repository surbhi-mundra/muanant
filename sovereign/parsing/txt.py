"""TXT parser — preserves line structure and detects encoding."""

from __future__ import annotations

from typing import ClassVar

import chardet

from sovereign.parsing.model import Block, DocumentMetadata, Page, ParsedDocument


class TXTParser:
    """Parse plain text files with encoding detection."""

    NAME: ClassVar[str] = "txt.chardet"
    SUPPORTED: ClassVar[list[str]] = ["text/plain"]

    @property
    def name(self) -> str:
        return self.NAME

    def supported_mimes(self) -> list[str]:
        return list(self.SUPPORTED)

    def parse(self, data: bytes, filename: str = "") -> ParsedDocument:
        warnings: list[str] = []

        # Detect encoding
        detected = chardet.detect(data)
        encoding = detected.get("encoding") or "utf-8"
        confidence = detected.get("confidence") or 0
        if confidence < 0.7:
            warnings.append(f"low encoding confidence: {confidence:.2f} for {encoding}")

        try:
            text = data.decode(encoding, errors="replace")
        except (LookupError, UnicodeDecodeError):
            text = data.decode("utf-8", errors="replace")
            encoding = "utf-8"

        # Split into paragraphs (double newline) and preserve order
        blocks: list[Block] = []
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        total_words = 0

        for para in paragraphs:
            # Detect simple heading patterns: ALL CAPS short lines, or lines
            # ending with no period and < 80 chars
            is_heading = (
                len(para) < 100
                and para.isupper()
                and not para.endswith(".")
            )
            if is_heading:
                blocks.append(
                    Block(
                        kind="heading",
                        text=para,
                        section_path=[],
                        level=1,
                    )
                )
            else:
                total_words += len(para.split())
                blocks.append(
                    Block(
                        kind="paragraph",
                        text=para,
                        section_path=[],
                    )
                )

        metadata = DocumentMetadata(
            page_count=1,
            word_count=total_words,
            char_count=len(text),
            language="unknown",
            extra={"encoding": encoding},
        )

        # TXT has no pages — single synthetic page
        pages = [Page(page_number=1, blocks=blocks, is_synthetic=True)]

        return ParsedDocument(
            source_filename=filename,
            source_mime_type="text/plain",
            pages=pages,
            metadata=metadata,
            parser_name=self.NAME,
            parse_warnings=warnings,
        )
