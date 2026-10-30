import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import get_current_user
from app.auth.password import hash_password
from app.database.base import Base
from app.database.connection import get_db
from app.main import app
from app.models.evaluation import EvaluationRun
from app.models.project import Project
from app.models.user import User, UserRole


@pytest.fixture(scope="module")
def api_test_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def api_db(api_test_engine):
    connection = api_test_engine.connect()
    session_factory = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())
        connection.commit()
        connection.close()


@pytest.fixture
def admin_user(api_db: Session) -> User:
    user = User(
        email="admin_api@orchestra.ai",
        password_hash=hash_password("AdminPass123!"),
        role=UserRole.ADMIN.value,
    )
    api_db.add(user)
    api_db.commit()
    api_db.refresh(user)
    return user


@pytest.fixture
def member_user_a(api_db: Session) -> User:
    user = User(
        email="member_a_api@orchestra.ai",
        password_hash=hash_password("MemberPass123!"),
        role=UserRole.MEMBER.value,
    )
    api_db.add(user)
    api_db.commit()
    api_db.refresh(user)
    return user


@pytest.fixture
def member_user_b(api_db: Session) -> User:
    user = User(
        email="member_b_api@orchestra.ai",
        password_hash=hash_password("MemberPass456!"),
        role=UserRole.MEMBER.value,
    )
    api_db.add(user)
    api_db.commit()
    api_db.refresh(user)
    return user


@pytest.fixture
def viewer_user(api_db: Session) -> User:
    user = User(
        email="viewer_api@orchestra.ai",
        password_hash=hash_password("ViewerPass123!"),
        role=UserRole.VIEWER.value,
    )
    api_db.add(user)
    api_db.commit()
    api_db.refresh(user)
    return user


@pytest.fixture
def project_a(api_db: Session, member_user_a: User) -> Project:
    proj = Project(
        name="Project A API",
        description="Project A for API testing",
        owner_id=member_user_a.id,
    )
    api_db.add(proj)
    api_db.commit()
    api_db.refresh(proj)
    return proj


@pytest.fixture
def client(api_db: Session):
    def _override_get_db():
        yield api_db

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def set_auth():
    def _set(user: User):
        app.dependency_overrides[get_current_user] = lambda: user

    yield _set
    app.dependency_overrides.pop(get_current_user, None)


def test_unauthenticated_request_rejected(client: TestClient):
    resp = client.get("/evaluations/benchmarks")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_benchmarks_success(client: TestClient, set_auth, member_user_a: User):
    set_auth(member_user_a)
    resp = client.get("/evaluations/benchmarks")
    assert resp.status_code == status.HTTP_200_OK
    suites = resp.json()
    assert isinstance(suites, list)
    assert len(suites) >= 5
    suite_ids = [s["suite_id"] for s in suites]
    assert "rag_faithfulness" in suite_ids
    assert "retrieval_ranking" in suite_ids
    assert "coding_ast" in suite_ids
    assert "orchestrator_routing" in suite_ids
    assert "full_system" in suite_ids


def test_viewer_run_forbidden(client: TestClient, set_auth, viewer_user: User):
    set_auth(viewer_user)
    payload = {
        "suite_id": "orchestrator_routing",
        "project_id": None,
        "execution_mode": "regression",
        "max_cases": 2,
    }
    resp = client.post("/evaluations/runs", json=payload)
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_member_system_suite_forbidden(client: TestClient, set_auth, member_user_a: User):
    set_auth(member_user_a)
    payload = {
        "suite_id": "orchestrator_routing",
        "project_id": None,
        "execution_mode": "regression",
        "max_cases": 2,
    }
    resp = client.post("/evaluations/runs", json=payload)
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_member_foreign_project_404(
    client: TestClient,
    set_auth,
    member_user_b: User,
    project_a: Project,
):
    set_auth(member_user_b)
    payload = {
        "suite_id": "project_invariants",
        "project_id": project_a.id,
        "execution_mode": "regression",
        "max_cases": 2,
    }
    resp = client.post("/evaluations/runs", json=payload)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_admin_execute_run_and_lifecycle(
    client: TestClient,
    set_auth,
    admin_user: User,
):
    set_auth(admin_user)
    # 1. Execute run
    payload = {
        "suite_id": "orchestrator_routing",
        "project_id": None,
        "execution_mode": "regression",
        "max_cases": 3,
    }
    create_resp = client.post("/evaluations/runs", json=payload)
    assert create_resp.status_code == status.HTTP_201_CREATED
    run_data = create_resp.json()
    run_id = run_data["id"]
    assert run_data["suite_id"] == "orchestrator_routing"
    assert run_data["total_cases"] == 3
    assert len(run_data["case_results"]) == 3
    assert run_data["status"] == "completed"

    # 2. List runs
    list_resp = client.get("/evaluations/runs")
    assert list_resp.status_code == status.HTTP_200_OK
    runs = list_resp.json()
    assert any(r["id"] == run_id for r in runs)

    # 3. Get single run
    get_resp = client.get(f"/evaluations/runs/{run_id}")
    assert get_resp.status_code == status.HTTP_200_OK
    assert get_resp.json()["id"] == run_id

    # 4. Promote to baseline
    base_resp = client.post(f"/evaluations/runs/{run_id}/baseline")
    assert base_resp.status_code == status.HTTP_200_OK
    assert base_resp.json()["is_baseline"] is True

    # 5. Delete run
    del_resp = client.delete(f"/evaluations/runs/{run_id}")
    assert del_resp.status_code == status.HTTP_204_NO_CONTENT

    # 6. Verify deleted
    get_after_del = client.get(f"/evaluations/runs/{run_id}")
    assert get_after_del.status_code == status.HTTP_404_NOT_FOUND
