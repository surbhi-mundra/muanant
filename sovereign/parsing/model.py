"""ParsedDocument — the canonical structure-preserving document model.

Every parser produces a ``ParsedDocument``. Every downstream subsystem
(chunker, embedder, RAG, agents, evidence, deliverables) consumes it.

Design principles:
1. **Structure is explicit.** Pages, headings, sections, tables, figures,
   and captions are first-class typed objects — not embedded in raw text.
2. **Provenance is preserved.** Every block knows its page number, section
   path, and source document. This flows through to chunk-level provenance
   and ultimately to citation rendering.
3. **Format-agnostic.** The same ``ParsedDocument`` shape represents a PDF,
   a DOCX, a CSV, or an XLSX — downstream code doesn't care about source.
4. **Serializable.** ``ParsedDocument`` is a pydantic model — JSON-serializable
   for storage, API responses, and debugging.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Block types
# ---------------------------------------------------------------------------
BlockKind = Literal[
    "heading",
    "paragraph",
    "list_item",
    "table",
    "figure",
    "caption",
    "code",
    "quote",
    "page_break",
]


class BoundingBox(BaseModel):
    """Bounding box in PDF/image coordinates (points or pixels)."""

    x0: float = 0.0
    y0: float = 0.0
    x1: float = 0.0
    y1: float = 0.0


class TableCell(BaseModel):
    text: str = ""
    row_span: int = 1
    col_span: int = 1
    is_header: bool = False


class TableRow(BaseModel):
    cells: list[TableCell] = Field(default_factory=list)


class Table(BaseModel):
    """A table with explicit row/column structure."""

    rows: list[TableRow] = Field(default_factory=list)
    caption: str | None = None
    page: int | None = None
    # Markdown rendering (pre-computed for convenience)
    markdown: str | None = None

    @property
    def num_rows(self) -> int:
        return len(self.rows)

    @property
    def num_cols(self) -> int:
        return max((len(r.cells) for r in self.rows), default=0)


class Figure(BaseModel):
    """A figure / image extracted from a document."""

    caption: str | None = None
    page: int | None = None
    # Storage key if the figure image was persisted to the object store.
    image_key: str | None = None
    bbox: BoundingBox | None = None


class Block(BaseModel):
    """An ordered content block within a page or section.

    Blocks are the unit of structure. The chunker walks them in order,
    grouping adjacent blocks into chunks that respect section boundaries.
    """

    kind: BlockKind
    text: str = ""
    # 1-indexed page number (None for formats without pages, e.g. TXT/MD).
    page: int | None = None
    # Section path: ["Chapter 1", "1.2 Safety Procedures"] — the heading
    # hierarchy that contains this block. Used for provenance.
    section_path: list[str] = Field(default_factory=list)
    # Heading level (1=H1, 2=H2, ...) for heading blocks.
    level: int | None = None
    # For table blocks:
    table: Table | None = None
    # For figure blocks:
    figure: Figure | None = None
    # Bounding box (PDF/image documents only)
    bbox: BoundingBox | None = None


class Page(BaseModel):
    """A single page of a paginated document.

    Non-paginated formats (TXT, MD, CSV) produce a single page with
    ``page_number=1`` and ``is_synthetic=True``.
    """

    page_number: int
    blocks: list[Block] = Field(default_factory=list)
    width: float | None = None
    height: float | None = None
    is_synthetic: bool = False  # True for formats without real pages


class DocumentMetadata(BaseModel):
    """Metadata extracted from the document itself (not user-supplied)."""

    title: str | None = None
    author: str | None = None
    subject: str | None = None
    keywords: list[str] = Field(default_factory=list)
    created_at: str | None = None  # ISO 8601
    modified_at: str | None = None
    producer: str | None = None  # Software that created the doc
    page_count: int | None = None
    word_count: int | None = None
    char_count: int | None = None
    language: str | None = None
    # Format-specific extras
    extra: dict[str, str] = Field(default_factory=dict)


class ParsedDocument(BaseModel):
    """The canonical structure-preserving document representation.

    Produced by ``sovereign.parsing`` parsers. Consumed by the chunker,
    embedder, RAG pipeline, agents, evidence verifier, and deliverable
    generator.
    """

    # Identifiers (set by the ingestion service, not the parser)
    document_id: str | None = None
    project_id: str | None = None

    # Source info
    source_filename: str = ""
    source_mime_type: str = ""
    source_sha256: str = ""

    # Structure
    pages: list[Page] = Field(default_factory=list)
    metadata: DocumentMetadata = Field(default_factory=dict)  # type: ignore[assignment]

    # Parser info
    parser_name: str = ""
    parser_version: str = "1.0"
    parse_warnings: list[str] = Field(default_factory=list)

    @property
    def all_blocks(self) -> list[Block]:
        """Flat list of all blocks across all pages, in reading order."""
        blocks: list[Block] = []
        for page in self.pages:
            blocks.extend(page.blocks)
        return blocks

    @property
    def total_text(self) -> str:
        """Concatenated text of all blocks (for simple use cases)."""
        parts: list[str] = []
        for block in self.all_blocks:
            if block.text:
                parts.append(block.text)
            if block.table and block.table.markdown:
                parts.append(block.table.markdown)
        return "\n\n".join(parts)

    @property
    def headings(self) -> list[Block]:
        """All heading blocks, in order."""
        return [b for b in self.all_blocks if b.kind == "heading"]

    @property
    def tables(self) -> list[Table]:
        """All tables, in order."""
        return [b.table for b in self.all_blocks if b.kind == "table" and b.table]

    @property
    def figures(self) -> list[Figure]:
        """All figures, in order."""
        return [b.figure for b in self.all_blocks if b.kind == "figure" and b.figure]
