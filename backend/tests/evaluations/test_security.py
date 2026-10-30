import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.evaluations.schemas import EvaluationRunCreate, ExecutionMode
from app.evaluations.service import EvaluationService
from app.models import EvaluationRun, Project, User, UserRole


@pytest.fixture
def security_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    admin_user = User(id=1, email="admin@orchestra.ai", password_hash="hash", role=UserRole.ADMIN.value)
    user_a = User(id=2, email="user_a@orchestra.ai", password_hash="hash", role=UserRole.MEMBER.value)
    user_b = User(id=3, email="user_b@orchestra.ai", password_hash="hash", role=UserRole.MEMBER.value)
    viewer_user = User(id=4, email="viewer@orchestra.ai", password_hash="hash", role=UserRole.VIEWER.value)
    db.add_all([admin_user, user_a, user_b, viewer_user])
    db.commit()

    proj_a = Project(id=101, name="Project A", owner_id=user_a.id)
    proj_b = Project(id=102, name="Project B", owner_id=user_b.id)
    db.add_all([proj_a, proj_b])
    db.commit()

    yield db
    db.close()


@pytest.mark.asyncio
async def test_foreign_project_ownership_before_cost_404(security_db):
    """Verify that User B attempting to run evaluation on User A's project is aborted with 404 immediately."""
    user_b = security_db.query(User).filter(User.id == 3).first()
    service = EvaluationService(security_db)

    payload = EvaluationRunCreate(
        suite_id="project_invariants",
        project_id=101,  # Belongs to User A!
        execution_mode=ExecutionMode.REGRESSION,
        max_cases=5,
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.execute_run(payload, user=user_b)

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()

    # Zero runs persisted
    assert security_db.query(EvaluationRun).count() == 0


@pytest.mark.asyncio
async def test_member_system_benchmark_forbidden_403(security_db):
    """Verify that a non-admin Member cannot execute system benchmark suites."""
    user_a = security_db.query(User).filter(User.id == 2).first()
    service = EvaluationService(security_db)

    payload = EvaluationRunCreate(
        suite_id="coding_ast",
        project_id=None,  # System benchmark
        execution_mode=ExecutionMode.REGRESSION,
        max_cases=5,
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.execute_run(payload, user=user_a)

    assert exc_info.value.status_code == 403
    assert "admin privileges" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_idor_foreign_run_lookup_isolation(security_db):
    """Verify that User B cannot look up an evaluation run belonging to User A's project."""
    user_a = security_db.query(User).filter(User.id == 2).first()
    user_b = security_db.query(User).filter(User.id == 3).first()
    service = EvaluationService(security_db)

    # User A executes run on Project A
    payload = EvaluationRunCreate(
        suite_id="project_invariants",
        project_id=101,
        execution_mode=ExecutionMode.REGRESSION,
        max_cases=1,
    )
    run_a = await service.execute_run(payload, user=user_a)

    # User A can fetch it
    res_a = service.get_run_scoped(run_a.id, user=user_a)
    assert res_a is not None
    assert res_a.id == run_a.id

    # User B looking up run_a must return None (IDOR protected)
    res_b = service.get_run_scoped(run_a.id, user=user_b)
    assert res_b is None


@pytest.mark.asyncio
async def test_run_list_tenancy_scoping(security_db):
    """Verify list_runs_scoped only returns owned project runs and system runs."""
    admin = security_db.query(User).filter(User.id == 1).first()
    user_a = security_db.query(User).filter(User.id == 2).first()
    user_b = security_db.query(User).filter(User.id == 3).first()
    service = EvaluationService(security_db)

    # Create run for Project A
    await service.execute_run(
        EvaluationRunCreate(suite_id="project_invariants", project_id=101, max_cases=1),
        user=user_a,
    )
    # Create run for Project B
    await service.execute_run(
        EvaluationRunCreate(suite_id="project_invariants", project_id=102, max_cases=1),
        user=user_b,
    )
    # Create system run
    await service.execute_run(
        EvaluationRunCreate(suite_id="coding_ast", project_id=None, max_cases=1),
        user=admin,
    )

    # User A list: sees Project A run + system run = 2 runs (never Project B)
    runs_a = service.list_runs_scoped(user=user_a)
    run_project_ids = [r.project_id for r in runs_a]
    assert 101 in run_project_ids
    assert 102 not in run_project_ids

    # Admin list: sees all 3 runs
    runs_admin = service.list_runs_scoped(user=admin)
    assert len(runs_admin) == 3
