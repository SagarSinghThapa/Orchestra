import io
import pypdf
import pypdf.errors

from app.core.config import settings
from app.research.exceptions import ParserError
from app.research.parsers.base import BaseParser, ExtractedDocument, ExtractedPage


class PDFParser(BaseParser):
    """
    Pure-Python PDF parser utilizing pypdf with magic bytes validation,
    page limit exhaustion defense, and zero-extractable-text detection.
    """

    def parse(self, content: bytes, filename: str) -> ExtractedDocument:
        if not content:
            raise ParserError("Uploaded PDF file is empty")

        # Signature validation
        if not content.startswith(b"%PDF-"):
            raise ParserError("Invalid PDF file signature; expected %PDF- header")

        try:
            stream = io.BytesIO(content)
            reader = pypdf.PdfReader(stream)
        except (pypdf.errors.PdfReadError, Exception) as exc:
            raise ParserError(f"Corrupted or malformed PDF file: {exc}") from exc

        if reader.is_encrypted:
            raise ParserError("Encrypted PDFs are not supported")

        page_count = len(reader.pages)
        if page_count > settings.max_pdf_pages:
            raise ParserError(
                f"PDF page count ({page_count}) exceeds maximum allowed limit of {settings.max_pdf_pages} pages"
            )

        extracted_pages: list[ExtractedPage] = []
        total_text_length = 0

        for idx, page in enumerate(reader.pages):
            try:
                page_text = page.extract_text() or ""
            except Exception as exc:
                raise ParserError(f"Failed to extract text from PDF page {idx + 1}: {exc}") from exc

            # Strip null bytes and normalize control characters
            clean_text = page_text.replace("\0", "")
            non_ws_count = len(clean_text.strip())
            total_text_length += non_ws_count

            extracted_pages.append(
                ExtractedPage(
                    page_number=idx + 1,
                    text=clean_text,
                    char_count=len(clean_text),
                )
            )

        if total_text_length == 0:
            raise ParserError("Document contains no extractable text; OCR is not supported.")

        return ExtractedDocument(
            pages=extracted_pages,
            total_pages=len(extracted_pages),
            metadata={"filename": filename, "format": "pdf"},
        )
