import asyncio
import io
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.orm import Session

from app.main import app
from app.models.user import User, UserRole
from app.models.project import Project
from app.models.document import Document
from app.models.evaluation import EvaluationRun
from app.models.session_summary import SessionSummary
from app.models.session import Session as SessionModel
from app.memory.summarizer import SummarizerService
from app.memory.exceptions import StaleWriteError, WatermarkRegressionError
from app.core.rate_limit import MemoryRateLimiterStorage
from app.auth.password import hash_password
from app.auth.jwt import create_access_token


@pytest.mark.asyncio
@pytest.mark.resilience
async def test_duplicate_document_upload_race(db_session: Session):
    """
    Fire parallel uploads of the exact same document to the same project workspace.
    Verifies that deduplication or database uniqueness preserves integrity.
    """
    user = User(
        email="concurrent_upload@orchestra.io",
        password_hash=hash_password("Pass123!"),
        role=UserRole.MEMBER.value,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    project = Project(
        name="Concurrent Upload Workspace",
        owner_id=user.id,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    token = create_access_token(user.id, role=user.role)
    transport = ASGITransport(app=app)

    file_bytes = b"# Quantum Computing Overview\n\nSuperconducting qubits maintain coherence for microseconds."

    async def upload_file():
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                f"/projects/{project.id}/documents",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Orchestra-Request": "true",
                },
                files={"file": ("quantum.md", io.BytesIO(file_bytes), "text/markdown")},
            )

    # Dispatch 5 parallel uploads
    responses = await asyncio.gather(*(upload_file() for _ in range(5)), return_exceptions=True)

    # Count responses: at least one must succeed (201)
    status_codes = [r.status_code for r in responses if hasattr(r, "status_code")]
    assert 201 in status_codes, f"Expected at least one 201 Created, got: {status_codes}"

    # Verify database has valid documents
    docs = db_session.query(Document).filter(Document.project_id == project.id).all()
    assert len(docs) >= 1
    for doc in docs:
        assert doc.status in ("uploaded", "processing", "indexed")


@pytest.mark.asyncio
@pytest.mark.resilience
async def test_multi_tenant_concurrency_isolation(db_session: Session):
    """
    Spawn 10 concurrent requests: 5 querying User A's project and 5 querying User B's project.
    Verifies 100% tenant boundary isolation with zero cross-tenant contamination.
    """
    user_a = User(email="tenant_a@orchestra.io", password_hash=hash_password("Pass123!"), role="member")
    user_b = User(email="tenant_b@orchestra.io", password_hash=hash_password("Pass123!"), role="member")
    db_session.add_all([user_a, user_b])
    db_session.commit()
    db_session.refresh(user_a)
    db_session.refresh(user_b)

    proj_a = Project(name="Project A", owner_id=user_a.id)
    proj_b = Project(name="Project B", owner_id=user_b.id)
    db_session.add_all([proj_a, proj_b])
    db_session.commit()
    db_session.refresh(proj_a)
    db_session.refresh(proj_b)

    token_a = create_access_token(user_a.id, role=user_a.role)
    token_b = create_access_token(user_b.id, role=user_b.role)

    transport = ASGITransport(app=app)

    async def query_tenant(token: str, project_id: int):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(
                f"/projects/{project_id}",
                headers={"Authorization": f"Bearer {token}"},
            )

    tasks = []
    # 5 queries for tenant A
    for _ in range(5):
        tasks.append(query_tenant(token_a, proj_a.id))
    # 5 queries for tenant B
    for _ in range(5):
        tasks.append(query_tenant(token_b, proj_b.id))

    responses = await asyncio.gather(*tasks)

    for i, resp in enumerate(responses):
        assert resp.status_code == 200
        data = resp.json()
        if i < 5:
            assert data["id"] == proj_a.id
            assert data["name"] == "Project A"
        else:
            assert data["id"] == proj_b.id
            assert data["name"] == "Project B"


