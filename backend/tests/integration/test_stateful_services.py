import os
import pytest
import pytest_asyncio
from sqlalchemy import create_engine, text
import redis.asyncio as aioredis
from qdrant_client import AsyncQdrantClient, models


TEST_PG_URL = os.getenv(
    "TEST_DATABASE_URL",
    os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:replace_with_strong_postgres_password_here@127.0.0.1:5433/orchestra",
    ),
)
TEST_REDIS_URL = os.getenv(
    "TEST_REDIS_URL",
    os.getenv(
        "REDIS_URL",
        "redis://:replace_with_strong_redis_password_here@127.0.0.1:6380/0",
    ),
)
TEST_QDRANT_URL = os.getenv(
    "TEST_QDRANT_URL",
    os.getenv(
        "QDRANT_URL",
        "http://127.0.0.1:6334",
    ),
)


@pytest.mark.integration
def test_postgres_live_connection_and_dialect():
    """
    Verifies that the database connection connects to a real PostgreSQL 16 server
    and strictly enforces the postgresql dialect (not SQLite or mock).
    """
    engine = create_engine(TEST_PG_URL, pool_pre_ping=True)
    try:
        assert engine.dialect.name == "postgresql", f"Expected postgresql dialect, got {engine.dialect.name}"

        with engine.connect() as conn:
            # Query version string
            version_row = conn.execute(text("SELECT version();")).scalar()
            assert version_row is not None
            assert "PostgreSQL" in version_row, f"Version string does not indicate PostgreSQL: {version_row}"

            # Query current database
            current_db = conn.execute(text("SELECT current_database();")).scalar()
            assert current_db in ("orchestra", "orchestra_test"), f"Unexpected database: {current_db}"

            # DDL & DML test
            conn.execute(text("CREATE TABLE IF NOT EXISTS _test_probe (id SERIAL PRIMARY KEY, val TEXT);"))
            conn.execute(text("INSERT INTO _test_probe (val) VALUES ('live_probe_ok');"))
            conn.commit()

            val = conn.execute(text("SELECT val FROM _test_probe WHERE val = 'live_probe_ok' LIMIT 1;")).scalar()
            assert val == "live_probe_ok"

            conn.execute(text("DROP TABLE _test_probe;"))
            conn.commit()
    finally:
        engine.dispose()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_redis_live_connection_and_caching():
    """
    Verifies that Redis connects to a live Redis 7 instance with authentication,
    and performs read/write operations without memory fallback.
    """
    client = aioredis.from_url(
        TEST_REDIS_URL,
        decode_responses=True,
        socket_timeout=3.0,
    )
    try:
        # Ping
        pong = await client.ping()
        assert pong is True, f"Redis ping failed: {pong}"

        # Server info inspection
        info = await client.info("server")
        assert "redis_version" in info, "Missing redis_version in INFO output"
        assert info["redis_version"].startswith("7."), f"Expected Redis 7.x, got {info['redis_version']}"

        # Key operations with TTL
        test_key = "orchestra:test:probe"
        await client.set(test_key, "active_probe", ex=30)
        retrieved = await client.get(test_key)
        assert retrieved == "active_probe"

        ttl = await client.ttl(test_key)
        assert 0 < ttl <= 30

        await client.delete(test_key)
        deleted = await client.get(test_key)
        assert deleted is None
    finally:
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_qdrant_live_connection_and_collection():
    """
    Verifies that Qdrant connects to an external Qdrant server over HTTP,
    proves the storage is external and not :memory:, and manages collections.
    """
    client = AsyncQdrantClient(url=TEST_QDRANT_URL, timeout=5.0)
    test_collection = "test_probe_collection"
    try:
        # Ensure external HTTP connectivity
        collections_resp = await client.get_collections()
        assert hasattr(collections_resp, "collections")

        # Cleanup in case previous run left it
        existing = [c.name for c in collections_resp.collections]
        if test_collection in existing:
            await client.delete_collection(test_collection)

        # Create collection
        await client.create_collection(
            collection_name=test_collection,
            vectors_config=models.VectorParams(
                size=384,
                distance=models.Distance.COSINE,
            ),
        )

        # Verify collection exists
        info = await client.get_collection(test_collection)
        assert info.status == models.CollectionStatus.GREEN
        assert info.config.params.vectors.size == 384

        # Delete collection
        deleted = await client.delete_collection(test_collection)
        assert deleted is True
    finally:
        await client.close()

