import os
import sqlite3
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
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
from app.auth.dependencies import get_current_user

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")


@pytest.fixture(autouse=True)
def test_environment(monkeypatch):
    """Enforces test environment mode during orchestrator test runs."""
    monkeypatch.setattr(settings, "environment", "test")
    monkeypatch.setattr(settings, "embedding_provider", "test")


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enforces foreign key constraint checks in SQLite."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@pytest.fixture(scope="session")
def test_engine():
    """Session-scoped engine fixture with checkpoints tables."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS checkpoints (
                thread_id VARCHAR(255) NOT NULL,
                checkpoint_ns VARCHAR(255) NOT NULL DEFAULT '',
                checkpoint_id VARCHAR(255) NOT NULL,
                parent_checkpoint_id VARCHAR(255),
                type VARCHAR(100),
                checkpoint TEXT NOT NULL,
                metadata TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
            );
            """
            )
        )
        conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS checkpoint_writes (
                thread_id VARCHAR(255) NOT NULL,
                checkpoint_ns VARCHAR(255) NOT NULL DEFAULT '',
                checkpoint_id VARCHAR(255) NOT NULL,
                task_id VARCHAR(255) NOT NULL,
                idx INTEGER NOT NULL,
                channel VARCHAR(255) NOT NULL,
                type VARCHAR(100),
                value TEXT NOT NULL,
                PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
            );
            """
            )
        )
    yield engine
    Base.metadata.drop_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS checkpoint_writes;"))
        conn.execute(text("DROP TABLE IF EXISTS checkpoints;"))
    engine.dispose()


@pytest.fixture
def db_session(test_engine) -> Generator[Session, None, None]:
    """Isolated database session with reverse-dependency cleanup."""
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
        name="Orchestrator Project Alpha",
        description="Workspace for Alpha",
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
        name="Orchestrator Project Beta",
        description="Workspace for Beta",
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
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient overriding get_db."""
    from app.api.orchestrator import get_orchestrator_service

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_orchestrator_service, None)


@pytest.fixture
def set_auth():
    """Helper to dynamically switch authenticated user for API requests."""
    def _set(user: User):
        app.dependency_overrides[get_current_user] = lambda: user

    yield _set
    app.dependency_overrides.pop(get_current_user, None)
