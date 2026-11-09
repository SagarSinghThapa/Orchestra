from typing import Optional

from app.research.retrieval.schemas import SearchResultChunk


class ChunkDeduplicator:
    """
    Deduplicates retrieval candidates with exact ID matching and conservative overlap suppression.
    
    Guarantees:
    - Always eliminates exact duplicate chunk_ids globally.
    - Suppresses identical text scoped to the same provenance (document_id, page_number)
      so identical citations across different documents or pages are preserved.
    - Suppresses candidate chunks only when the candidate itself is >=90% contained inside
      an already-accepted higher-ranked chunk on the same document and page.
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
        seen_provenance_texts: set[tuple[int, Optional[int], str]] = set()
        accepted_candidates: list[SearchResultChunk] = []

        for candidate in candidates:
            # 1. Exact chunk_id deduplication (global)
            if candidate.chunk_id in seen_chunk_ids:
                continue

            # 2. Exact identical text duplicate suppression (scoped to provenance: doc + page)
            clean_text = candidate.text.strip()
            prov_key = (candidate.document_id, candidate.page_number, clean_text)
            if prov_key in seen_provenance_texts:
                continue

            # 3. High-containment overlap check with already-accepted higher-ranked chunks
            # Candidate containment asks: "How much of the CANDIDATE is already covered?"
            # Only evaluated for chunks from the EXACT same document and page.
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

                    # Compute character span overlap
                    overlap_start = max(c_start, a_start)
                    overlap_end = min(c_end, a_end)
                    overlap_chars = max(0, overlap_end - overlap_start)

                    if overlap_chars > 0:
                        candidate_containment = overlap_chars / c_len
                        if candidate_containment >= self.max_containment_ratio:
                            # Candidate is >=90% subsumed by a higher-ranked chunk on same page
                            subsumed = True
                            break

            if subsumed:
                continue

            seen_chunk_ids.add(candidate.chunk_id)
            seen_provenance_texts.add(prov_key)
            accepted_candidates.append(candidate)

        return accepted_candidates
