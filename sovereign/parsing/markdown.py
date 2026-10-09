"""Markdown parser — preserves heading hierarchy, lists, code blocks, tables.

Uses a lightweight line-by-line parser (no external `markdown` dep needed).
The goal is structure extraction, not HTML rendering.
"""

from __future__ import annotations

import re
from typing import ClassVar

from sovereign.parsing.model import (
    Block,
    DocumentMetadata,
    Page,
    ParsedDocument,
    Table,
    TableCell,
    TableRow,
)

# Heading: # Title, ## Subtitle, etc.
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
# List item: - item, * item, 1. item
_LIST_RE = re.compile(r"^\s*([-*+]|\d+\.)\s+(.+)$")
# Code fence: ```
_CODE_FENCE_RE = re.compile(r"^```(\w*)$")
# Table row: | cell | cell |
_TABLE_ROW_RE = re.compile(r"^\|(.+)\|$")
# Table separator: | --- | --- |
_TABLE_SEP_RE = re.compile(r"^\|[\s:|-]+\|$")
# Blockquote: > text
_QUOTE_RE = re.compile(r"^>\s*(.*)$")


class MarkdownParser:
    """Parse Markdown preserving heading hierarchy, lists, code, tables."""

    NAME: ClassVar[str] = "markdown.lightweight"
    SUPPORTED: ClassVar[list[str]] = ["text/markdown", "text/x-markdown"]

    @property
    def name(self) -> str:
        return self.NAME

    def supported_mimes(self) -> list[str]:
        return list(self.SUPPORTED)

    def parse(self, data: bytes, filename: str = "") -> ParsedDocument:
        warnings: list[str] = []
        try:
            text = data.decode("utf-8", errors="replace")
        except Exception:
            text = data.decode("latin-1", errors="replace")

        lines = text.split("\n")
        blocks: list[Block] = []
        section_path: list[str] = []
        total_words = 0

        i = 0
        while i < len(lines):
            line = lines[i]

            # Code fence
            code_match = _CODE_FENCE_RE.match(line)
            if code_match:
                _lang = code_match.group(1)
                code_lines: list[str] = []
                i += 1
                while i < len(lines) and not lines[i].startswith("```"):
                    code_lines.append(lines[i])
                    i += 1
                blocks.append(
                    Block(
                        kind="code",
                        text="\n".join(code_lines),
                        section_path=list(section_path),
                    )
                )
                total_words += len(code_lines)
                i += 1
                continue

            # Heading
            heading_match = _HEADING_RE.match(line)
            if heading_match:
                level = len(heading_match.group(1))
                text_val = heading_match.group(2).strip()
                if level <= len(section_path):
                    section_path = section_path[:level]
                while len(section_path) < level - 1:
                    section_path.append("")
                if level - 1 < len(section_path):
                    section_path[level - 1] = text_val
                else:
                    section_path.append(text_val)
                blocks.append(
                    Block(
                        kind="heading",
                        text=text_val,
                        section_path=list(section_path[: level - 1]),
                        level=level,
                    )
                )
                i += 1
                continue

            # Table (look-ahead for separator line)
            if _TABLE_ROW_RE.match(line) and i + 1 < len(lines) and _TABLE_SEP_RE.match(
                lines[i + 1]
            ):
                table, consumed = _parse_md_table(lines, i)
                blocks.append(
                    Block(
                        kind="table",
                        text=table.markdown or "",
                        section_path=list(section_path),
                        table=table,
                    )
                )
                i += consumed
                continue

            # List item
            list_match = _LIST_RE.match(line)
            if list_match:
                blocks.append(
                    Block(
                        kind="list_item",
                        text=list_match.group(2).strip(),
                        section_path=list(section_path),
                    )
                )
                total_words += len(list_match.group(2).split())
                i += 1
                continue

            # Blockquote
            quote_match = _QUOTE_RE.match(line)
            if quote_match:
                blocks.append(
                    Block(
                        kind="quote",
                        text=quote_match.group(1).strip(),
                        section_path=list(section_path),
                    )
                )
                total_words += len(quote_match.group(1).split())
                i += 1
                continue

            # Paragraph (collect consecutive non-empty, non-structural lines)
            if line.strip():
                para_lines: list[str] = []
                while i < len(lines):
                    src_line = lines[i]
                    if not src_line.strip():
                        break
                    if (
                        _HEADING_RE.match(src_line)
                        or _LIST_RE.match(src_line)
                        or _CODE_FENCE_RE.match(src_line)
                        or _TABLE_ROW_RE.match(src_line)
                        or _QUOTE_RE.match(src_line)
                    ):
                        break
                    para_lines.append(src_line)
                    i += 1
                para_text = " ".join(para_lines).strip()
                if para_text:
                    total_words += len(para_text.split())
                    blocks.append(
                        Block(
                            kind="paragraph",
                            text=para_text,
                            section_path=list(section_path),
                        )
                    )
                continue

            i += 1  # skip empty line

        metadata = DocumentMetadata(
            page_count=1,
            word_count=total_words,
            char_count=len(text),
        )

        pages = [Page(page_number=1, blocks=blocks, is_synthetic=True)]

        return ParsedDocument(
            source_filename=filename,
            source_mime_type="text/markdown",
            pages=pages,
            metadata=metadata,
            parser_name=self.NAME,
            parse_warnings=warnings,
        )


def _parse_md_table(lines: list[str], start: int) -> tuple[Table, int]:
    """Parse a markdown table starting at ``lines[start]``.

    Returns (Table, lines_consumed).
    """
    rows: list[TableRow] = []

    # Simple approach: split each row on | and strip
    raw_cells = lines[start].strip().strip("|").split("|")
    header_cells = [c.strip() for c in raw_cells]
    rows.append(
        TableRow(cells=[TableCell(text=c, is_header=True) for c in header_cells])
    )

    i = start + 2  # skip header + separator
    while i < len(lines) and _TABLE_ROW_RE.match(lines[i]):
        raw = lines[i].strip().strip("|").split("|")
        cells = [c.strip() for c in raw]
        rows.append(TableRow(cells=[TableCell(text=c) for c in cells]))
        i += 1

    # Build markdown
    md_lines: list[str] = []
    if rows:
        md_lines.append("| " + " | ".join(c.text for c in rows[0].cells) + " |")
        md_lines.append("| " + " | ".join("---" for _ in rows[0].cells) + " |")
        for r in rows[1:]:
            md_lines.append("| " + " | ".join(c.text for c in r.cells) + " |")

    return Table(rows=rows, markdown="\n".join(md_lines)), i - start
