from typing import Optional

from app.research.retrieval.schemas import SearchResultChunk


class ChunkDeduplicator:
    """
    Deduplicates retrieval candidates with exact ID matching and conservative overlap suppression.
    
    Guarantees:
    - Always eliminates exact duplicate chunk_ids.
    - Suppresses near-identical overlapping spans only when span containment >= 90%,
      ensuring that adjacent chunks containing meaningful unique evidence are never discarded.
    """

    def __init__(self, max_containment_ratio: float = 0.90) -> None:
        self.max_containment_ratio = max_containment_ratio

    def deduplicate_chunks(
        self,
        candidates: list[SearchResultChunk],
    ) -> list[SearchResultChunk]:
        if not candidates:
            return []

        seen_chunk_ids: set[str] = set()
        seen_texts: set[str] = set()
        accepted_candidates: list[SearchResultChunk] = []

        for candidate in candidates:
            # 1. Exact chunk_id deduplication
            if candidate.chunk_id in seen_chunk_ids:
                continue

            # 2. Exact identical text deduplication
            clean_text = candidate.text.strip()
            if clean_text in seen_texts:
                continue

            # 3. High-containment overlap check with already-accepted higher-ranked chunks
            # Only evaluated for chunks from the EXACT same document and page
            subsumed = False
            c_start = candidate.start_char
            c_end = candidate.end_char
            c_len = max(1, c_end - c_start)

            for accepted in accepted_candidates:
                if (
                    accepted.document_id == candidate.document_id
                    and accepted.page_number == candidate.page_number
                ):
                    a_start = accepted.start_char
                    a_end = accepted.end_char
                    a_len = max(1, a_end - a_start)

                    # Compute character span overlap
                    overlap_start = max(c_start, a_start)
                    overlap_end = min(c_end, a_end)
                    overlap_chars = max(0, overlap_end - overlap_start)

                    if overlap_chars > 0:
                        min_len = min(c_len, a_len)
                        containment = overlap_chars / min_len
                        if containment >= self.max_containment_ratio:
                            # Candidate is >=90% subsumed by a higher-ranked chunk on same page
                            subsumed = True
                            break

            if subsumed:
                continue

            seen_chunk_ids.add(candidate.chunk_id)
            seen_texts.add(clean_text)
            accepted_candidates.append(candidate)

        return accepted_candidates
