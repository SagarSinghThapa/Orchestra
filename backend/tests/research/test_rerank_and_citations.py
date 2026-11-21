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
        c1 = _make_chunk("chunk_1", doc_id=1, page=1, start=0, end=100, text="Text for chunk 1", score=0.9)
        c2 = _make_chunk("chunk_1", doc_id=2, page=5, start=0, end=100, text="Different text duplicate ID", score=0.7)
        c3 = _make_chunk("chunk_2", doc_id=1, page=1, start=100, end=200, text="Distinct text for chunk 2", score=0.8)

        accepted = dedup.deduplicate_chunks([c1, c2, c3])
        assert len(accepted) == 2
        assert [c.chunk_id for c in accepted] == ["chunk_1", "chunk_2"]

    def test_exact_text_deduplication_same_provenance(self):
        dedup = ChunkDeduplicator()
        c1 = _make_chunk("chunk_1", doc_id=1, page=1, text="Exact duplicate text same page", score=0.9)
        c2 = _make_chunk("chunk_2", doc_id=1, page=1, text="Exact duplicate text same page", score=0.8)

        accepted = dedup.deduplicate_chunks([c1, c2])
        assert len(accepted) == 1
        assert accepted[0].chunk_id == "chunk_1"

    def test_cross_document_identical_text_retained(self):
        """Fix 1: Identical text appearing in different documents represents independent evidence and must not be collapsed."""
        dedup = ChunkDeduplicator()
        text = "The model achieved 94% accuracy."
        c1 = _make_chunk("chunk_docA_p2", doc_id=10, page=2, text=text, score=0.92)
        c2 = _make_chunk("chunk_docB_p8", doc_id=20, page=8, text=text, score=0.85)

        accepted = dedup.deduplicate_chunks([c1, c2])
        assert len(accepted) == 2
        assert accepted[0].chunk_id == "chunk_docA_p2"
        assert accepted[1].chunk_id == "chunk_docB_p8"

    def test_cross_page_identical_text_retained(self):
        """Fix 1: Identical text on different pages of the same document must remain independently retrievable."""
        dedup = ChunkDeduplicator()
        text = "Recurring header or repeated finding across chapters."
        c1 = _make_chunk("chunk_p1", doc_id=1, page=1, text=text, score=0.90)
        c2 = _make_chunk("chunk_p2", doc_id=1, page=2, text=text, score=0.80)

        accepted = dedup.deduplicate_chunks([c1, c2])
        assert len(accepted) == 2
        assert accepted[0].chunk_id == "chunk_p1"
        assert accepted[1].chunk_id == "chunk_p2"

    def test_short_accepted_and_long_candidate_retained(self):
        """Fix 2: Accepted chunk is 50 chars, candidate is 500 chars (overlap 50 chars). Candidate must NOT be suppressed."""
        dedup = ChunkDeduplicator(max_containment_ratio=0.90)
        # Accepted chunk: 50 chars
        c1 = _make_chunk("short_accepted", doc_id=1, page=1, start=0, end=50, text="A" * 50, score=0.95)
        # Candidate chunk: 500 chars (50 chars overlap / 500 chars candidate = 0.10 containment < 0.90)
        c2 = _make_chunk("long_candidate", doc_id=1, page=1, start=0, end=500, text="A" * 50 + "B" * 450, score=0.85)

        accepted = dedup.deduplicate_chunks([c1, c2])
        assert len(accepted) == 2
        assert accepted[0].chunk_id == "short_accepted"
        assert accepted[1].chunk_id == "long_candidate"

    def test_long_accepted_and_nearly_contained_short_candidate_suppressed(self):
        """Fix 2: Accepted chunk is 500 chars, candidate is 50 chars nearly contained. Candidate MUST be suppressed."""
        dedup = ChunkDeduplicator(max_containment_ratio=0.90)
        # Accepted chunk: 500 chars (0-500)
        c1 = _make_chunk("long_accepted", doc_id=1, page=1, start=0, end=500, text="A" * 500, score=0.95)
        # Candidate chunk: 50 chars (10-60) -> 100% overlap with c1
        c2 = _make_chunk("short_candidate", doc_id=1, page=1, start=10, end=60, text="A" * 50, score=0.80)

        accepted = dedup.deduplicate_chunks([c1, c2])
        assert len(accepted) == 1
        assert accepted[0].chunk_id == "long_accepted"

    def test_moderate_adjacent_overlap_retained(self):
        """Fix 2: Moderate overlap below 90% (e.g. 20%) must be retained."""
        dedup = ChunkDeduplicator(max_containment_ratio=0.90)
        c1 = _make_chunk("c1", doc_id=1, page=1, start=0, end=100, text="A" * 100, score=0.9)
        c2 = _make_chunk("c2", doc_id=1, page=1, start=80, end=180, text="C" * 100, score=0.85)

        accepted = dedup.deduplicate_chunks([c1, c2])
        assert len(accepted) == 2
        assert accepted[0].chunk_id == "c1"
        assert accepted[1].chunk_id == "c2"

    def test_overlap_different_pages_both_retained(self):
        """Fix 2: Candidates on different pages are not subject to overlap suppression."""
        dedup = ChunkDeduplicator(max_containment_ratio=0.90)
        c1 = _make_chunk("c1", doc_id=1, page=1, start=0, end=100, text="Page 1", score=0.9)
        c2 = _make_chunk("c2", doc_id=1, page=2, start=0, end=100, text="Page 2", score=0.8)

        accepted = dedup.deduplicate_chunks([c1, c2])
        assert len(accepted) == 2

    def test_overlap_different_documents_both_retained(self):
        """Fix 2: Candidates in different documents are not subject to overlap suppression."""
        dedup = ChunkDeduplicator(max_containment_ratio=0.90)
        c1 = _make_chunk("c1", doc_id=1, page=1, start=0, end=100, text="Doc 1", score=0.9)
        c2 = _make_chunk("c2", doc_id=2, page=1, start=0, end=100, text="Doc 2", score=0.8)

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
        citations = builder.build_citations(candidates, project_id=test_project.id)

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

    def test_citation_project_defense_in_depth_no_foreign_metadata_leakage(
        self, db_session: Session, test_user: User, test_project: Project, test_project_b: Project
    ):
        """Fix 3: Retrieval candidate referencing foreign Project B document must never leak Project B metadata."""
        # Project A document
        doc_a = Document(
            project_id=test_project.id,
            original_filename="project_a_public_report.pdf",
            storage_key="projects/a/report.pdf",
            content_type="application/pdf",
            size_bytes=1000,
            checksum="hash_proj_a",
        )
        # Foreign Project B document containing confidential information
        doc_b = Document(
            project_id=test_project_b.id,
            original_filename="confidential_secret_project_b.pdf",
            storage_key="projects/b/secret.pdf",
            content_type="application/pdf",
            size_bytes=2000,
            checksum="hash_proj_b",
        )
        db_session.add_all([doc_a, doc_b])
        db_session.commit()
        db_session.refresh(doc_a)
        db_session.refresh(doc_b)

        # Candidates contain 1 valid Project A candidate, plus 1 corrupted/foreign candidate pointing to doc_b
        candidates = [
            _make_chunk("chk_valid_a", doc_id=doc_a.id, page=1, text="Legitimate Project A chunk", score=0.9),
            _make_chunk("chk_foreign_b", doc_id=doc_b.id, page=1, text="Foreign candidate chunk", score=0.8),
        ]

        builder = CitationAnchorBuilder(db_session)
        citations = builder.build_citations(candidates, project_id=test_project.id)

        # Must only return Project A citation; foreign document is dropped and its filename is NEVER returned
        assert len(citations) == 1
        assert citations[0].document_id == doc_a.id
        assert citations[0].document_filename == "project_a_public_report.pdf"

        # Explicit assertion proving Project B filename is nowhere in the result
        for cite in citations:
            assert cite.document_filename != "confidential_secret_project_b.pdf"
            assert "secret" not in cite.document_filename
