"""Tests for sovereign.parsing — all parsers."""

from __future__ import annotations

import io

import docx
import pytest
from openpyxl import Workbook

from sovereign.parsing.csv import CSVParser
from sovereign.parsing.markdown import MarkdownParser

# PDF parser tests are optional — they need PyMuPDF which is installed
from sovereign.parsing.pdf import PDFParser
from sovereign.parsing.registry import get_parser, parse_document, supported_mimes
from sovereign.parsing.txt import TXTParser
from sovereign.parsing.xlsx import XLSXParser


# ---------------------------------------------------------------------------
# Fixtures: create test documents
# ---------------------------------------------------------------------------
@pytest.fixture
def txt_bytes() -> bytes:
    return (
        b"Introduction\n\nThis is a test document.\n"
        b"It has multiple paragraphs.\n\nCONCLUSION\n\nThe end."
    )


@pytest.fixture
def md_bytes() -> bytes:
    return b"""# Main Title

## Section 1

This is a paragraph under section 1.

- Item 1
- Item 2

## Section 2

| Col A | Col B |
|-------|-------|
| 1     | 2     |
| 3     | 4     |

```python
print("hello")
```

> A blockquote.

Final paragraph.
"""


@pytest.fixture
def csv_bytes() -> bytes:
    return b"Name,Age,City\nAlice,30,NYC\nBob,25,LA\nCarol,35,Chicago\n"


@pytest.fixture
def xlsx_bytes() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Data"
    ws.append(["Name", "Value"])
    ws.append(["Alpha", 100])
    ws.append(["Beta", 200])
    ws2 = wb.create_sheet("Summary")
    ws2.append(["Total", 300])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture
def docx_bytes() -> bytes:
    doc = docx.Document()
    doc.add_heading("Document Title", 0)
    doc.add_heading("Section 1", 1)
    doc.add_paragraph("First paragraph in section 1.")
    doc.add_paragraph("Second paragraph in section 1.")
    doc.add_heading("Subsection 1.1", 2)
    doc.add_paragraph("Content in subsection.")
    # Add a table
    table = doc.add_table(rows=3, cols=2)
    table.style = "Table Grid"
    for i, (a, b) in enumerate([("Header A", "Header B"), ("1", "2"), ("3", "4")]):
        table.rows[i].cells[0].text = a
        table.rows[i].cells[1].text = b
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


