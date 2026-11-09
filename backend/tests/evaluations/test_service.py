import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.evaluations.schemas import EvaluationRunCreate, ExecutionMode
from app.evaluations.service import EvaluationService
from app.models import EvaluationRun, Project, User, UserRole


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    admin_user = User(id=1, email="admin@orchestra.ai", password_hash="hash", role=UserRole.ADMIN.value)
    member_user = User(id=2, email="member@orchestra.ai", password_hash="hash", role=UserRole.MEMBER.value)
    viewer_user = User(id=3, email="viewer@orchestra.ai", password_hash="hash", role=UserRole.VIEWER.value)
    db.add_all([admin_user, member_user, viewer_user])
    db.commit()

    proj1 = Project(id=1, name="Admin Project", owner_id=admin_user.id)
    proj2 = Project(id=2, name="Member Project", owner_id=member_user.id)
    db.add_all([proj1, proj2])
    db.commit()

    yield db
    db.close()


@pytest.mark.asyncio
async def test_service_execute_system_run(test_db):
    """Verify admin can execute a system benchmark suite."""
    admin_user = test_db.query(User).filter(User.role == UserRole.ADMIN.value).first()
    service = EvaluationService(test_db)

    payload = EvaluationRunCreate(
        suite_id="coding_ast",
        project_id=None,
        execution_mode=ExecutionMode.REGRESSION,
        max_cases=5,
    )
    result = await service.execute_run(payload, user=admin_user)

    assert result.status == "completed"
    assert result.suite_id == "coding_ast"
    assert result.total_cases == 5
    assert result.passed_cases == 5
    assert result.failed_cases == 0
    assert result.duration_ms > 0.0
    assert "ast_syntax_validity" in result.summary_metrics


@pytest.mark.asyncio
async def test_service_execute_full_system_suite(test_db):
    """Verify full_system composite suite runs 20 cases across all 4 pillars."""
    admin_user = test_db.query(User).filter(User.role == UserRole.ADMIN.value).first()
    service = EvaluationService(test_db)

    payload = EvaluationRunCreate(
        suite_id="full_system",
        project_id=None,
        execution_mode=ExecutionMode.REGRESSION,
        max_cases=20,
    )
    result = await service.execute_run(payload, user=admin_user)

    assert result.status == "completed"
    assert result.total_cases == 20
    assert result.passed_cases == 20
    assert len(result.case_results) == 20


@pytest.mark.asyncio
async def test_service_execute_project_run(test_db):
    """Verify member can execute project_invariants on their owned project."""
    member_user = test_db.query(User).filter(User.role == UserRole.MEMBER.value).first()
    service = EvaluationService(test_db)

    payload = EvaluationRunCreate(
        suite_id="project_invariants",
        project_id=2,  # Owned by member_user
        execution_mode=ExecutionMode.REGRESSION,
        max_cases=5,
    )
    result = await service.execute_run(payload, user=member_user)

    assert result.project_id == 2
    assert result.status == "completed"
    assert result.total_cases >= 1


@pytest.mark.asyncio
async def test_service_baseline_atomic_replacement(test_db):
    """Verify baseline designation atomically clears previous baseline for the same suite signature."""
    admin_user = test_db.query(User).filter(User.role == UserRole.ADMIN.value).first()
    service = EvaluationService(test_db)

    payload = EvaluationRunCreate(
        suite_id="coding_ast",
        project_id=None,
        execution_mode=ExecutionMode.REGRESSION,
        max_cases=2,
    )
    run1 = await service.execute_run(payload, user=admin_user)
    run2 = await service.execute_run(payload, user=admin_user)

    # Set run1 as baseline
    res1 = service.set_baseline_scoped(run1.id, user=admin_user)
    assert res1.is_baseline is True

    # Set run2 as baseline: run1 must be cleared!
    res2 = service.set_baseline_scoped(run2.id, user=admin_user)
    assert res2.is_baseline is True

    test_db.expire_all()
    db_run1 = test_db.query(EvaluationRun).filter(EvaluationRun.id == run1.id).first()
    assert db_run1.is_baseline is False


@pytest.mark.asyncio
async def test_service_global_timeout_enforcement(test_db):
    """Verify global timeout marks remaining cases as skipped and run as failed."""
    admin_user = test_db.query(User).filter(User.role == UserRole.ADMIN.value).first()
    # Inject a 0.0001s global timeout
    service = EvaluationService(test_db, global_timeout_s=0.0001)

    payload = EvaluationRunCreate(
        suite_id="coding_ast",
        project_id=None,
        execution_mode=ExecutionMode.REGRESSION,
        max_cases=5,
    )
    result = await service.execute_run(payload, user=admin_user)

    assert result.status == "failed"
    assert "Global evaluation deadline exceeded" in (result.error_message or "")
    # Skipped cases exist
    assert any(cr.status == "skipped" for cr in result.case_results)
