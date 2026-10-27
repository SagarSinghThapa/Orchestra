import os
import sqlite3
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.connection import get_db
from app.core.config import settings
from app.main import app
from app.models.user import User, UserRole
from app.models.project import Project
from app.auth.password import hash_password
from app.developer.workspace import WorkspaceResolver
from app.developer.services.developer_service import DeveloperService
from app.research.llm.mock import DeterministicTestLLMProvider

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")


@pytest.fixture(autouse=True)
def test_environment(monkeypatch):
    """Enforces test environment mode during developer test runs."""
    monkeypatch.setattr(settings, "environment", "test")


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enforces foreign key constraint checks in SQLite."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@pytest.fixture(scope="session")
def test_engine():
    """Session-scoped engine fixture for developer tests."""
    if TEST_DATABASE_URL.startswith("sqlite"):
        engine = create_engine(
            TEST_DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_session(test_engine) -> Generator[Session, None, None]:
    """Isolated database session with reverse-dependency table cleanup."""
    connection = test_engine.connect()
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
def test_user(db_session: Session) -> User:
    """Primary test user (Member role)."""
    user = User(
        email="developer_a@orchestra.ai",
        password_hash=hash_password("Password123!"),
        role=UserRole.MEMBER.value,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_project(db_session: Session, test_user: User) -> Project:
    """Primary project owned by test_user."""
    project = Project(
        name="Developer Project Alpha",
        description="Dev workspace for Alpha",
        owner_id=test_user.id,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


@pytest.fixture
def test_user_b(db_session: Session) -> User:
    """Secondary test user for tenant isolation / IDOR tests."""
    user = User(
        email="developer_b@orchestra.ai",
        password_hash=hash_password("Password456!"),
        role=UserRole.MEMBER.value,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_project_b(db_session: Session, test_user_b: User) -> Project:
    """Secondary project owned by test_user_b."""
    project = Project(
        name="Developer Project Beta",
        description="Dev workspace for Beta",
        owner_id=test_user_b.id,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


@pytest.fixture
def test_viewer_user(db_session: Session) -> User:
    """Viewer user for RBAC tests."""
    user = User(
        email="viewer@orchestra.ai",
        password_hash=hash_password("PasswordViewer123!"),
        role=UserRole.VIEWER.value,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_viewer_project(db_session: Session, test_viewer_user: User) -> Project:
    """Project owned by viewer user."""
    project = Project(
        name="Viewer Project",
        description="Workspace for viewer",
        owner_id=test_viewer_user.id,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


@pytest.fixture
def test_llm_provider():
    """Deterministic offline test LLM provider."""
    return DeterministicTestLLMProvider()


@pytest.fixture
def test_workspace_resolver(tmp_path):
    """Isolated WorkspaceResolver rooted in temporary test directory."""
    ws_dir = tmp_path / "workspaces"
    ws_dir.mkdir(parents=True, exist_ok=True)
    return WorkspaceResolver(base_dir=ws_dir)


@pytest.fixture
def test_developer_service(db_session: Session, test_workspace_resolver, test_llm_provider):
    """Configured DeveloperService for testing."""
    return DeveloperService(
        db=db_session,
        workspace_resolver=test_workspace_resolver,
        llm_provider=test_llm_provider,
        timeout_seconds=45.0,
    )


@pytest.fixture
def client(
    db_session: Session, test_developer_service
) -> Generator[TestClient, None, None]:
    """TestClient overriding get_db and get_developer_service."""
    from app.auth.dependencies import get_current_user
    from app.api.developer import get_developer_service

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_developer_service] = lambda: test_developer_service

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_developer_service, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def set_auth():
    """Helper to dynamically switch authenticated user for API requests."""
    from app.auth.dependencies import get_current_user

    def _set(user: User):
        app.dependency_overrides[get_current_user] = lambda: user

    yield _set
    app.dependency_overrides.pop(get_current_user, None)
