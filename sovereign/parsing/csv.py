"""CSV parser — preserves header + row structure as a table."""

from __future__ import annotations

import csv
import io
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


class CSVParser:
    """Parse CSV files into a structured table."""

    NAME: ClassVar[str] = "csv.stdlib"
    SUPPORTED: ClassVar[list[str]] = ["text/csv"]

    @property
    def name(self) -> str:
        return self.NAME

    def supported_mimes(self) -> list[str]:
        return list(self.SUPPORTED)

    def parse(self, data: bytes, filename: str = "") -> ParsedDocument:
        warnings: list[str] = []

        # Detect encoding
        try:
            text = data.decode("utf-8-sig")  # handles BOM
        except UnicodeDecodeError:
            text = data.decode("latin-1", errors="replace")
            warnings.append("fell back to latin-1 encoding for CSV")

        # Detect delimiter (simple heuristic: comma vs semicolon vs tab)
        delimiter = ","
        first_line = text.split("\n")[0] if text else ""
        if first_line.count(";") > first_line.count(","):
            delimiter = ";"
        elif first_line.count("\t") > first_line.count(","):
            delimiter = "\t"

        rows: list[TableRow] = []
        total_cells = 0

        try:
            reader = csv.reader(io.StringIO(text), delimiter=delimiter)
            for i, row in enumerate(reader):
                if not row or all(not c.strip() for c in row):
                    continue
                cells = [TableCell(text=c.strip(), is_header=(i == 0)) for c in row]
                rows.append(TableRow(cells=cells))
                total_cells += len(cells)
        except csv.Error as e:
            warnings.append(f"CSV parse error: {e}")

        # Build markdown representation
        md_lines: list[str] = []
        if rows:
            md_lines.append("| " + " | ".join(c.text for c in rows[0].cells) + " |")
            md_lines.append("| " + " | ".join("---" for _ in rows[0].cells) + " |")
            for r in rows[1:]:
                md_lines.append("| " + " | ".join(c.text for c in r.cells) + " |")

        table = Table(rows=rows, markdown="\n".join(md_lines))

        blocks: list[Block] = [
            Block(
                kind="table",
                text=table.markdown or "",
                section_path=[],
                table=table,
            )
        ]

        metadata = DocumentMetadata(
            page_count=1,
            word_count=total_cells,
            char_count=len(text),
            extra={"delimiter": delimiter, "num_rows": str(len(rows))},
        )

        pages = [Page(page_number=1, blocks=blocks, is_synthetic=True)]

        return ParsedDocument(
            source_filename=filename,
            source_mime_type="text/csv",
            pages=pages,
            metadata=metadata,
            parser_name=self.NAME,
            parse_warnings=warnings,
        )