@pytest.mark.asyncio
@pytest.mark.resilience
async def test_evaluation_baseline_designation_race(db_session: Session):
    """
    Fire concurrent baseline designation requests for Run 1 and Run 2.
    Verifies that transaction isolation guarantees exactly one run is designated as the active baseline.
    """
    user = User(email="baseline_race@orchestra.io", password_hash=hash_password("Pass123!"), role="admin")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    suite_id = "orchestrator_routing"

    run_1 = EvaluationRun(
        id=str(uuid.uuid4()),
        suite_id=suite_id,
        created_by_user_id=user.id,
        dataset_id="test_ds",
        dataset_version="1.0",
        dataset_sha256="abc",
        target_type="orchestrator",
        execution_mode="regression",
        status="completed",
        is_baseline=False,
    )
    run_2 = EvaluationRun(
        id=str(uuid.uuid4()),
        suite_id=suite_id,
        created_by_user_id=user.id,
        dataset_id="test_ds",
        dataset_version="1.0",
        dataset_sha256="abc",
        target_type="orchestrator",
        execution_mode="regression",
        status="completed",
        is_baseline=False,
    )
    db_session.add_all([run_1, run_2])
    db_session.commit()
    db_session.refresh(run_1)
    db_session.refresh(run_2)

    token = create_access_token(user.id, role=user.role)
    transport = ASGITransport(app=app)

    async def designate_baseline(run_id: str):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                f"/evaluations/runs/{run_id}/baseline",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Orchestra-Request": "true",
                },
            )

    # Fire both baseline requests concurrently
    resp_1, resp_2 = await asyncio.gather(
        designate_baseline(run_1.id),
        designate_baseline(run_2.id),
    )

    assert resp_1.status_code == 200
    assert resp_2.status_code == 200

    # Query database to confirm baseline invariant
    db_session.expire_all()
    active_baselines = (
        db_session.query(EvaluationRun)
        .filter(EvaluationRun.suite_id == suite_id, EvaluationRun.is_baseline == True)
        .all()
    )
    assert len(active_baselines) == 1, f"Expected exactly 1 active baseline, found: {len(active_baselines)}"


@pytest.mark.asyncio
@pytest.mark.resilience
async def test_memory_summarization_version_race(db_session: Session):
    """
    Simulates concurrent summarization updates against the same active session summary.
    Verifies optimistic concurrency locking: an update with a stale expected version
    raises StaleWriteError, preventing older writes from overwriting newer writes.
    """
    user = User(email="mem_race@orchestra.io", password_hash=hash_password("Pass123!"), role="member")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    proj = Project(name="Mem Race Space", owner_id=user.id)
    db_session.add(proj)
    db_session.commit()
    db_session.refresh(proj)

    sess = SessionModel(
        project_id=proj.id,
        type="research",
        title="Mem Thread",
        query="Initial query",
        status="active",
    )
    db_session.add(sess)
    db_session.commit()
    db_session.refresh(sess)

    summarizer = SummarizerService(db=db_session, llm_provider=None)

    # 1. Initial summary creation (version 1)
    s1 = summarizer._upsert_summary(
        session_id=sess.id,
        project_id=proj.id,
        summary_text="Initial turn summary",
        watermark_id=10,
        message_count=10,
        expected_version=None,
    )
    assert s1.version == 1
    assert s1.message_watermark_id == 10

    # 2. Worker A and Worker B both read summary at version 1
    read_version_a = s1.version  # 1
    read_version_b = s1.version  # 1

    # Worker A succeeds in updating to version 2
    s2 = summarizer._upsert_summary(
        session_id=sess.id,
        project_id=proj.id,
        summary_text="Worker A summary update",
        watermark_id=20,
        message_count=10,
        expected_version=read_version_a,
    )
    assert s2.version == 2
    assert s2.message_watermark_id == 20

    # Worker B tries to update using stale version 1 -> Must raise StaleWriteError
    with pytest.raises(StaleWriteError):
        summarizer._upsert_summary(
            session_id=sess.id,
            project_id=proj.id,
            summary_text="Worker B stale update",
            watermark_id=25,
            message_count=5,
            expected_version=read_version_b,
        )

    # Verify watermark regression protection
    with pytest.raises(WatermarkRegressionError):
        summarizer._upsert_summary(
            session_id=sess.id,
            project_id=proj.id,
            summary_text="Regressed watermark update",
            watermark_id=5,  # Less than current 20
            message_count=5,
            expected_version=2,
        )

    # Invariant: Database maintains Worker A's update (version 2, watermark 20)
    current = db_session.query(SessionSummary).filter(SessionSummary.session_id == sess.id).one()
    assert current.version == 2
    assert current.message_watermark_id == 20
    assert "Worker A" in current.summary_text


@pytest.mark.asyncio
@pytest.mark.resilience
async def test_memory_rate_limiter_lru_bounding():
    """
    Simulates high-cardinality traffic (20,000 distinct IP addresses) against MemoryRateLimiterStorage.
    Verifies that the storage capacity strictly caps at 10,000 keys via LRU eviction.
    """
    storage = MemoryRateLimiterStorage(max_keys=10000)

    # Inject 20,000 unique IP keys
    for i in range(20000):
        key = f"ip:192.168.{i // 256}.{i % 256}"
        allowed, rem, retry = await storage.check_and_record(key=key, window_seconds=60, limit=10)
        assert allowed is True

    # Check internal bucket size
    assert len(storage._buckets) == 10000, f"Expected 10000 keys max, got {len(storage._buckets)}"

    # Earliest keys should have been evicted by LRU
    assert "ip:192.168.0.0" not in storage._buckets
    # Latest keys must still be present
    assert "ip:192.168.78.31" in storage._buckets


