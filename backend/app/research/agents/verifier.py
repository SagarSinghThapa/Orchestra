from datetime import datetime
import logging
from typing import Optional
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentStatus
from app.research.agents.aggregator import AggregatedEvidence
from app.research.schemas import (
    DraftResearchAnswer,
    ResearchClaim,
    VerifiedCitation,
)

logger = logging.getLogger(__name__)

CANONICAL_INSUFFICIENT_EVIDENCE_ANSWER = (
    "The indexed sources do not provide enough evidence to answer this question reliably."
)


class CitationVerifier:
    """
    Deterministically verifies claim citations against live PostgreSQL document metadata
    and immutable Qdrant chunk provenance from Phase 05.
    Assembles final research answer strictly from verified claims.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _is_timestamp_fresh(
        retrieved_updated_at: Optional[datetime],
        current_updated_at: Optional[datetime],
        tolerance_seconds: float = 0.001,
    ) -> bool:
        """
        Validates whether evidence was captured from the current document index version.
        Normalizes tzinfo and handles sub-millisecond precision safely.
        """
        if retrieved_updated_at is None or current_updated_at is None:
            return True
        t1 = retrieved_updated_at.replace(tzinfo=None) if retrieved_updated_at.tzinfo else retrieved_updated_at
        t2 = current_updated_at.replace(tzinfo=None) if current_updated_at.tzinfo else current_updated_at
        return abs((t1 - t2).total_seconds()) < tolerance_seconds

    def verify(
        self,
        project_id: int,
        draft: DraftResearchAnswer,
        evidence_pool: list[AggregatedEvidence],
    ) -> tuple[list[ResearchClaim], list[VerifiedCitation], str, bool]:
        """
        Validates claim citations against candidate evidence pool and database document records.

        Returns:
            tuple of (verified_claims, verified_citations, final_answer, is_sufficient)
        """
        # If model explicitly reported insufficient evidence
        if not draft.has_sufficient_evidence or not draft.claims:
            return ([], [], CANONICAL_INSUFFICIENT_EVIDENCE_ANSWER, False)

        # 1. Build lookup dictionary for candidate evidence items
        evidence_id_map: dict[str, AggregatedEvidence] = {}
        for i, item in enumerate(evidence_pool):
            evidence_id_map[f"evidence_{i}"] = item
            # Also register original evidence_id in case model referenced it directly
            evidence_id_map[item.evidence_id] = item

        # 2. Relational Verification & TOCTOU Freshness check against PostgreSQL
        doc_ids = {item.document_id for item in evidence_pool}
        valid_documents = (
            self.db.query(Document)
            .filter(
                Document.id.in_(doc_ids),
                Document.project_id == project_id,
                Document.status == DocumentStatus.INDEXED.value,
            )
            .all()
        )
        valid_doc_ids = {doc.id for doc in valid_documents}
        doc_map = {doc.id: doc for doc in valid_documents}

        # 3. Verify claim citations and strip ungrounded claims
        verified_claims_raw: list[tuple[str, list[AggregatedEvidence]]] = []

        for draft_claim in draft.claims:
            claim_text = draft_claim.claim_text.strip()
            if not claim_text:
                continue

            verified_items_for_claim: list[AggregatedEvidence] = []
            for eid in draft_claim.supporting_evidence_ids:
                cleaned_eid = eid.strip()
                if cleaned_eid not in evidence_id_map:
                    # Hallucinated or unknown evidence ID -> STRIP
                    logger.debug("Stripping unknown evidence ID: %s", cleaned_eid)
                    continue

                item = evidence_id_map[cleaned_eid]

                # Check document ownership, liveness, and status
                if item.document_id not in valid_doc_ids:
                    logger.debug(
                        "Stripping evidence ID %s: document %s is unowned, deleted, or unindexed",
                        cleaned_eid,
                        item.document_id,
                    )
                    continue

                # Check TOCTOU freshness against live document index version
                current_doc = doc_map[item.document_id]
                if not self._is_timestamp_fresh(item.document_updated_at, current_doc.updated_at):
                    logger.debug(
                        "Stripping evidence ID %s: document %s has been reindexed (stale citation: retrieved_at=%s, live_at=%s)",
                        cleaned_eid,
                        item.document_id,
                        item.document_updated_at,
                        current_doc.updated_at,
                    )
                    continue

                # Check offset and page validity
                if item.page_number < 1 or item.start_char >= item.end_char:
                    logger.debug("Stripping evidence ID %s: invalid offsets or page", cleaned_eid)
                    continue

                if item not in verified_items_for_claim:
                    verified_items_for_claim.append(item)

            # Strict factual grounding rule: drop claims that have zero verified supporting evidence
            if verified_items_for_claim:
                verified_claims_raw.append((claim_text, verified_items_for_claim))

        # 4. Check whether any verified claims remain
        if not verified_claims_raw:
            return ([], [], CANONICAL_INSUFFICIENT_EVIDENCE_ANSWER, False)

        # 5. Build unique citation list with user-facing labels ([C1], [C2], ...)
        unique_citation_map: dict[str, tuple[str, VerifiedCitation]] = {}
        citation_counter = 1

        for _, items in verified_claims_raw:
            for item in items:
                if item.chunk_id not in unique_citation_map:
                    label = f"[C{citation_counter}]"
                    citation_obj = VerifiedCitation(
                        citation_id=label,
                        evidence_id=item.evidence_id,
                        document_id=item.document_id,
                        document_filename=item.document_filename,
                        page_number=item.page_number,
                        chunk_id=item.chunk_id,
                        start_char=item.start_char,
                        end_char=item.end_char,
                        text=item.text,
                        score=item.score,
                    )
                    unique_citation_map[item.chunk_id] = (label, citation_obj)
                    citation_counter += 1

        # 6. Map claim citations to labels and build deterministic final answer
        final_claims: list[ResearchClaim] = []
        answer_segments: list[str] = []

        for claim_text, items in verified_claims_raw:
            claim_citation_labels = [unique_citation_map[item.chunk_id][0] for item in items]
            final_claims.append(
                ResearchClaim(
                    claim_text=claim_text,
                    citation_ids=claim_citation_labels,
                )
            )
            labels_str = " ".join(claim_citation_labels)
            answer_segments.append(f"{claim_text} {labels_str}".strip())

        final_answer = " ".join(answer_segments)
        verified_citations_list = [entry[1] for entry in unique_citation_map.values()]

        return (final_claims, verified_citations_list, final_answer, True)
