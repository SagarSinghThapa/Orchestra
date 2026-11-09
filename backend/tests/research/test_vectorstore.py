import pytest
from uuid import NAMESPACE_URL, uuid5

from app.research.chunking.base import DocumentChunk
from app.research.exceptions import ConfigurationError, VectorStoreError
from app.research.vectorstore.qdrant import QdrantVectorStore


class TestQdrantVectorStore:
    @pytest.mark.asyncio
    async def test_dynamic_collection_creation(self):
        store = QdrantVectorStore(location=":memory:", collection_name="test_col_dynamic")
        try:
            await store.ensure_collection(dimension=1536)
            client = await store._get_client()
            info = await client.get_collection("test_col_dynamic")
            assert info.config.params.vectors.size == 1536
        finally:
            await store.close()

    @pytest.mark.asyncio
    async def test_dimension_mismatch_raises_configuration_error(self):
        store = QdrantVectorStore(location=":memory:", collection_name="test_col_mismatch")
        try:
            # First ensure collection with dimension 768
            await store.ensure_collection(dimension=768)

            # Subsequent call attempting dimension 1536 must fail fast
            with pytest.raises(
                ConfigurationError,
                match="vector dimension 768, but embedding provider is configured for dimension 1536",
            ):
                await store.ensure_collection(dimension=1536)
        finally:
            await store.close()

    @pytest.mark.asyncio
    async def test_upsert_chunks_with_tenant_uuid5(self):
        store = QdrantVectorStore(location=":memory:", collection_name="test_col_upsert")
        try:
            await store.ensure_collection(dimension=4)

            chunks = [
                DocumentChunk(
                    chunk_id="doc_10_chk_0",
                    document_id=10,
                    project_id=100,
                    text="Chunk alpha on AI systems.",
                    chunk_index=0,
                    page_number=1,
                    start_char=0,
                    end_char=26,
                    token_count=6,
                ),
                DocumentChunk(
                    chunk_id="doc_10_chk_1",
                    document_id=10,
                    project_id=100,
                    text="Chunk beta on LLM pipelines.",
                    chunk_index=1,
                    page_number=1,
                    start_char=27,
                    end_char=55,
                    token_count=7,
                ),
            ]
            vectors = [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
            ]

            await store.upsert_chunks(chunks, vectors)

            # Verify deterministic point IDs
            client = await store._get_client()
            expected_id_0 = str(uuid5(NAMESPACE_URL, "proj_100_doc_10_chk_0"))
            expected_id_1 = str(uuid5(NAMESPACE_URL, "proj_100_doc_10_chk_1"))

            points = await client.retrieve("test_col_upsert", ids=[expected_id_0, expected_id_1])
            assert len(points) == 2
            ids_retrieved = {str(p.id) for p in points}
            assert expected_id_0 in ids_retrieved
            assert expected_id_1 in ids_retrieved
            assert points[0].payload["project_id"] == 100
        finally:
            await store.close()

    @pytest.mark.asyncio
    async def test_cross_project_isolation(self):
        store = QdrantVectorStore(location=":memory:", collection_name="test_col_isolation")
        try:
            await store.ensure_collection(dimension=4)

            # Project 1 chunks
            p1_chunks = [
                DocumentChunk(
                    chunk_id="doc_1_chk_0",
                    document_id=1,
                    project_id=1,
                    text="Secret roadmap for project 1",
                    chunk_index=0,
                    page_number=1,
                    start_char=0,
                    end_char=28,
                    token_count=7,
                )
            ]
            # Project 2 chunks
            p2_chunks = [
                DocumentChunk(
                    chunk_id="doc_2_chk_0",
                    document_id=2,
                    project_id=2,
                    text="Public notes for project 2",
                    chunk_index=0,
                    page_number=1,
                    start_char=0,
                    end_char=26,
                    token_count=6,
                )
            ]

            vec = [1.0, 0.0, 0.0, 0.0]
            await store.upsert_chunks(p1_chunks, [vec])
            await store.upsert_chunks(p2_chunks, [vec])

            # Query with project_id=1
            results_p1 = await store.search(project_id=1, query_vector=vec, limit=10)
            assert len(results_p1) == 1
            assert results_p1[0].payload["project_id"] == 1
            assert results_p1[0].payload["text"] == "Secret roadmap for project 1"

            # Query with project_id=2
            results_p2 = await store.search(project_id=2, query_vector=vec, limit=10)
            assert len(results_p2) == 1
            assert results_p2[0].payload["project_id"] == 2
            assert results_p2[0].payload["text"] == "Public notes for project 2"

            # Query with non-existent project 999
            results_empty = await store.search(project_id=999, query_vector=vec, limit=10)
            assert len(results_empty) == 0
        finally:
            await store.close()

    @pytest.mark.asyncio
    async def test_scoped_deletion(self):
        store = QdrantVectorStore(location=":memory:", collection_name="test_col_delete")
        try:
            await store.ensure_collection(dimension=4)
            vec = [1.0, 0.0, 0.0, 0.0]

            # Project 1 Document 1
            c1 = DocumentChunk("c1", 1, 1, "P1 D1 text", 0, 1, 0, 10, 2)
            # Project 2 Document 1 (same document_id but different project_id)
            c2 = DocumentChunk("c2", 1, 2, "P2 D1 text", 0, 1, 0, 10, 2)

            await store.upsert_chunks([c1], [vec])
            await store.upsert_chunks([c2], [vec])

            # Delete Project 1 Document 1
            await store.delete_document_vectors(project_id=1, document_id=1)

            # Project 1 should now be empty
            p1_res = await store.search(project_id=1, query_vector=vec)
            assert len(p1_res) == 0

            # Project 2 Document 1 must remain intact
            p2_res = await store.search(project_id=2, query_vector=vec)
            assert len(p2_res) == 1
            assert p2_res[0].payload["project_id"] == 2
        finally:
            await store.close()

    @pytest.mark.asyncio
    async def test_idempotent_delete_on_missing_document(self):
        store = QdrantVectorStore(location=":memory:", collection_name="test_col_idempotent")
        try:
            await store.ensure_collection(dimension=4)
            # Deleting non-existent document vectors must not raise an error
            await store.delete_document_vectors(project_id=999, document_id=999)
        finally:
            await store.close()

    @pytest.mark.asyncio
    async def test_absent_collection_returns_empty_results(self):
        """Optional fix: Non-existent collection returns empty results cleanly without raising errors."""
        store = QdrantVectorStore(location=":memory:", collection_name="non_existent_collection_abc")
        try:
            res_search = await store.search(project_id=1, query_vector=[0.1, 0.2, 0.3, 0.4])
            assert res_search == []

            res_scroll = await store.scroll_project_chunks(project_id=1)
            assert res_scroll == []
        finally:
            await store.close()

    @pytest.mark.asyncio
    async def test_unreachable_qdrant_raises_vectorstore_error(self, monkeypatch):
        """Optional fix: Network / connection failure during collection check raises controlled VectorStoreError."""
        store = QdrantVectorStore(location=":memory:", collection_name="test_col_conn_err")
        client = await store._get_client()

        async def _mock_collection_exists_fail(_name):
            raise ConnectionError("Simulated socket connection failure to Qdrant cluster")

        monkeypatch.setattr(client, "collection_exists", _mock_collection_exists_fail)

        try:
            with pytest.raises(VectorStoreError, match="Failed to search Qdrant collection"):
                await store.search(project_id=1, query_vector=[0.1, 0.2, 0.3, 0.4])

            with pytest.raises(VectorStoreError, match="Failed to scroll chunks for project"):
                await store.scroll_project_chunks(project_id=1)
        finally:
            await store.close()

    def test_lazy_app_main_import_without_live_qdrant(self):
        # Verification that importing app.main does not trigger any network connection to Qdrant
        import app.main
        assert app.main.app is not None

