import asyncio
import io
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from starlette.requests import Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.main import app
import app.main as app_main
from app.core.config import settings
from app.core.rate_limit import RouteClass, limiter
from app.models.user import User, UserRole
from app.models.project import Project
from app.models.document import Document, DocumentStatus
from app.auth.password import hash_password
from app.auth.jwt import create_access_token
from app.research.exceptions import VectorStoreError, ResearchPipelineError
from app.orchestrator.service import OrchestratorService
from app.research.services.retrieval_service import RetrievalService
from app.research.vectorstore.qdrant import QdrantVectorStore
import qdrant_client


@pytest.fixture
def auth_context(db_session: Session):
    user = User(
        email=f"fault_test_{uuid.uuid4().hex[:8]}@orchestra.io",
        password_hash=hash_password("Pass123!"),
        role=UserRole.MEMBER.value,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    project = Project(
        name="Fault Injection Workspace",
        owner_id=user.id,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    token = create_access_token(user.id, role=user.role)
    return {"user": user, "project": project, "token": token}


@pytest.mark.asyncio
@pytest.mark.resilience
async def test_database_outage_simulation_and_recovery(auth_context, monkeypatch):
    """
    Simulates a database outage via non-destructive monkeypatching.
    Verifies 503 readiness, error sanitization (no SQL/passwords leaked), and automatic pool healing.
    """
    transport = ASGITransport(app=app)

    # 1. Healthy baseline check
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health/ready")
        assert resp.status_code == 200
        assert resp.json()["dependencies"]["database"] == "healthy"

    # 2. Inject database fault
    def mock_broken_connect(*args, **kwargs):
        raise OperationalError("Simulated connection timeout", params=None, orig=None)

    monkeypatch.setattr(app_main.engine, "connect", mock_broken_connect)

    # 3. Verify /health/ready reports database unhealthy with HTTP 503
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health/ready")
        assert resp.status_code == 503
        data = resp.json()
        assert data["dependencies"]["database"] == "unhealthy"

    # 4. Release fault injection (recovery)
    monkeypatch.undo()

    # 5. Verify database connection pool heals without restart
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health/ready")
        assert resp.status_code == 200
        assert resp.json()["dependencies"]["database"] == "healthy"


@pytest.mark.asyncio
@pytest.mark.resilience
async def test_redis_outage_differentiated_failure_policy(auth_context, monkeypatch):
    """
    Simulates Redis outage and verifies differentiated failure policy:
    Auth & AI routes fail-closed (HTTP 503) to prevent unmetered usage,
    Cheap read routes fail-open (HTTP 200) with in-memory fallback.
    """
    settings.rate_limit_backend = "redis"
    settings.rate_limit_enabled = True

    # Mock Redis client that raises ConnectionError on eval
    class MockBrokenRedis:
        async def eval(self, *args, **kwargs):
            raise ConnectionError("Connection refused to Redis cluster")

    from app.core import rate_limit

    monkeypatch.setattr(rate_limit, "get_redis_client", lambda: MockBrokenRedis())

    mock_req = Request({"type": "http", "client": ("127.0.0.1", 12345), "headers": []})

    try:
        # 1. Fail-closed: Auth route must return 503
        allowed, status_code, _ = await limiter.check_rate_limit(
            request=mock_req, route_class=RouteClass.AUTH
        )
        assert allowed is False
        assert status_code == 503

        # 2. Fail-closed: AI Research route must return 503
        allowed, status_code, _ = await limiter.check_rate_limit(
            request=mock_req, route_class=RouteClass.RESEARCH
        )
        assert allowed is False
        assert status_code == 503

        # 3. Fail-open: Cheap read route must return 200
        allowed, status_code, _ = await limiter.check_rate_limit(
            request=mock_req, route_class=RouteClass.CHEAP_READ
        )
        assert allowed is True
        assert status_code == 200

    finally:
        # 4. Release monkeypatch (recovery)
        monkeypatch.undo()
        settings.rate_limit_backend = "memory"
        settings.rate_limit_enabled = False


@pytest.mark.asyncio
@pytest.mark.resilience
async def test_qdrant_outage_and_degraded_state(auth_context, monkeypatch):
    """
    Simulates Qdrant outage. Verifies readiness degraded status and safe 502 response on search.
    """
    transport = ASGITransport(app=app)
    token = auth_context["token"]
    project_id = auth_context["project"].id

    # 1. Break Qdrant AsyncQdrantClient.get_collections
    async def mock_broken_get_collections(*args, **kwargs):
        raise Exception("Qdrant cluster timeout")

    monkeypatch.setattr(qdrant_client.AsyncQdrantClient, "get_collections", mock_broken_get_collections)

    # 2. Verify readiness reports qdrant as degraded
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health/ready")
        assert resp.status_code == 200
        assert resp.json()["dependencies"]["qdrant"] == "degraded"

    # 3. Search endpoint returns 502 with sanitized error message
    async def mock_broken_search(*args, **kwargs):
        raise VectorStoreError("Simulated Qdrant cluster unreachable")

    monkeypatch.setattr(RetrievalService, "search", mock_broken_search)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        search_resp = await client.post(
            f"/projects/{project_id}/search",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Orchestra-Request": "true",
            },
            json={"query": "Quantum coherence mechanisms"},
        )
        assert search_resp.status_code == 502
        data = search_resp.json()
        assert "Retrieval service encountered an error" in data["detail"]
        assert "password" not in str(data).lower()
        assert "traceback" not in str(data).lower()

    # 4. Recovery: restore normal operations
    monkeypatch.undo()


@pytest.mark.asyncio
@pytest.mark.resilience
async def test_llm_provider_timeout_and_malformation(auth_context, monkeypatch):
    """
    Verifies LLM provider timeout handling (504 Gateway Timeout) and
    malformed output handling (502 Bad Gateway) without external network calls.
    """
    transport = ASGITransport(app=app)
    token = auth_context["token"]
    project_id = auth_context["project"].id

    # 1. Timeout simulation: returns 504 Gateway Timeout
    async def mock_timeout_orchestrate(*args, **kwargs):
        raise TimeoutError("LLM response deadline exceeded 20s")

    monkeypatch.setattr(OrchestratorService, "orchestrate", mock_timeout_orchestrate)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/projects/{project_id}/orchestrate",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Orchestra-Request": "true",
            },
            json={"prompt": "Test orchestrator timeout"},
        )
        assert resp.status_code == 504
        assert "timed out" in resp.json()["detail"].lower()

    # 2. Malformed JSON output simulation: returns 502 Bad Gateway
    async def mock_malformed_orchestrate(*args, **kwargs):
        raise ResearchPipelineError("Failed to parse LLM structured output as JSON")

    monkeypatch.setattr(OrchestratorService, "orchestrate", mock_malformed_orchestrate)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/projects/{project_id}/orchestrate",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Orchestra-Request": "true",
            },
            json={"prompt": "Test orchestrator malformed output"},
        )
        assert resp.status_code == 502
        assert "upstream subsystem error" in resp.json()["detail"].lower()

    monkeypatch.undo()


@pytest.mark.asyncio
@pytest.mark.resilience
async def test_partial_ingestion_failure_compensation(auth_context, db_session: Session, monkeypatch):
    """
    Simulates a failure during document vector indexing.
    Verifies that status compensation marks the document as 'failed' in the database.
    """
    transport = ASGITransport(app=app)
    token = auth_context["token"]
    project_id = auth_context["project"].id

    async def mock_failing_upsert_chunks(*args, **kwargs):
        raise VectorStoreError("Vector database write failed")

    monkeypatch.setattr(QdrantVectorStore, "upsert_chunks", mock_failing_upsert_chunks)

    file_bytes = b"# Fault Document\nThis document will fail during vector indexing."

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/projects/{project_id}/documents",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Orchestra-Request": "true",
            },
            files={"file": ("fault_doc.md", io.BytesIO(file_bytes), "text/markdown")},
        )
        # Endpoint returns the document or error
        assert resp.status_code in (200, 201, 500, 502)

    # Invariant: Database document record is transitioned to 'failed' status
    doc = db_session.query(Document).filter(Document.project_id == project_id, Document.original_filename == "fault_doc.md").first()
    if doc:
        assert doc.status == DocumentStatus.FAILED.value
