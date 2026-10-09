"""Parser base class and registry."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from sovereign.parsing.model import ParsedDocument


@runtime_checkable
class Parser(Protocol):
    """Protocol for document parsers.

    Each parser takes raw bytes and a MIME type, and returns a
    ``ParsedDocument`` preserving structure.
    """

    @property
    def name(self) -> str: ...

    def parse(self, data: bytes, filename: str) -> ParsedDocument: ...

    def supported_mimes(self) -> list[str]: ...
