from typing import Optional

from sqlalchemy.orm import Session

from app.models.document import Document
from app.research.retrieval.schemas import CitationEvidence, SearchResultChunk


class CitationAnchorBuilder:
    """
    Enriches retrieval candidates with relational Document metadata to produce
    citation-ready evidence structures with verified provenance offsets.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def build_citations(
        self,
        candidates: list[SearchResultChunk],
        project_id: Optional[int] = None,
    ) -> list[CitationEvidence]:
        if not candidates:
            return []

        # 1. Collect unique document IDs to avoid N+1 queries
        doc_ids = list({c.document_id for c in candidates})

        # 2. Perform a single batched relational query scoped to project_id when provided
        query = self.db.query(Document).filter(Document.id.in_(doc_ids))
        if project_id is not None:
            query = query.filter(Document.project_id == project_id)
        docs = query.all()
        doc_map = {d.id: d.original_filename for d in docs}

        # 3. Construct CitationEvidence items preserving provenance
        citations: list[CitationEvidence] = []
        for c in candidates:
            # Foreign-project isolation defense-in-depth:
            # If project_id is specified, drop candidates referencing documents that cannot be
            # resolved inside the requested project to prevent foreign metadata leakage.
            if project_id is not None and c.document_id not in doc_map:
                continue

            filename = doc_map.get(c.document_id, f"document_{c.document_id}.txt")
            evidence_id = f"cite_{c.document_id}_{c.chunk_id}"

            citations.append(
                CitationEvidence(
                    evidence_id=evidence_id,
                    document_id=c.document_id,
                    document_filename=filename,
                    page_number=c.page_number,
                    chunk_id=c.chunk_id,
                    chunk_index=c.chunk_index,
                    start_char=c.start_char,
                    end_char=c.end_char,
                    text=c.text,
                    score=c.score,
                    dense_score=c.dense_score,
                    sparse_score=c.sparse_score,
                    dense_rank=c.dense_rank,
                    sparse_rank=c.sparse_rank,
                )
            )

        return citations
