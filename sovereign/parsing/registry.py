"""Parser registry and dispatcher.

Selects the right parser based on MIME type. All parsers are registered
here; the ingestion service calls ``get_parser(mime_type)`` to get one.
"""

from __future__ import annotations

from sovereign.core.errors import DocumentParseError
from sovereign.parsing.base import Parser
from sovereign.parsing.csv import CSVParser
from sovereign.parsing.docx import DOCXParser
from sovereign.parsing.markdown import MarkdownParser
from sovereign.parsing.model import ParsedDocument
from sovereign.parsing.pdf import PDFParser
from sovereign.parsing.txt import TXTParser
from sovereign.parsing.xlsx import XLSXParser

# Registry: MIME → parser instance
_PARSERS: dict[str, Parser] = {}


def _register(parser: Parser) -> None:
    for mime in parser.supported_mimes():
        _PARSERS[mime] = parser


_register(PDFParser())
_register(DOCXParser())
_register(TXTParser())
_register(MarkdownParser())
_register(CSVParser())
_register(XLSXParser())


def get_parser(mime_type: str) -> Parser:
    """Return the parser for ``mime_type``. Raises if unsupported."""
    # Normalize charset suffix: text/plain; charset=utf-8 → text/plain
    mime = mime_type.split(";", maxsplit=1)[0].strip().lower()
    if mime not in _PARSERS:
        msg = (
            f"unsupported MIME type: {mime_type!r}. "
            f"Supported: {sorted(_PARSERS)}"
        )
        raise DocumentParseError(msg)
    return _PARSERS[mime]


def supported_mimes() -> list[str]:
    """Return all supported MIME types."""
    return sorted(_PARSERS)


def parse_document(data: bytes, filename: str, mime_type: str) -> ParsedDocument:
    """Parse a document using the appropriate parser for ``mime_type``."""
    parser = get_parser(mime_type)
    return parser.parse(data, filename)
