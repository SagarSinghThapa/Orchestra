import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document
from app.models.project import Project
from app.models.user import User
from app.research.exceptions import ConfigurationError
from app.research.retrieval.citation import CitationAnchorBuilder
from app.research.retrieval.dedup import ChunkDeduplicator
from app.research.retrieval.rerank import (
    DeterministicTestReranker,
    PassThroughReranker,
    get_reranker,
)
from app.research.retrieval.schemas import SearchResultChunk


def _make_chunk(
    chunk_id: str,
    doc_id: int = 1,
    page: int = 1,
    start: int = 0,
    end: int = 100,
    text: str = "Sample chunk text",
    score: float = 0.5,
) -> SearchResultChunk:
    return SearchResultChunk(
        chunk_id=chunk_id,
        document_id=doc_id,
        project_id=1,
        text=text,
        chunk_index=0,
        page_number=page,
        start_char=start,
        end_char=end,
        score=score,
        source_engine="hybrid",
    )


class TestRerankers:
    @pytest.mark.asyncio
    async def test_passthrough_reranker(self):
        reranker = PassThroughReranker()
        candidates = [_make_chunk("c1", score=0.9), _make_chunk("c2", score=0.8), _make_chunk("c3", score=0.7)]
        results = await reranker.rerank("any query", candidates, limit=2)
        assert len(results) == 2
        assert results[0].chunk_id == "c1"
        assert results[1].chunk_id == "c2"

    @pytest.mark.asyncio
    async def test_deterministic_test_reranker_boosts_matching_keywords(self):
        reranker = DeterministicTestReranker()
        candidates = [
            _make_chunk("c1", text="generic system architecture notes", score=0.9),
            _make_chunk("c2", text="PostgreSQL relational database transaction management", score=0.5),
        ]
        results = await reranker.rerank("PostgreSQL database", candidates, limit=2)
        assert len(results) == 2
        # c2 has high overlap with query, should be boosted to top
        assert results[0].chunk_id == "c2"
        assert results[0].rerank_score is not None

    def test_production_guard_rejects_test_reranker(self, monkeypatch):
        monkeypatch.setattr(settings, "environment", "production")
        with pytest.raises(ConfigurationError) as exc_info:
            get_reranker(provider_name="test")
        assert "cannot be enabled in production" in str(exc_info.value)


class TestChunkDeduplicator:
    def test_exact_chunk_id_deduplication(self):
        dedup = ChunkDeduplicator()
        c1 = _make_chunk("chunk_1", start=0, end=100, text="Text for chunk 1", score=0.9)
        c2 = _make_chunk("chunk_1", start=0, end=100, text="Text for chunk 1 duplicate", score=0.7)  # Duplicate ID
        c3 = _make_chunk("chunk_2", start=100, end=200, text="Distinct text for chunk 2", score=0.8)

        accepted = dedup.deduplicate_chunks([c1, c2, c3])
        assert len(accepted) == 2
        assert [c.chunk_id for c in accepted] == ["chunk_1", "chunk_2"]

    def test_exact_text_deduplication(self):
        dedup = ChunkDeduplicator()
        c1 = _make_chunk("chunk_1", text="Exact duplicate text across docs", score=0.9)
        c2 = _make_chunk("chunk_2", text="Exact duplicate text across docs", score=0.8)

        accepted = dedup.deduplicate_chunks([c1, c2])
        assert len(accepted) == 1
        assert accepted[0].chunk_id == "chunk_1"

    def test_subsumed_overlap_suppression_at_90_percent(self):
        dedup = ChunkDeduplicator(max_containment_ratio=0.90)
        # c1 covers chars 0-100 on page 1
        c1 = _make_chunk("c1", doc_id=1, page=1, start=0, end=100, text="A" * 100, score=0.9)
        # c2 covers chars 5-95 (length 90) on page 1 -> 100% contained inside c1
        c2 = _make_chunk("c2", doc_id=1, page=1, start=5, end=95, text="B" * 90, score=0.8)

        accepted = dedup.deduplicate_chunks([c1, c2])
        assert len(accepted) == 1
        assert accepted[0].chunk_id == "c1"

    def test_moderate_adjacent_overlap_retained(self):
        dedup = ChunkDeduplicator(max_containment_ratio=0.90)
        # c1 covers chars 0-100
        c1 = _make_chunk("c1", doc_id=1, page=1, start=0, end=100, text="A" * 100, score=0.9)
        # c2 covers chars 80-180 (overlap is 20 chars, containment is 20/100 = 0.20 < 0.90)
        c2 = _make_chunk("c2", doc_id=1, page=1, start=80, end=180, text="C" * 100, score=0.85)

        accepted = dedup.deduplicate_chunks([c1, c2])
        # Both must be retained to avoid discarding unique evidence!
        assert len(accepted) == 2
        assert accepted[0].chunk_id == "c1"
        assert accepted[1].chunk_id == "c2"

    def test_disjoint_pages_retained(self):
        dedup = ChunkDeduplicator(max_containment_ratio=0.90)
        # Same offsets but different pages
        c1 = _make_chunk("c1", doc_id=1, page=1, start=0, end=100, text="Page 1 text", score=0.9)
        c2 = _make_chunk("c2", doc_id=1, page=2, start=0, end=100, text="Page 2 text", score=0.8)

        accepted = dedup.deduplicate_chunks([c1, c2])
        assert len(accepted) == 2


class TestCitationAnchorBuilder:
    def test_citation_anchor_builder_batched_query(self, db_session: Session, test_user: User, test_project: Project):
        # Create 2 documents in DB
        doc1 = Document(
            project_id=test_project.id,
            original_filename="research_paper_quantum.pdf",
            storage_key="projects/1/quantum.pdf",
            content_type="application/pdf",
            size_bytes=1024,
            checksum="hash1",
        )
        doc2 = Document(
            project_id=test_project.id,
            original_filename="whitepaper_distributed.txt",
            storage_key="projects/1/dist.txt",
            content_type="text/plain",
            size_bytes=2048,
            checksum="hash2",
        )
        db_session.add_all([doc1, doc2])
        db_session.commit()
        db_session.refresh(doc1)
        db_session.refresh(doc2)

        candidates = [
            _make_chunk("chk_1", doc_id=doc1.id, page=2, start=120, end=350, text="Quantum teleportation protocol", score=0.95),
            _make_chunk("chk_2", doc_id=doc2.id, page=1, start=0, end=200, text="Distributed consensus algorithms", score=0.88),
        ]

        builder = CitationAnchorBuilder(db_session)
        citations = builder.build_citations(candidates)

        assert len(citations) == 2

        # Verify Doc 1 Citation
        cite1 = citations[0]
        assert cite1.evidence_id == f"cite_{doc1.id}_chk_1"
        assert cite1.document_id == doc1.id
        assert cite1.document_filename == "research_paper_quantum.pdf"
        assert cite1.page_number == 2
        assert cite1.start_char == 120
        assert cite1.end_char == 350
        assert cite1.text == "Quantum teleportation protocol"
        assert cite1.score == 0.95

        # Verify Doc 2 Citation
        cite2 = citations[1]
        assert cite2.evidence_id == f"cite_{doc2.id}_chk_2"
        assert cite2.document_id == doc2.id
        assert cite2.document_filename == "whitepaper_distributed.txt"
        assert cite2.page_number == 1
        assert cite2.start_char == 0
        assert cite2.end_char == 200
        assert cite2.text == "Distributed consensus algorithms"
        assert cite2.score == 0.88
