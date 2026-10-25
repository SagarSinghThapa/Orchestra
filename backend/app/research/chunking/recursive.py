from app.research.chunking.base import DocumentChunk
from app.research.chunking.normalizer import TextNormalizer
from app.research.exceptions import ParserError
from app.research.parsers.base import ExtractedDocument


class RecursiveTokenChunker:
    """
    Page-bounded recursive text chunker preserving citation provenance.
    
    Guarantees:
    - PDF chunks NEVER cross page boundaries. Each page is chunked in strict isolation.
    - Every chunk belongs to exactly one 1-indexed page_number.
    - start_char and end_char index precisely into the normalized page text used for indexing.
    - Token heuristic is len(text) // 4 chars per token.
    - Chunks have bounded overlap within a page, but zero overlap across page boundaries.
    """

    def __init__(
        self,
        chunk_size_tokens: int = 400,
        chunk_overlap_tokens: int = 80,
    ) -> None:
        if chunk_overlap_tokens >= chunk_size_tokens:
            raise ValueError("chunk_overlap_tokens must be strictly less than chunk_size_tokens")

        self.chunk_size_tokens = chunk_size_tokens
        self.chunk_overlap_tokens = chunk_overlap_tokens
        self.chunk_size_chars = chunk_size_tokens * 4
        self.chunk_overlap_chars = chunk_overlap_tokens * 4
        self.normalizer = TextNormalizer()
        self.separators = ["\n\n", "\n", ". ", " ", ""]

    def _estimate_tokens(self, text: str) -> int:
        """Token count heuristic based on character length."""
        return max(1, len(text) // 4) if text else 0

    def _split_into_spans(
        self, text: str, base_offset: int, sep_idx: int
    ) -> list[tuple[int, int]]:
        """
        Recursively decompose text into spans bounded by chunk_size_tokens.
        Returns list of (start_offset, end_offset) spans within the normalized page text.
        """
        if not text:
            return []

        # If already within chunk budget, return whole span
        if self._estimate_tokens(text) <= self.chunk_size_tokens:
            return [(base_offset, base_offset + len(text))]

        # If we exhausted separators, slice character-by-character
        if sep_idx >= len(self.separators) - 1:
            step = max(1, self.chunk_size_chars - self.chunk_overlap_chars)
            spans: list[tuple[int, int]] = []
            for i in range(0, len(text), step):
                chunk_slice = text[i : i + self.chunk_size_chars]
                if chunk_slice.strip():
                    spans.append((base_offset + i, base_offset + min(i + self.chunk_size_chars, len(text))))
            return spans

        sep = self.separators[sep_idx]
        if sep not in text:
            # Try next finer separator
            return self._split_into_spans(text, base_offset, sep_idx + 1)

        # Split preserving offsets
        raw_parts: list[tuple[int, int]] = []
        cur = 0
        while cur < len(text):
            pos = text.find(sep, cur)
            if pos == -1:
                raw_parts.append((cur, len(text)))
                break
            part_end = pos + len(sep)
            raw_parts.append((cur, part_end))
            cur = part_end

        result_spans: list[tuple[int, int]] = []
        for start_rel, end_rel in raw_parts:
            part_str = text[start_rel:end_rel]
            if not part_str.strip():
                continue
            if self._estimate_tokens(part_str) <= self.chunk_size_tokens:
                result_spans.append((base_offset + start_rel, base_offset + end_rel))
            else:
                sub_spans = self._split_into_spans(part_str, base_offset + start_rel, sep_idx + 1)
                result_spans.extend(sub_spans)

        return result_spans

    def chunk_page(
        self,
        page_text: str,
        page_number: int,
        document_id: int,
        project_id: int,
        start_chunk_index: int,
    ) -> tuple[list[DocumentChunk], int]:
        """
        Chunks text from a single page in strict isolation.
        
        Returns:
            (list of DocumentChunks, next_available_chunk_index)
        """
        normalized_page = self.normalizer.normalize(page_text)
        if not normalized_page.strip():
            return [], start_chunk_index

        pieces = self._split_into_spans(normalized_page, 0, 0)
        if not pieces:
            return [], start_chunk_index

        chunks: list[DocumentChunk] = []
        current_idx = start_chunk_index
        n_pieces = len(pieces)
        i = 0

        while i < n_pieces:
            span_start = pieces[i][0]
            span_end = pieces[i][1]
            j = i

            # Accumulate pieces until chunk size limit is reached
            while j + 1 < n_pieces:
                candidate_end = pieces[j + 1][1]
                candidate_text = normalized_page[span_start:candidate_end]
                if self._estimate_tokens(candidate_text) <= self.chunk_size_tokens:
                    span_end = candidate_end
                    j += 1
                else:
                    break

            # Trim leading/trailing whitespace while strictly adjusting character offsets
            raw_chunk = normalized_page[span_start:span_end]
            l_strip = len(raw_chunk) - len(raw_chunk.lstrip())
            r_strip = len(raw_chunk) - len(raw_chunk.rstrip())
            trimmed_start = span_start + l_strip
            trimmed_end = span_end - r_strip
            trimmed_text = normalized_page[trimmed_start:trimmed_end]

            if trimmed_text:
                chunk_obj = DocumentChunk(
                    chunk_id=f"doc_{document_id}_chk_{current_idx}",
                    document_id=document_id,
                    project_id=project_id,
                    text=trimmed_text,
                    chunk_index=current_idx,
                    page_number=page_number,
                    start_char=trimmed_start,
                    end_char=trimmed_end,
                    token_count=self._estimate_tokens(trimmed_text),
                )
                chunks.append(chunk_obj)
                current_idx += 1

            # Determine next start piece with bounded overlap
            if j >= n_pieces - 1:
                break

            # Backtrack from j for overlap
            overlap_k = j
            while overlap_k > i:
                candidate_overlap_text = normalized_page[pieces[overlap_k - 1][0] : span_end]
                if self._estimate_tokens(candidate_overlap_text) <= self.chunk_overlap_tokens:
                    overlap_k -= 1
                else:
                    break

            # Ensure forward progress
            i = max(overlap_k, i + 1)

        return chunks, current_idx

    def chunk_document(
        self,
        doc: ExtractedDocument,
        document_id: int,
        project_id: int,
    ) -> list[DocumentChunk]:
        """
        Processes each page in doc.pages independently to guarantee that
        no chunk crosses page boundaries.
        """
        all_chunks: list[DocumentChunk] = []
        current_chunk_idx = 0

        for page in doc.pages:
            page_chunks, current_chunk_idx = self.chunk_page(
                page_text=page.text,
                page_number=page.page_number,
                document_id=document_id,
                project_id=project_id,
                start_chunk_index=current_chunk_idx,
            )
            all_chunks.extend(page_chunks)

        if not all_chunks:
            raise ParserError("Document produced 0 text chunks")

        return all_chunks
