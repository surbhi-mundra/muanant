"""XLSX parser — preserves sheet names and cell structure as tables."""

from __future__ import annotations

import io
from typing import Any, ClassVar

import openpyxl  # type: ignore[import-untyped]

from sovereign.parsing.model import (
    Block,
    DocumentMetadata,
    Page,
    ParsedDocument,
    Table,
    TableCell,
    TableRow,
)


class XLSXParser:
    """Parse XLSX files preserving each sheet as a table block."""

    NAME: ClassVar[str] = "xlsx.openpyxl"
    SUPPORTED: ClassVar[list[str]] = [
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]

    @property
    def name(self) -> str:
        return self.NAME

    def supported_mimes(self) -> list[str]:
        return list(self.SUPPORTED)

    def parse(self, data: bytes, filename: str = "") -> ParsedDocument:
        warnings: list[str] = []
        blocks: list[Block] = []

        try:
            wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        except Exception as e:
            warnings.append(f"failed to open XLSX: {e}")
            return ParsedDocument(
                source_filename=filename,
                source_mime_type=self.SUPPORTED[0],
                parser_name=self.NAME,
                parse_warnings=warnings,
            )

        total_cells = 0
        sheet_names: list[str] = []

        for sheet_name in wb.sheetnames:
            sheet_names.append(sheet_name)
            ws = wb[sheet_name]
            rows: list[TableRow] = []

            for i, row in enumerate(ws.iter_rows(values_only=True)):
                # Skip completely empty rows
                if all(v is None or (isinstance(v, str) and not v.strip()) for v in row):
                    continue
                cells = []
                for cell_val in row:
                    text_val = _cell_to_str(cell_val)
                    cells.append(
                        TableCell(
                            text=text_val,
                            is_header=(i == 0),
                        )
                    )
                    if text_val:
                        total_cells += 1
                rows.append(TableRow(cells=cells))

            # Build markdown
            md_lines: list[str] = []
            if rows:
                md_lines.append("| " + " | ".join(c.text for c in rows[0].cells) + " |")
                md_lines.append("| " + " | ".join("---" for _ in rows[0].cells) + " |")
                for r in rows[1:]:
                    md_lines.append("| " + " | ".join(c.text for c in r.cells) + " |")

            table = Table(
                rows=rows,
                markdown="\n".join(md_lines),
                caption=f"Sheet: {sheet_name}",
            )

            blocks.append(
                Block(
                    kind="table",
                    text=table.markdown or "",
                    section_path=[sheet_name],
                    table=table,
                )
            )

        wb.close()

        metadata = DocumentMetadata(
            page_count=len(sheet_names),
            word_count=total_cells,
            char_count=total_cells,
            extra={"sheets": ",".join(sheet_names)},
        )

        # XLSX: one synthetic "page" per sheet would be ideal, but for
        # simplicity we put all sheet-tables in one page. The chunker will
        # separate them.
        pages = [Page(page_number=1, blocks=blocks, is_synthetic=True)]

        return ParsedDocument(
            source_filename=filename,
            source_mime_type=self.SUPPORTED[0],
            pages=pages,
            metadata=metadata,
            parser_name=self.NAME,
            parse_warnings=warnings,
        )


def _cell_to_str(val: Any) -> str:
    """Convert an XLSX cell value to string."""
    if val is None:
        return ""
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    if isinstance(val, float):
        # Avoid trailing .0 for integer-valued floats
        if val == int(val):
            return str(int(val))
        return str(val)
    if isinstance(val, int):
        return str(val)
    return str(val).strip()
