"""Parsers — structure-preserving document parsing.

Each parser converts a raw document (PDF, DOCX, TXT, MD, CSV, XLSX) into
a ``ParsedDocument`` that preserves:

- page numbers (where applicable)
- headings and section hierarchy
- tables (with row/column structure)
- figures and captions
- metadata (title, author, creation date, etc.)
- document structure as an ordered list of blocks

The ``ParsedDocument`` is the canonical intermediate representation
between ingestion and the chunker/embedder. Every downstream subsystem
RAG, agents, evidence verification, deliverables) works with this
structure, never with raw file bytes.
"""
