"""Tests for sovereign.parsing.chunking."""

from __future__ import annotations

from sovereign.parsing.chunking import Chunker
from sovereign.parsing.model import (
    Block,
    DocumentMetadata,
    Page,
    ParsedDocument,
    Table,
    TableCell,
    TableRow,
)


def _make_doc(blocks: list[Block], pages: int = 1) -> ParsedDocument:
    """Build a minimal ParsedDocument from a list of blocks."""
    pages_list = []
    for i in range(pages):
        page_blocks = [b for b in blocks if b.page == i + 1 or (b.page is None and i == 0)]
        pages_list.append(Page(page_number=i + 1, blocks=page_blocks, is_synthetic=True))
    return ParsedDocument(
        document_id="doc_test",
        project_id="proj_test",
        source_filename="test.txt",
        source_mime_type="text/plain",
        pages=pages_list,
        metadata=DocumentMetadata(page_count=pages),
    )


def test_chunker_produces_at_least_one_chunk() -> None:
    """A document with content must produce at least one chunk."""
    doc = _make_doc([
        Block(kind="paragraph", text="This is a test paragraph with enough words " * 5),
    ])
    chunks = Chunker().chunk(doc)
    assert len(chunks) >= 1
    assert chunks[0].text
    assert chunks[0].document_id == "doc_test"


def test_chunker_respects_heading_boundaries() -> None:
    """A new heading should start a new chunk."""
    doc = _make_doc([
        Block(kind="heading", text="Section 1", level=1, section_path=[]),
        Block(kind="paragraph", text="Content of section 1 " * 20),
        Block(kind="heading", text="Section 2", level=1, section_path=["Section 1"]),
        Block(kind="paragraph", text="Content of section 2 " * 20),
    ])
    chunks = Chunker(target_words=50, max_words=100).chunk(doc)
    assert len(chunks) >= 2
    # First chunk should contain "Section 1"
    assert "Section 1" in chunks[0].text
    # A later chunk should contain "Section 2"
    assert any("Section 2" in c.text for c in chunks)


def test_chunker_emits_tables_as_standalone() -> None:
    """Table blocks should become standalone chunks."""
    table = Table(
        rows=[
            TableRow(
                cells=[
                    TableCell(text="A", is_header=True),
                    TableCell(text="B", is_header=True),
                ]
            ),
            TableRow(cells=[TableCell(text="1"), TableCell(text="2")]),
        ],
        markdown="| A | B |\n|---|---|\n| 1 | 2 |",
    )
    doc = _make_doc([
        Block(kind="paragraph", text="Intro paragraph " * 10),
        Block(kind="table", text=table.markdown, table=table),
        Block(kind="paragraph", text="After table " * 10),
    ])
    chunks = Chunker().chunk(doc)
    table_chunks = [c for c in chunks if "table" in c.block_kinds]
    assert len(table_chunks) == 1
    assert "| A | B |" in table_chunks[0].text


def test_chunker_preserves_provenance() -> None:
    """Each chunk must carry page number and section path."""
    doc = _make_doc([
        Block(kind="heading", text="Chapter 1", level=1, page=1, section_path=[]),
        Block(kind="paragraph", text="Content here " * 20, page=1, section_path=["Chapter 1"]),
    ])
    chunks = Chunker().chunk(doc)
    assert len(chunks) >= 1
    c = chunks[0]
    assert c.page == 1
    assert "Chapter 1" in c.section_path


def test_chunker_splits_long_text() -> None:
    """A single paragraph exceeding max_words should be split."""
    long_text = "word " * 500  # 500 words
    doc = _make_doc([
        Block(kind="paragraph", text=long_text),
    ])
    chunks = Chunker(target_words=100, max_words=200, min_words=10).chunk(doc)
    assert len(chunks) >= 2
    # All chunks together should cover the full text
    total = " ".join(c.text for c in chunks)
    assert len(total.split()) >= 400  # some overlap expected


def test_chunker_chunk_indices_are_sequential() -> None:
    """chunk_index should be 0, 1, 2, ... in order."""
    doc = _make_doc([
        Block(kind="heading", text="S1", level=1),
        Block(kind="paragraph", text="content " * 30),
        Block(kind="heading", text="S2", level=1),
        Block(kind="paragraph", text="content " * 30),
        Block(kind="heading", text="S3", level=1),
        Block(kind="paragraph", text="content " * 30),
    ])
    chunks = Chunker(target_words=20, max_words=50, min_words=5).chunk(doc)
    indices = [c.chunk_index for c in chunks]
    assert indices == list(range(len(chunks)))


def test_chunker_empty_document() -> None:
    """An empty document should produce zero chunks."""
    doc = _make_doc([])
    chunks = Chunker().chunk(doc)
    assert len(chunks) == 0


def test_chunker_section_label_property() -> None:
    """The section_label property should render the section path."""
    doc = _make_doc([
        Block(kind="heading", text="Intro", level=1),
        Block(kind="paragraph", text="Some content " * 20, section_path=["Intro"]),
    ])
    chunks = Chunker().chunk(doc)
    assert len(chunks) >= 1
    assert "Intro" in chunks[0].section_label
