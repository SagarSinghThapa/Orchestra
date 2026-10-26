import pytest

from app.research.chunking.base import DocumentChunk
from app.research.embeddings.mock import DeterministicTestEmbeddingProvider
from app.research.exceptions import VectorStoreError
from app.research.retrieval.dense import QdrantDenseRetriever
from app.research.retrieval.fusion import ReciprocalRankFusion, WeightedScoreFusion
from app.research.retrieval.schemas import SearchResultChunk
from app.research.retrieval.sparse import BM25SparseRetriever
from app.research.vectorstore.qdrant import QdrantVectorStore


@pytest.fixture
def in_memory_store():
    return QdrantVectorStore(location=":memory:", collection_name="test_col_fusion")


@pytest.fixture
def embedding_provider():
    return DeterministicTestEmbeddingProvider(dimension=1536)


class TestQdrantScrollAndRetrievers:
    @pytest.mark.asyncio
    async def test_qdrant_scroll_project_chunks_pagination_and_isolation(self, in_memory_store):
        try:
            await in_memory_store.ensure_collection(dimension=1536)
            provider = DeterministicTestEmbeddingProvider(dimension=1536)

            # Seed 15 chunks for Project 1 across 2 documents
            p1_chunks = [
                DocumentChunk(
                    chunk_id=f"p1_c{i}",
                    document_id=101 if i < 8 else 102,
                    project_id=1,
                    text=f"Project 1 scientific text content batch {i}",
                    chunk_index=i,
                    page_number=1,
                    start_char=i * 20,
                    end_char=(i + 1) * 20,
                    token_count=5,
                )
                for i in range(15)
            ]
            # Seed 5 chunks for Project 2
            p2_chunks = [
                DocumentChunk(
                    chunk_id=f"p2_c{i}",
                    document_id=201,
                    project_id=2,
                    text=f"Project 2 confidential research notes {i}",
                    chunk_index=i,
                    page_number=1,
                    start_char=i * 20,
                    end_char=(i + 1) * 20,
                    token_count=5,
                )
                for i in range(5)
            ]

            p1_vecs = await provider.embed_documents([c.text for c in p1_chunks])
            p2_vecs = await provider.embed_documents([c.text for c in p2_chunks])

            await in_memory_store.upsert_chunks(p1_chunks, p1_vecs)
            await in_memory_store.upsert_chunks(p2_chunks, p2_vecs)

            # Test scroll with small batch_size (5) to force cursor pagination across 3 batches
            scrolled_p1 = await in_memory_store.scroll_project_chunks(project_id=1, batch_size=5)
            assert len(scrolled_p1) == 15
            assert all(c.project_id == 1 for c in scrolled_p1)

            # Test document_ids filter
            scrolled_doc101 = await in_memory_store.scroll_project_chunks(
                project_id=1, document_ids=[101], batch_size=5
            )
            assert len(scrolled_doc101) == 8
            assert all(c.document_id == 101 for c in scrolled_doc101)

            # Project 2 scroll
            scrolled_p2 = await in_memory_store.scroll_project_chunks(project_id=2)
            assert len(scrolled_p2) == 5
            assert all(c.project_id == 2 for c in scrolled_p2)

            # Non-existent project
            scrolled_empty = await in_memory_store.scroll_project_chunks(project_id=999)
            assert len(scrolled_empty) == 0
        finally:
            await in_memory_store.close()

    @pytest.mark.asyncio
    async def test_scroll_exceeds_max_chunks_limit_raises_error(self, in_memory_store, monkeypatch):
        try:
            await in_memory_store.ensure_collection(dimension=1536)
            provider = DeterministicTestEmbeddingProvider(dimension=1536)
            chunks = [
                DocumentChunk(
                    chunk_id=f"c{i}",
                    document_id=1,
                    project_id=1,
                    text=f"Sample text {i}",
                    chunk_index=i,
                    page_number=1,
                    start_char=0,
                    end_char=10,
                    token_count=2,
                )
                for i in range(10)
            ]
            vecs = await provider.embed_documents([c.text for c in chunks])
            await in_memory_store.upsert_chunks(chunks, vecs)

            from app.core.config import settings
            monkeypatch.setattr(settings, "retrieval_max_project_chunks", 5)

            with pytest.raises(VectorStoreError) as exc_info:
                await in_memory_store.scroll_project_chunks(project_id=1, batch_size=3)
            assert "exceeds maximum chunk limit" in str(exc_info.value)
        finally:
            await in_memory_store.close()

    @pytest.mark.asyncio
    async def test_dense_and_sparse_retrievers_cross_tenant_isolation(self, in_memory_store, embedding_provider):
        try:
            await in_memory_store.ensure_collection(dimension=1536)

            # Project 1 chunk: generic text
            p1_chunks = [
                DocumentChunk("p1_c1", 1, 1, "Quantum computing algorithms for factoring", 0, 1, 0, 42, 5)
            ]
            # Project 2 chunk: exact match for "CRITICAL_SECRET_KEY_12345"
            p2_chunks = [
                DocumentChunk("p2_c1", 2, 2, "CRITICAL_SECRET_KEY_12345 is confidential to project 2", 0, 1, 0, 55, 6)
            ]

            p1_vecs = await embedding_provider.embed_documents([c.text for c in p1_chunks])
            p2_vecs = await embedding_provider.embed_documents([c.text for c in p2_chunks])

            await in_memory_store.upsert_chunks(p1_chunks, p1_vecs)
            await in_memory_store.upsert_chunks(p2_chunks, p2_vecs)

            dense_retriever = QdrantDenseRetriever(in_memory_store, embedding_provider)
            sparse_retriever = BM25SparseRetriever(in_memory_store)

            # User queries Project 1 with terms matching Project 2's secret key!
            # Both dense and sparse MUST NEVER return Project 2's chunk!
            dense_res = await dense_retriever.search(project_id=1, query="CRITICAL_SECRET_KEY_12345")
            assert len(dense_res) <= 1
            if dense_res:
                assert dense_res[0].project_id == 1
                assert "CRITICAL_SECRET_KEY_12345" not in dense_res[0].text

            sparse_res = await sparse_retriever.search(project_id=1, query="CRITICAL_SECRET_KEY_12345")
            # In project 1, the secret key doesn't exist, so sparse returns 0 results
            assert len(sparse_res) == 0

            # But searching Project 2 directly returns it
            sparse_p2_res = await sparse_retriever.search(project_id=2, query="CRITICAL_SECRET_KEY_12345")
            assert len(sparse_p2_res) == 1
            assert sparse_p2_res[0].project_id == 2
            assert sparse_p2_res[0].chunk_id == "p2_c1"
        finally:
            await in_memory_store.close()


