import pytest

from app.research.chunking.base import DocumentChunk
from app.research.chunking.normalizer import TextNormalizer
from app.research.chunking.recursive import RecursiveTokenChunker
from app.research.exceptions import ParserError
from app.research.parsers.base import ExtractedDocument, ExtractedPage


class TestTextNormalizer:
    def test_line_ending_standardization(self):
        norm = TextNormalizer()
        input_text = "Line 1\r\nLine 2\rLine 3\nLine 4"
        assert norm.normalize(input_text) == "Line 1\nLine 2\nLine 3\nLine 4"

    def test_nfc_canonical_preservation(self):
        norm = TextNormalizer()
        # Ligatures (ﬁ), math (∑, √), sub/superscripts (x², H₂O)
        special_text = "Formula: ∑(x²) = √y. Chemical: H₂O. Ligature: ﬁle and ﬂow."
        normalized = norm.normalize(special_text)
        assert "ﬁle" in normalized
        assert "∑(x²)" in normalized
        assert "√y" in normalized
        assert "H₂O" in normalized

    def test_preserves_case_and_citations(self):
        norm = TextNormalizer()
        citation = 'According to Smith et al. (2024), "Large Language Models require grounded retrieval."'
        assert norm.normalize(citation) == citation

    def test_whitespace_and_excessive_newlines(self):
        norm = TextNormalizer()
        dirty = "Line 1   \n\n\n\nLine 2\t  \n\n\nLine 3"
        expected = "Line 1\n\nLine 2\n\nLine 3"
        assert norm.normalize(dirty) == expected

    def test_control_character_filtering(self):
        norm = TextNormalizer()
        dirty = "Clean text\x00with\x07bell\x1bescape\tpreserved\nline"
        cleaned = norm.normalize(dirty)
        assert cleaned == "Clean textwithbellescape\tpreserved\nline"


class TestRecursiveTokenChunker:
    def test_page_boundary_strict_isolation(self):
        """Chunks on Page 1 and Page 2 must never cross page boundaries."""
        chunker = RecursiveTokenChunker(chunk_size_tokens=100, chunk_overlap_tokens=20)
        p1_text = "Page 1 Content. " * 30
        p2_text = "Page 2 Content. " * 30

        doc = ExtractedDocument(
            pages=[
                ExtractedPage(page_number=1, text=p1_text, char_count=len(p1_text)),
                ExtractedPage(page_number=2, text=p2_text, char_count=len(p2_text)),
            ],
            total_pages=2,
        )

        chunks = chunker.chunk_document(doc, document_id=42, project_id=7)
        assert len(chunks) > 2

        p1_chunks = [c for c in chunks if c.page_number == 1]
        p2_chunks = [c for c in chunks if c.page_number == 2]

        assert len(p1_chunks) > 0
        assert len(p2_chunks) > 0
        assert len(p1_chunks) + len(p2_chunks) == len(chunks)

        for c in p1_chunks:
            assert "Page 1 Content" in c.text
            assert "Page 2 Content" not in c.text

        for c in p2_chunks:
            assert "Page 2 Content" in c.text
            assert "Page 1 Content" not in c.text

    def test_start_char_and_end_char_exact_indexing(self):
        chunker = RecursiveTokenChunker(chunk_size_tokens=50, chunk_overlap_tokens=10)
        page_text = "The quick brown fox jumps over the lazy dog. " * 20
        norm_text = chunker.normalizer.normalize(page_text)

        chunks, _ = chunker.chunk_page(
            page_text=page_text,
            page_number=1,
            document_id=1,
            project_id=1,
            start_chunk_index=0,
        )

        assert len(chunks) > 1
        for chunk in chunks:
            # Substring at offsets must strictly equal chunk text
            slice_text = norm_text[chunk.start_char : chunk.end_char]
            assert slice_text == chunk.text
            assert len(chunk.text.strip()) > 0
            assert chunk.token_count > 0

    def test_monotonic_chunk_indices(self):
        chunker = RecursiveTokenChunker(chunk_size_tokens=40, chunk_overlap_tokens=10)
        p1 = "First page text block. " * 10
        p2 = "Second page text block. " * 10

        doc = ExtractedDocument(
            pages=[
                ExtractedPage(page_number=1, text=p1, char_count=len(p1)),
                ExtractedPage(page_number=2, text=p2, char_count=len(p2)),
            ],
            total_pages=2,
        )

        chunks = chunker.chunk_document(doc, document_id=10, project_id=5)
        for idx, chunk in enumerate(chunks):
            assert chunk.chunk_index == idx
            assert chunk.chunk_id == f"doc_10_chk_{idx}"
            assert chunk.project_id == 5
            assert chunk.document_id == 10

    def test_overlap_between_adjacent_chunks_on_same_page(self):
        chunker = RecursiveTokenChunker(chunk_size_tokens=60, chunk_overlap_tokens=20)
        page_text = (
            "Sentence alpha provides background details. "
            "Sentence beta elaborates on technical findings. "
            "Sentence gamma analyzes experimental results. "
            "Sentence delta discusses unexpected observations. "
            "Sentence epsilon concludes the chapter findings."
        ) * 5

        chunks, _ = chunker.chunk_page(
            page_text=page_text,
            page_number=1,
            document_id=1,
            project_id=1,
            start_chunk_index=0,
        )

        assert len(chunks) >= 2
        # Verify adjacent chunks share overlapping words/substrings
        found_overlap = False
        for i in range(len(chunks) - 1):
            c1_words = set(chunks[i].text.split())
            c2_words = set(chunks[i + 1].text.split())
            shared = c1_words.intersection(c2_words)
            if len(shared) > 3:
                found_overlap = True
                break
        assert found_overlap, "Adjacent chunks on same page should have overlapping content"

    def test_empty_document_raises_parser_error(self):
        chunker = RecursiveTokenChunker()
        empty_doc = ExtractedDocument(pages=[], total_pages=0)
        with pytest.raises(ParserError, match="Document produced 0 text chunks"):
            chunker.chunk_document(empty_doc, document_id=1, project_id=1)

    def test_whitespace_only_page_raises_parser_error(self):
        chunker = RecursiveTokenChunker()
        doc = ExtractedDocument(
            pages=[ExtractedPage(page_number=1, text="   \n\n\t  ", char_count=7)],
            total_pages=1,
        )
        with pytest.raises(ParserError, match="Document produced 0 text chunks"):
            chunker.chunk_document(doc, document_id=1, project_id=1)