@pytest.fixture
def pdf_bytes() -> bytes:
    """Create a minimal PDF with PyMuPDF."""
    import fitz

    doc = fitz.open()  # new empty PDF
    page = doc.new_page()
    page.insert_text((50, 72), "Document Title", fontsize=18)
    page.insert_text((50, 120), "This is a paragraph of body text.", fontsize=11)
    page.insert_text((50, 140), "Another paragraph here.", fontsize=11)
    page2 = doc.new_page()
    page2.insert_text((50, 72), "Page 2 heading", fontsize=14)
    page2.insert_text((50, 120), "Content on page 2.", fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
def test_supported_mimes_includes_all_formats() -> None:
    mimes = supported_mimes()
    assert "text/plain" in mimes
    assert "text/markdown" in mimes
    assert "text/csv" in mimes
    assert "application/pdf" in mimes
    assert any("wordprocessingml" in m for m in mimes)
    assert any("spreadsheetml" in m for m in mimes)


# ---------------------------------------------------------------------------
# TXT parser
# ---------------------------------------------------------------------------
def test_txt_parser_extracts_paragraphs(txt_bytes: bytes) -> None:
    parser = TXTParser()
    doc = parser.parse(txt_bytes, "test.txt")
    assert doc.source_mime_type == "text/plain"
    assert len(doc.pages) == 1
    paragraphs = [b for b in doc.all_blocks if b.kind == "paragraph"]
    assert len(paragraphs) >= 2
    # "Introduction" is not all-caps, so it's a paragraph (correct behavior)
    full_text = " ".join(p.text for p in paragraphs)
    assert "test document" in full_text.lower()
    assert "Introduction" in full_text


def test_txt_parser_detects_caps_headings(txt_bytes: bytes) -> None:
    parser = TXTParser()
    doc = parser.parse(txt_bytes, "test.txt")
    headings = [b for b in doc.all_blocks if b.kind == "heading"]
    assert len(headings) >= 1
    assert any("CONCLUSION" in h.text for h in headings)


def test_txt_parser_metadata(txt_bytes: bytes) -> None:
    parser = TXTParser()
    doc = parser.parse(txt_bytes, "test.txt")
    assert doc.metadata.word_count is not None
    assert doc.metadata.word_count > 0
    assert doc.metadata.char_count is not None


# ---------------------------------------------------------------------------
# Markdown parser
# ---------------------------------------------------------------------------
def test_md_parser_extracts_headings(md_bytes: bytes) -> None:
    parser = MarkdownParser()
    doc = parser.parse(md_bytes, "test.md")
    headings = doc.headings
    assert len(headings) >= 3
    assert any(h.text == "Main Title" for h in headings)
    assert any(h.text == "Section 1" for h in headings)
    assert any(h.text == "Section 2" for h in headings)


def test_md_parser_heading_levels(md_bytes: bytes) -> None:
    parser = MarkdownParser()
    doc = parser.parse(md_bytes, "test.md")
    h1 = [h for h in doc.headings if h.level == 1]
    h2 = [h for h in doc.headings if h.level == 2]
    assert len(h1) >= 1
    assert len(h2) >= 2


def test_md_parser_extracts_list_items(md_bytes: bytes) -> None:
    parser = MarkdownParser()
    doc = parser.parse(md_bytes, "test.md")
    list_items = [b for b in doc.all_blocks if b.kind == "list_item"]
    assert len(list_items) >= 2
    assert any("Item 1" in b.text for b in list_items)


def test_md_parser_extracts_table(md_bytes: bytes) -> None:
    parser = MarkdownParser()
    doc = parser.parse(md_bytes, "test.md")
    tables = doc.tables
    assert len(tables) >= 1
    assert tables[0].num_rows >= 3  # header + 2 data rows
    assert tables[0].num_cols >= 2


def test_md_parser_extracts_code_block(md_bytes: bytes) -> None:
    parser = MarkdownParser()
    doc = parser.parse(md_bytes, "test.md")
    code_blocks = [b for b in doc.all_blocks if b.kind == "code"]
    assert len(code_blocks) >= 1
    assert "print" in code_blocks[0].text


def test_md_parser_extracts_blockquote(md_bytes: bytes) -> None:
    parser = MarkdownParser()
    doc = parser.parse(md_bytes, "test.md")
    quotes = [b for b in doc.all_blocks if b.kind == "quote"]
    assert len(quotes) >= 1
    assert "blockquote" in quotes[0].text.lower()


def test_md_parser_section_path(md_bytes: bytes) -> None:
    parser = MarkdownParser()
    doc = parser.parse(md_bytes, "test.md")
    # Paragraphs under "Section 1" should have it in their section_path
    paras = [b for b in doc.all_blocks if b.kind == "paragraph"]
    section1_paras = [p for p in paras if "Section 1" in p.section_path]
    assert len(section1_paras) >= 1


# ---------------------------------------------------------------------------
# CSV parser
# ---------------------------------------------------------------------------
def test_csv_parser_extracts_table(csv_bytes: bytes) -> None:
    parser = CSVParser()
    doc = parser.parse(csv_bytes, "test.csv")
    assert doc.source_mime_type == "text/csv"
    tables = doc.tables
    assert len(tables) == 1
    assert tables[0].num_rows == 4  # header + 3 data
    assert tables[0].num_cols == 3
    # First row is header
    assert tables[0].rows[0].cells[0].text == "Name"
    assert tables[0].rows[0].cells[0].is_header


def test_csv_parser_markdown(csv_bytes: bytes) -> None:
    parser = CSVParser()
    doc = parser.parse(csv_bytes, "test.csv")
    md = doc.tables[0].markdown
    assert "| Name |" in md
    assert "| Alice |" in md


# ---------------------------------------------------------------------------
# XLSX parser
# ---------------------------------------------------------------------------
def test_xlsx_parser_extracts_sheets(xlsx_bytes: bytes) -> None:
    parser = XLSXParser()
    doc = parser.parse(xlsx_bytes, "test.xlsx")
    tables = doc.tables
    assert len(tables) == 2  # two sheets
    # First table = "Data" sheet
    assert "Data" in tables[0].caption
    assert tables[0].num_rows >= 3  # header + 2 data
    assert tables[0].num_cols == 2


def test_xlsx_parser_cell_values(xlsx_bytes: bytes) -> None:
    parser = XLSXParser()
    doc = parser.parse(xlsx_bytes, "test.xlsx")
    data_table = doc.tables[0]
    # Header row
    assert data_table.rows[0].cells[0].text == "Name"
    assert data_table.rows[0].cells[1].text == "Value"
    # Data rows
    assert data_table.rows[1].cells[0].text == "Alpha"
    assert data_table.rows[1].cells[1].text == "100"  # int → str, no .0


# ---------------------------------------------------------------------------
# DOCX parser
# ---------------------------------------------------------------------------
def test_docx_parser_extracts_headings(docx_bytes: bytes) -> None:
    parser = get_parser(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    doc = parser.parse(docx_bytes, "test.docx")
    headings = doc.headings
    assert len(headings) >= 3
    assert any("Document Title" in h.text for h in headings)
    assert any("Section 1" in h.text for h in headings)
    assert any("Subsection 1.1" in h.text for h in headings)


def test_docx_parser_extracts_paragraphs(docx_bytes: bytes) -> None:
    parser = get_parser(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    doc = parser.parse(docx_bytes, "test.docx")
    paras = [b for b in doc.all_blocks if b.kind == "paragraph"]
    assert len(paras) >= 3
    assert any("First paragraph" in p.text for p in paras)


def test_docx_parser_extracts_table(docx_bytes: bytes) -> None:
    parser = get_parser(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    doc = parser.parse(docx_bytes, "test.docx")
    tables = doc.tables
    assert len(tables) >= 1
    assert tables[0].num_rows == 3
    assert tables[0].num_cols == 2
    assert tables[0].rows[0].cells[0].text == "Header A"


def test_docx_parser_section_path(docx_bytes: bytes) -> None:
    parser = get_parser(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    doc = parser.parse(docx_bytes, "test.docx")
    # "Content in subsection" should be under Section 1 > Subsection 1.1
    content_blocks = [b for b in doc.all_blocks if "Content in subsection" in b.text]
    assert len(content_blocks) == 1
    assert "Section 1" in content_blocks[0].section_path
    assert "Subsection 1.1" in content_blocks[0].section_path


def test_docx_parser_metadata(docx_bytes: bytes) -> None:
    parser = get_parser(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    doc = parser.parse(docx_bytes, "test.docx")
    assert doc.metadata.word_count is not None
    assert doc.metadata.word_count > 0


# ---------------------------------------------------------------------------
# PDF parser
# ---------------------------------------------------------------------------
def test_pdf_parser_extracts_pages(pdf_bytes: bytes) -> None:
    parser = PDFParser()
    doc = parser.parse(pdf_bytes, "test.pdf")
    assert doc.source_mime_type == "application/pdf"
    assert len(doc.pages) == 2
    assert doc.pages[0].page_number == 1
    assert doc.pages[1].page_number == 2


def test_pdf_parser_extracts_text(pdf_bytes: bytes) -> None:
    parser = PDFParser()
    doc = parser.parse(pdf_bytes, "test.pdf")
    all_text = doc.total_text
    assert "Document Title" in all_text
    assert "paragraph of body text" in all_text
    assert "Page 2" in all_text


def test_pdf_parser_metadata(pdf_bytes: bytes) -> None:
    parser = PDFParser()
    doc = parser.parse(pdf_bytes, "test.pdf")
    assert doc.metadata.page_count == 2
    assert doc.metadata.word_count is not None
    assert doc.metadata.word_count > 0


def test_pdf_parser_detects_headings(pdf_bytes: bytes) -> None:
    parser = PDFParser()
    doc = parser.parse(pdf_bytes, "test.pdf")
    headings = doc.headings
    # The 18pt "Document Title" should be detected as a heading
    assert len(headings) >= 1
    assert any("Document Title" in h.text for h in headings)


# ---------------------------------------------------------------------------
# Registry dispatcher
# ---------------------------------------------------------------------------
def test_parse_document_dispatches_by_mime(txt_bytes: bytes, md_bytes: bytes) -> None:
    doc_txt = parse_document(txt_bytes, "test.txt", "text/plain")
    assert doc_txt.parser_name == "txt.chardet"
    doc_md = parse_document(md_bytes, "test.md", "text/markdown")
    assert doc_md.parser_name == "markdown.lightweight"
