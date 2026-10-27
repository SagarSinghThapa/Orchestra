from datetime import datetime
import logging
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.document import Document
from app.research.retrieval.schemas import CitationEvidence, SearchMode, SearchQuery
from app.research.services.retrieval_service import RetrievalService

logger = logging.getLogger(__name__)


class AggregatedEvidence(BaseModel):
    """
    Consolidated evidence representation across multi-query retrieval.
    Preserves exact provenance (document, page, chunk offsets, filename) and tracks query attribution.
    """
    evidence_id: str
    document_id: int
    document_filename: str
    page_number: int
    chunk_id: str
    chunk_index: int
    start_char: int
    end_char: int
    text: str
    score: float
    aggregated_score: float
    retrieved_by_queries: list[str] = Field(default_factory=list)
    document_updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class EvidenceAggregator:
    """
    Coordinates multi-query retrieval across 1..4 subqueries using Phase 05 RetrievalService.
    Preserves independent provenance and aggregates relevance across queries.
    """

    def __init__(self, retrieval_service: RetrievalService) -> None:
        self.retrieval_service = retrieval_service

    async def aggregate(
        self,
        project_id: int,
        subqueries: list[str],
        limit_per_query: int = 5,
    ) -> list[AggregatedEvidence]:
        """
        Executes bounded hybrid retrieval for each subquery and merges results.
        Fails fast if any retrieval call errors.
        """
        clamped_queries = subqueries[:4]
        merged: dict[str, AggregatedEvidence] = {}

        for sq in clamped_queries:
            query_input = SearchQuery(
                query=sq,
                limit=limit_per_query,
                mode=SearchMode.HYBRID,
            )

            # Let exceptions propagate (fail-fast, no silent incomplete retrieval)
            retrieval_response = await self.retrieval_service.search(
                project_id=project_id,
                query_input=query_input,
            )

            for item in retrieval_response.results:
                # Key strictly by chunk_id to preserve cross-document and cross-page provenance
                if item.chunk_id in merged:
                    existing = merged[item.chunk_id]
                    if sq not in existing.retrieved_by_queries:
                        existing.retrieved_by_queries.append(sq)
                    # Multi-query boost
                    existing.aggregated_score = max(existing.score, item.score) + 0.1 * len(existing.retrieved_by_queries)
                else:
                    merged[item.chunk_id] = AggregatedEvidence(
                        evidence_id=item.evidence_id,
                        document_id=item.document_id,
                        document_filename=item.document_filename,
                        page_number=item.page_number,
                        chunk_id=item.chunk_id,
                        chunk_index=item.chunk_index,
                        start_char=item.start_char,
                        end_char=item.end_char,
                        text=item.text,
                        score=item.score,
                        aggregated_score=item.score,
                        retrieved_by_queries=[sq],
                    )

        if merged and hasattr(self.retrieval_service, "db") and self.retrieval_service.db:
            try:
                doc_ids = list({item.document_id for item in merged.values()})
                docs = (
                    self.retrieval_service.db.query(Document.id, Document.updated_at)
                    .filter(Document.id.in_(doc_ids))
                    .all()
                )
                updated_map = {d[0]: d[1] for d in docs}
                for item in merged.values():
                    item.document_updated_at = updated_map.get(item.document_id)
            except Exception as e:
                logger.warning("Could not query Document.updated_at during aggregation: %s", e)

        return list(merged.values())


class EvidenceSelector:
    """
    Selects top evidence chunks prioritizing relevance while promoting source document diversity
    and enforcing an authoritative character budget limit.
    """

    def __init__(
        self,
        max_chunks: int = 10,
        max_total_chars: int = 16000,
        max_chunks_per_doc: int = 4,
    ) -> None:
        self.max_chunks = max_chunks
        self.max_total_chars = max_total_chars
        self.max_chunks_per_doc = max_chunks_per_doc

    def select(
        self,
        candidates: list[AggregatedEvidence],
        max_chunks_override: Optional[int] = None,
    ) -> list[AggregatedEvidence]:
        """
        Filters and sorts candidates within diversity and character budget bounds.
        """
        if not candidates:
            return []

        effective_max_chunks = min(
            max_chunks_override or self.max_chunks, self.max_chunks
        )

        # Sort by aggregated relevance descending
        sorted_candidates = sorted(
            candidates, key=lambda c: c.aggregated_score, reverse=True
        )

        selected: list[AggregatedEvidence] = []
        doc_counts: dict[int, int] = {}
        total_chars = 0
        deferred: list[AggregatedEvidence] = []

        # Pass 1: Select top candidates respecting per-document diversity cap
        for cand in sorted_candidates:
            cand_len = len(cand.text)
            current_doc_count = doc_counts.get(cand.document_id, 0)

            if current_doc_count < self.max_chunks_per_doc:
                if total_chars + cand_len <= self.max_total_chars and len(selected) < effective_max_chunks:
                    selected.append(cand)
                    doc_counts[cand.document_id] = current_doc_count + 1
                    total_chars += cand_len
            else:
                deferred.append(cand)

        # Pass 2: If slots remain and budget permits, fill remaining slots from deferred
        if len(selected) < effective_max_chunks:
            for cand in deferred:
                cand_len = len(cand.text)
                if total_chars + cand_len <= self.max_total_chars and len(selected) < effective_max_chunks:
                    selected.append(cand)
                    total_chars += cand_len

        return selected
