import os
import pytest
from qdrant_client import AsyncQdrantClient, models

from app.research.chunking.base import DocumentChunk
from app.research.exceptions import ConfigurationError
from app.research.vectorstore.qdrant import QdrantVectorStore


TEST_QDRANT_URL = os.getenv(
    "TEST_QDRANT_URL",
    os.getenv(
        "QDRANT_URL",
        "http://127.0.0.1:6334",
    ),
)


@pytest.fixture(scope="module")
def qdrant_test_url():
    assert TEST_QDRANT_URL != ":memory:", "Integration test requires live external Qdrant server, not :memory:"
    assert TEST_QDRANT_URL.startswith("http"), f"Invalid Qdrant URL: {TEST_QDRANT_URL}"
    return TEST_QDRANT_URL


@pytest.mark.asyncio
@pytest.mark.integration
async def test_qdrant_live_collection_initialization_and_dimension_guard(qdrant_test_url):
    """
    Validates that QdrantVectorStore connects to live Qdrant, dynamically provisions
    the collection with the expected 1536 vector dimension and Cosine distance, and
    rejects conflicting dimensions with ConfigurationError.
    """
    collection_name = "test_live_dimension_guard"
    client = AsyncQdrantClient(url=qdrant_test_url, timeout=5.0)

    try:
        if await client.collection_exists(collection_name):
            await client.delete_collection(collection_name)

        store = QdrantVectorStore(
            client=client,
            url=qdrant_test_url,
            collection_name=collection_name,
        )

        # 1. Initialize with dimension 1536 (Orchestra production standard)
        await store.ensure_collection(dimension=1536)

        # 2. Assert collection exists and has size 1536
        info = await client.get_collection(collection_name)
        assert info.status == models.CollectionStatus.GREEN
        assert info.config.params.vectors.size == 1536
        assert info.config.params.vectors.distance == models.Distance.COSINE

        # 3. Assert idempotent call with matching dimension succeeds
        await store.ensure_collection(dimension=1536)

        # 4. Assert dimension mismatch raises ConfigurationError without data corruption
        with pytest.raises(ConfigurationError) as exc_info:
            await store.ensure_collection(dimension=384)
        assert "dimension" in str(exc_info.value).lower()

    finally:
        if await client.collection_exists(collection_name):
            await client.delete_collection(collection_name)
        await client.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_qdrant_dense_vector_indexing_and_multitenant_filtering(qdrant_test_url):
    """
    Validates dense vector upsert of 100 chunks across two projects, and confirms
    strict multi-tenant payload isolation: project A queries NEVER return project B points.
    """
    collection_name = "test_live_multitenant_isolation"
    client = AsyncQdrantClient(url=qdrant_test_url, timeout=5.0)

    try:
        if await client.collection_exists(collection_name):
            await client.delete_collection(collection_name)

        store = QdrantVectorStore(
            client=client,
            url=qdrant_test_url,
            collection_name=collection_name,
        )
        await store.ensure_collection(dimension=1536)

        # Prepare 100 chunks: 50 for Project 1001, 50 for Project 2002
        chunks: list[DocumentChunk] = []
        vectors: list[list[float]] = []

        # Project A chunks
        for i in range(50):
            chunks.append(
                DocumentChunk(
                    chunk_id=f"chk_a_{i}",
                    document_id=101,
                    project_id=1001,
                    text=f"Project Alpha architecture chunk content {i}",
                    chunk_index=i,
                    page_number=1 + (i // 10),
                    start_char=i * 100,
                    end_char=(i + 1) * 100,
                    token_count=25,
                )
            )
            # Vector strongly biased on dimension 0
            vec = [0.0] * 1536
            vec[0] = 0.95
            vec[1] = 0.05 * (i / 50.0)
            vectors.append(vec)

        # Project B chunks
        for i in range(50):
            chunks.append(
                DocumentChunk(
                    chunk_id=f"chk_b_{i}",
                    document_id=202,
                    project_id=2002,
                    text=f"Project Beta confidential data chunk content {i}",
                    chunk_index=i,
                    page_number=1 + (i // 10),
                    start_char=i * 100,
                    end_char=(i + 1) * 100,
                    token_count=25,
                )
            )
            # Vector strongly biased on dimension 500
            vec = [0.0] * 1536
            vec[500] = 0.95
            vec[501] = 0.05 * (i / 50.0)
            vectors.append(vec)

        # Batch upsert 100 chunks
        await store.upsert_chunks(chunks, vectors)

        # Confirm 100 points indexed
        count_info = await client.count(collection_name)
        assert count_info.count == 100

        # Query biased towards Project A with Project A filter (1001)
        query_a = [0.0] * 1536
        query_a[0] = 1.0
        results_a = await store.search(project_id=1001, query_vector=query_a, limit=10)
        assert len(results_a) > 0
        for pt in results_a:
            assert pt.payload["project_id"] == 1001
            assert pt.payload["document_id"] == 101
            assert "Project Alpha" in pt.payload["text"]

        # Query biased towards Project B with Project A filter (1001)
        # Even with query vector matching Project B, Project A filter MUST return 0 Project B points!
        query_b = [0.0] * 1536
        query_b[500] = 1.0
        results_cross = await store.search(project_id=1001, query_vector=query_b, limit=10)
        for pt in results_cross:
            assert pt.payload["project_id"] == 1001, f"Tenant leakage! Found point for project {pt.payload['project_id']}"

        # Query with Project B filter (2002)
        results_b = await store.search(project_id=2002, query_vector=query_b, limit=10)
        assert len(results_b) > 0
        for pt in results_b:
            assert pt.payload["project_id"] == 2002
            assert pt.payload["document_id"] == 202
            assert "Project Beta" in pt.payload["text"]

    finally:
        if await client.collection_exists(collection_name):
            await client.delete_collection(collection_name)
        await client.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_qdrant_document_deletion_synchronization(qdrant_test_url):
    """
    Validates document deletion synchronization:
    Calling delete_document_vectors purges points for the target document under the project,
    while leaving other project points intact.
    """
    collection_name = "test_live_deletion_sync"
    client = AsyncQdrantClient(url=qdrant_test_url, timeout=5.0)

    try:
        if await client.collection_exists(collection_name):
            await client.delete_collection(collection_name)

        store = QdrantVectorStore(
            client=client,
            url=qdrant_test_url,
            collection_name=collection_name,
        )
        await store.ensure_collection(dimension=1536)

        # Upsert 10 chunks for Doc 1, 10 chunks for Doc 2 under project 500
        chunks = []
        vectors = []
        for i in range(10):
            chunks.append(
                DocumentChunk(
                    chunk_id=f"c1_{i}",
                    document_id=1,
                    project_id=500,
                    text=f"Doc 1 chunk {i}",
                    chunk_index=i,
                    page_number=1,
                    start_char=i * 10,
                    end_char=(i + 1) * 10,
                    token_count=5,
                )
            )
            vec = [0.1] * 1536
            vectors.append(vec)

        for i in range(10):
            chunks.append(
                DocumentChunk(
                    chunk_id=f"c2_{i}",
                    document_id=2,
                    project_id=500,
                    text=f"Doc 2 chunk {i}",
                    chunk_index=i,
                    page_number=1,
                    start_char=i * 10,
                    end_char=(i + 1) * 10,
                    token_count=5,
                )
            )
            vec = [0.2] * 1536
            vectors.append(vec)

        await store.upsert_chunks(chunks, vectors)

        count_before = await client.count(collection_name)
        assert count_before.count == 20

        # Purge Doc 1 vectors
        await store.delete_document_vectors(project_id=500, document_id=1)

        # Verify Doc 1 is gone from search
        results_doc1 = await store.search(
            project_id=500,
            query_vector=[0.1] * 1536,
            document_ids=[1],
            limit=10,
        )
        assert len(results_doc1) == 0

        # Verify Doc 2 vectors remain
        results_doc2 = await store.search(
            project_id=500,
            query_vector=[0.2] * 1536,
            document_ids=[2],
            limit=10,
        )
        assert len(results_doc2) == 10

    finally:
        if await client.collection_exists(collection_name):
            await client.delete_collection(collection_name)
        await client.close()
