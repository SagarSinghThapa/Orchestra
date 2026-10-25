from pathlib import Path
from typing import Optional

from app.research.exceptions import ParserError
from app.research.parsers.base import BaseParser
from app.research.parsers.pdf import PDFParser
from app.research.parsers.text import MarkdownParser, TextParser


class ParserRegistry:
    """Registry coordinating format parsers by file extension."""

    def __init__(self) -> None:
        self._parsers: dict[str, BaseParser] = {
            ".pdf": PDFParser(),
            ".txt": TextParser(),
            ".md": MarkdownParser(),
        }

    def register_parser(self, extension: str, parser: BaseParser) -> None:
        """Register or override a parser for a specific file extension."""
        ext = extension.lower()
        if not ext.startswith("."):
            ext = f".{ext}"
        self._parsers[ext] = parser

    def get_parser_for_extension(self, extension: str) -> BaseParser:
        """Retrieve parser for a given extension, raising ParserError if unsupported."""
        ext = extension.lower()
        if not ext.startswith("."):
            ext = f".{ext}"
        parser = self._parsers.get(ext)
        if not parser:
            raise ParserError(f"No parser registered for extension '{extension}'")
        return parser

    def get_parser_for_filename(self, filename: str) -> BaseParser:
        """Extract file extension and dispatch to registered parser."""
        ext = Path(filename).suffix.lower()
        return self.get_parser_for_extension(ext)

    def get_supported_extensions(self) -> list[str]:
        """Return list of supported extensions."""
        return sorted(list(self._parsers.keys()))
