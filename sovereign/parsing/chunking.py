"""Structure-aware chunker.

Splits a ``ParsedDocument`` into ``Chunk``s that:

1. Respect section boundaries (don't split across headings)
2. Stay within a target token range (approximated by word count)
3. Preserve provenance: each chunk knows its page, section path, and source
4. Include table content as special chunks (tables don't split mid-row)

The chunker is the last step before embedding. Every chunk becomes a vector
in the knowledge base, and the chunk's provenance flows through to citations.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from sovereign.parsing.model import ParsedDocument


class Chunk(BaseModel):
    """A retrievable chunk of a document.

    This is the unit of the knowledge base. Each chunk has:
    - ``text``: the content (for embedding + LLM context)
    - ``document_id``: source document
    - ``project_id``: for isolation
    - ``page``: page number (for citation)
    - ``section_path``: heading hierarchy (for citation)
    - ``chunk_index``: position within the document
    - ``block_kinds``: what kinds of blocks were merged into this chunk
    """

    chunk_id: str = ""
    document_id: str = ""
    project_id: str = ""
    text: str = ""
    page: int | None = None
    section_path: list[str] = Field(default_factory=list)
    chunk_index: int = 0
    block_kinds: list[str] = Field(default_factory=list)
    # Token estimate (word count * 1.3 as rough approximation)
    token_estimate: int = 0

    @property
    def section_label(self) -> str:
        """Human-readable section path for citation rendering."""
        return " > ".join(self.section_path) if self.section_path else "(no section)"


class Chunker:
    """Structure-aware chunker with configurable size and overlap."""

    def __init__(
        self,
        target_words: int = 200,
        max_words: int = 400,
        min_words: int = 20,
        overlap_words: int = 30,
    ) -> None:
        self.target_words = target_words
        self.max_words = max_words
        self.min_words = min_words
        self.overlap_words = overlap_words

    def chunk(self, doc: ParsedDocument) -> list[Chunk]:
        """Split a ParsedDocument into provenance-preserving chunks."""
        chunks: list[Chunk] = []
        doc_id = doc.document_id or ""
        proj_id = doc.project_id or ""

        current_text: list[str] = []
        current_words = 0
        current_page: int | None = None
        current_section: list[str] = []
        current_kinds: list[str] = []
        chunk_idx = 0

        def _flush() -> None:
            nonlocal current_text, current_words, current_kinds, chunk_idx
            if not current_text:
                return
            text = "\n\n".join(current_text)
            words = len(text.split())
            if words < self.min_words and chunks:
                # Merge into previous chunk if too small
                prev = chunks[-1]
                prev.text = prev.text + "\n\n" + text
                prev.token_estimate = len(prev.text.split())
                prev.block_kinds = list(set(prev.block_kinds + current_kinds))
            else:
                chunks.append(
                    Chunk(
                        chunk_id=f"{doc_id}_c{chunk_idx}",
                        document_id=doc_id,
                        project_id=proj_id,
                        text=text,
                        page=current_page,
                        section_path=list(current_section),
                        chunk_index=chunk_idx,
                        block_kinds=list(set(current_kinds)),
                        token_estimate=words,
                    )
                )
                chunk_idx += 1
            current_text = []
            current_words = 0
            current_kinds = []

        for block in doc.all_blocks:
            # Table blocks: flush current, emit as standalone chunk
            if block.kind == "table" and block.table:
                _flush()
                table_text = block.table.markdown or block.text
                if table_text.strip():
                    chunks.append(
                        Chunk(
                            chunk_id=f"{doc_id}_c{chunk_idx}",
                            document_id=doc_id,
                            project_id=proj_id,
                            text=table_text,
                            page=block.page,
                            section_path=list(block.section_path),
                            chunk_index=chunk_idx,
                            block_kinds=["table"],
                            token_estimate=len(table_text.split()),
                        )
                    )
                    chunk_idx += 1
                continue

            # Figure blocks: flush current, emit as standalone chunk
            if block.kind == "figure":
                _flush()
                fig_caption = block.figure.caption if block.figure else None
                fig_text = block.text or fig_caption or ""
                if fig_text.strip():
                    chunks.append(
                        Chunk(
                            chunk_id=f"{doc_id}_c{chunk_idx}",
                            document_id=doc_id,
                            project_id=proj_id,
                            text=fig_text,
                            page=block.page,
                            section_path=list(block.section_path),
                            chunk_index=chunk_idx,
                            block_kinds=["figure"],
                            token_estimate=len(fig_text.split()),
                        )
                    )
                    chunk_idx += 1
                continue

            # Heading blocks: flush current, update section, start new chunk
            if block.kind == "heading":
                _flush()
                current_section = [*list(block.section_path), block.text]
                current_page = block.page
                # Include the heading in the next chunk
                heading_text = f"{'#' * (block.level or 1)} {block.text}"
                current_text.append(heading_text)
                current_words += len(block.text.split())
                current_kinds.append("heading")
                continue

            # Paragraph / list_item / code / quote: accumulate
            block_text = block.text.strip()
            if not block_text:
                continue

            block_words = len(block_text.split())

            # If this block alone exceeds max, split it
            if block_words > self.max_words:
                _flush()
                for piece in _split_long_text(block_text, self.target_words, self.overlap_words):
                    chunks.append(
                        Chunk(
                            chunk_id=f"{doc_id}_c{chunk_idx}",
                            document_id=doc_id,
                            project_id=proj_id,
                            text=piece,
                            page=block.page,
                            section_path=list(block.section_path),
                            chunk_index=chunk_idx,
                            block_kinds=[block.kind],
                            token_estimate=len(piece.split()),
                        )
                    )
                    chunk_idx += 1
                continue

            # Would adding this block exceed max?
            if current_words + block_words > self.max_words:
                _flush()

            current_text.append(block_text)
            current_words += block_words
            current_kinds.append(block.kind)
            if current_page is None:
                current_page = block.page
            if not current_section and block.section_path:
                current_section = list(block.section_path)

        _flush()  # flush remaining

        return chunks


def _split_long_text(
    text: str, target_words: int, overlap_words: int
) -> list[str]:
    """Split a long text into overlapping pieces by sentence boundaries.

    Uses a simple word-count-based approach: accumulate words until we
    hit the target, then start a new piece (optionally carrying some
    overlap from the previous piece).
    """
    words = text.split()
    if len(words) <= target_words:
        return [text]

    pieces: list[str] = []
    i = 0
    while i < len(words):
        # Take a slice of target_words starting at i
        end = min(i + target_words, len(words))
        piece = " ".join(words[i:end])
        pieces.append(piece)
        # Move forward by (target - overlap) words
        step = max(1, target_words - overlap_words)
        i += step
        # If we're near the end, stop (don't create tiny overlapping pieces)
        if end >= len(words):
            break

    return pieces
