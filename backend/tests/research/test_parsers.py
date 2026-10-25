import io
import pytest
import pypdf

from app.core.config import settings
from app.research.exceptions import ParserError
from app.research.parsers.base import ExtractedDocument
from app.research.parsers.pdf import PDFParser
from app.research.parsers.text import MarkdownParser, TextParser
from app.research.parsers.registry import ParserRegistry


SAMPLE_RAW_PDF = b"""%PDF-1.4
1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj
2 0 obj <</Type /Pages /Kids [3 0 R] /Count 1>> endobj
3 0 obj <</Type /Page /Parent 2 0 R /Resources <</Font <</F1 4 0 R>>>> /MediaBox [0 0 300 300] /Contents 5 0 R>> endobj
4 0 obj <</Type /Font /Subtype /Type1 /BaseFont /Helvetica>> endobj
5 0 obj <</Length 44>> stream
BT
/F1 12 Tf
100 100 Td
(Hello PDF World) Tj
ET
endstream
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000227 00000 n 
0000000295 00000 n 
trailer <</Size 6 /Root 1 0 R>>
startxref
390
%%EOF"""


def build_synthetic_pdf(page_count: int = 1, text: str = "Hello PDF World") -> bytes:
    """Helper to generate valid in-memory multi-page PDF bytes with extractable text."""
    r = pypdf.PdfReader(io.BytesIO(SAMPLE_RAW_PDF))
    w = pypdf.PdfWriter()
    for _ in range(page_count):
        w.add_page(r.pages[0])
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


class TestPDFParser:
    def test_missing_magic_bytes_raises_parser_error(self):
        parser = PDFParser()
        with pytest.raises(ParserError, match="Invalid PDF file signature"):
            parser.parse(b"NOT_A_PDF_STREAM", "doc.pdf")

    def test_empty_content_raises_parser_error(self):
        parser = PDFParser()
        with pytest.raises(ParserError, match="empty"):
            parser.parse(b"", "doc.pdf")

    def test_corrupted_pdf_raises_parser_error(self):
        parser = PDFParser()
        with pytest.raises(ParserError, match="Corrupted or malformed PDF file"):
            parser.parse(b"%PDF-corrupted_gibberish_bytes", "doc.pdf")

    def test_valid_multipage_pdf_parses_page_by_page(self):
        parser = PDFParser()
        pdf_bytes = build_synthetic_pdf(page_count=3)
        doc = parser.parse(pdf_bytes, "research.pdf")

        assert isinstance(doc, ExtractedDocument)
        assert doc.total_pages == 3
        assert len(doc.pages) == 3
        assert doc.pages[0].page_number == 1
        assert doc.pages[1].page_number == 2
        assert doc.pages[2].page_number == 3
        for page in doc.pages:
            assert "Hello PDF World" in page.text
            assert page.char_count > 0

    def test_blank_pdf_zero_extractable_text_fails(self):
        w = pypdf.PdfWriter()
        w.add_blank_page(width=200, height=200)
        buf = io.BytesIO()
        w.write(buf)
        blank_pdf_bytes = buf.getvalue()

        parser = PDFParser()
        with pytest.raises(ParserError, match="Document contains no extractable text; OCR is not supported."):
            parser.parse(blank_pdf_bytes, "blank.pdf")

    def test_encrypted_pdf_fails(self):
        r = pypdf.PdfReader(io.BytesIO(SAMPLE_RAW_PDF))
        w = pypdf.PdfWriter()
        w.add_page(r.pages[0])
        w.encrypt("test_password")
        buf = io.BytesIO()
        w.write(buf)
        encrypted_bytes = buf.getvalue()

        parser = PDFParser()
        with pytest.raises(ParserError, match="Encrypted PDFs are not supported"):
            parser.parse(encrypted_bytes, "encrypted.pdf")

    def test_max_pdf_pages_guard_enforced(self, monkeypatch):
        monkeypatch.setattr(settings, "max_pdf_pages", 2)
        pdf_bytes = build_synthetic_pdf(page_count=3)

        parser = PDFParser()
        with pytest.raises(ParserError, match="exceeds maximum allowed limit of 2 pages"):
            parser.parse(pdf_bytes, "large.pdf")


class TestTextAndMarkdownParsers:
    def test_valid_text_parser_success(self):
        parser = TextParser()
        raw = "Line 1 of research notes.\nLine 2 with data.".encode("utf-8")
        doc = parser.parse(raw, "notes.txt")

        assert doc.total_pages == 1
        assert len(doc.pages) == 1
        assert doc.pages[0].page_number == 1
        assert "Line 1 of research notes." in doc.pages[0].text

    def test_text_parser_rejects_null_bytes(self):
        parser = TextParser()
        binary_payload = b"Research data with embedded \x00 null byte"
        with pytest.raises(ParserError, match="Binary content not allowed in text document"):
            parser.parse(binary_payload, "binary.txt")

    def test_text_parser_rejects_empty_or_whitespace(self):
        parser = TextParser()
        with pytest.raises(ParserError, match="empty"):
            parser.parse(b"", "empty.txt")
        with pytest.raises(ParserError, match="Document contains no extractable text; OCR is not supported."):
            parser.parse(b"   \n\t  \n  ", "whitespace.txt")

    def test_markdown_parser_preserves_structure(self):
        parser = MarkdownParser()
        content = b"# Executive Summary\n\n- Key Point 1\n- Key Point 2\n\n```python\nprint('hello')\n```\n"
        doc = parser.parse(content, "summary.md")

        assert doc.total_pages == 1
        assert doc.pages[0].page_number == 1
        assert "# Executive Summary" in doc.pages[0].text
        assert "```python" in doc.pages[0].text

    def test_markdown_parser_rejects_null_bytes(self):
        parser = MarkdownParser()
        with pytest.raises(ParserError, match="Binary content not allowed"):
            parser.parse(b"# Header\x00malicious", "header.md")


class TestParserRegistry:
    def test_registry_dispatch(self):
        reg = ParserRegistry()
        assert isinstance(reg.get_parser_for_filename("doc.pdf"), PDFParser)
        assert isinstance(reg.get_parser_for_filename("FILE.PDF"), PDFParser)
        assert isinstance(reg.get_parser_for_filename("notes.txt"), TextParser)
        assert isinstance(reg.get_parser_for_filename("report.md"), MarkdownParser)

    def test_unsupported_extension_raises_parser_error(self):
        reg = ParserRegistry()
        with pytest.raises(ParserError, match="No parser registered for extension"):
            reg.get_parser_for_filename("spreadsheet.xlsx")
        with pytest.raises(ParserError, match="No parser registered for extension"):
            reg.get_parser_for_extension(".docx")
