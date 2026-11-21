from app.research.exceptions import ParserError
from app.research.parsers.base import BaseParser, ExtractedDocument, ExtractedPage


class TextParser(BaseParser):
    """Plain text parser with binary null-byte defense and UTF-8 decodability validation."""

    def parse(self, content: bytes, filename: str) -> ExtractedDocument:
        if not content:
            raise ParserError("Uploaded text file is empty")

        if b"\0" in content:
            raise ParserError("Binary content not allowed in text document")

        try:
            decoded = content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                decoded = content.decode("latin-1")
            except Exception as exc:
                raise ParserError(f"Invalid text encoding: {exc}") from exc

        if not decoded.strip():
            raise ParserError("Document contains no extractable text; OCR is not supported.")

        return ExtractedDocument(
            pages=[
                ExtractedPage(
                    page_number=1,
                    text=decoded,
                    char_count=len(decoded),
                )
            ],
            total_pages=1,
            metadata={"filename": filename, "format": "txt"},
        )


class MarkdownParser(BaseParser):
    """Markdown parser preserving heading syntax, code blocks, and formatting intact."""

    def parse(self, content: bytes, filename: str) -> ExtractedDocument:
        if not content:
            raise ParserError("Uploaded markdown file is empty")

        if b"\0" in content:
            raise ParserError("Binary content not allowed in text document")

        try:
            decoded = content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                decoded = content.decode("latin-1")
            except Exception as exc:
                raise ParserError(f"Invalid text encoding: {exc}") from exc

        if not decoded.strip():
            raise ParserError("Document contains no extractable text; OCR is not supported.")

        return ExtractedDocument(
            pages=[
                ExtractedPage(
                    page_number=1,
                    text=decoded,
                    char_count=len(decoded),
                )
            ],
            total_pages=1,
            metadata={"filename": filename, "format": "md"},
        )