class TestReciprocalRankFusion:
    def _create_chunk(self, chunk_id: str, score: float, engine: str) -> SearchResultChunk:
        return SearchResultChunk(
            chunk_id=chunk_id,
            document_id=1,
            project_id=1,
            text=f"Text for {chunk_id}",
            chunk_index=0,
            page_number=1,
            start_char=0,
            end_char=10,
            score=score,
            source_engine=engine,
        )

    def test_rrf_identical_ranks(self):
        engine = ReciprocalRankFusion(rrf_k=60)
        # c1 is rank 1 in both
        dense = [self._create_chunk("c1", 0.95, "dense"), self._create_chunk("c2", 0.80, "dense")]
        sparse = [self._create_chunk("c1", 8.5, "sparse"), self._create_chunk("c3", 5.0, "sparse")]

        fused = engine.fuse(dense, sparse, limit=5)
        assert len(fused) == 3
        # c1 should be rank 1 with score 1/(60+1) + 1/(60+1) = 2/61
        assert fused[0].chunk_id == "c1"
        assert fused[0].dense_rank == 1
        assert fused[0].sparse_rank == 1
        expected_score = (1.0 / 61.0) + (1.0 / 61.0)
        assert pytest.approx(fused[0].score, rel=1e-5) == expected_score

    def test_rrf_disjoint_candidates(self):
        engine = ReciprocalRankFusion(rrf_k=60)
        # dense has c1, sparse has c2
        dense = [self._create_chunk("c1", 0.90, "dense")]
        sparse = [self._create_chunk("c2", 6.0, "sparse")]

        fused = engine.fuse(dense, sparse, limit=5)
        assert len(fused) == 2
        # Both have rank 1 in their respective channel, so fusion scores are identical: 1/61
        assert pytest.approx(fused[0].score, rel=1e-5) == 1.0 / 61.0
        assert pytest.approx(fused[1].score, rel=1e-5) == 1.0 / 61.0

    def test_rrf_deterministic_ties(self):
        engine = ReciprocalRankFusion(rrf_k=60)
        # Both appear only in sparse at rank 1 and rank 2? No, let's make two chunks with identical score
        sparse = [
            self._create_chunk("b_chunk", 5.0, "sparse"),
            self._create_chunk("a_chunk", 5.0, "sparse"),
        ]
        # Equal weights and rank
        dense = []
        fused = engine.fuse(dense, sparse, limit=2)
        assert len(fused) == 2
        # rank 1 is b_chunk, rank 2 is a_chunk -> b_chunk has score 1/61, a_chunk has 1/62
        assert fused[0].chunk_id == "b_chunk"
        assert fused[1].chunk_id == "a_chunk"

    def test_rrf_weight_influence(self):
        engine = ReciprocalRankFusion(rrf_k=60)
        dense = [self._create_chunk("dense_top", 0.9, "dense")]
        sparse = [self._create_chunk("sparse_top", 5.0, "sparse")]

        # When sparse_weight is 3.0 and dense_weight is 1.0:
        # sparse_top receives 3.0 / 61, dense_top receives 1.0 / 61
        fused = engine.fuse(dense, sparse, limit=2, dense_weight=1.0, sparse_weight=3.0)
        assert fused[0].chunk_id == "sparse_top"
        assert fused[1].chunk_id == "dense_top"

    def test_rrf_empty_inputs(self):
        engine = ReciprocalRankFusion(rrf_k=60)
        assert engine.fuse([], [], limit=5) == []
