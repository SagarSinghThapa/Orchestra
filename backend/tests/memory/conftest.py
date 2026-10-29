import os
import sqlite3
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.database.base import Base
from app.database.connection import get_db
from app.auth.dependencies import get_current_user
from app.main import app
from app.models.user import User
from app.models.project import Project
from app.models.session import Session as DBSession
from app.models.message import Message
from app.models.session_summary import SessionSummary


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")


@pytest.fixture(autouse=True)
def test_environment(monkeypatch):
    """Enforces test environment mode during memory test runs."""
    monkeypatch.setattr(settings, "environment", "test")
    monkeypatch.setattr(settings, "embedding_provider", "test")


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enforces foreign key constraint checks and cascades when testing with SQLite."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@pytest.fixture(scope="session")
def test_engine():
    """Session-scoped engine fixture."""
    if TEST_DATABASE_URL.startswith("sqlite"):
        engine = create_engine(
            TEST_DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)

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


@pytest.fixture(scope="function")
def db_session(test_engine: Engine) -> Generator[Session, None, None]:
    """Function-scoped isolated session with clean database state."""
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


@pytest.fixture(scope="function")
def test_user(db_session: Session) -> User:
    """Fixture providing a primary test user."""
    user = User(
        email="memory_user@orchestra.ai",
        password_hash="hashed_pw_memory_123",
        role="member",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def test_project(db_session: Session, test_user: User) -> Project:
    """Fixture providing a primary test project."""
    project = Project(
        name="Memory Test Project",
        description="Project for validating memory intelligence",
        owner_id=test_user.id,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


@pytest.fixture(scope="function")
def test_session(db_session: Session, test_project: Project) -> DBSession:
    """Fixture providing a test conversation session."""
    session = DBSession(
        project_id=test_project.id,
        type="orchestrator",
        title="Architecture Discussion",
        query="Discussing memory subsystem",
        status="active",
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


@pytest.fixture(scope="function")
def foreign_user(db_session: Session) -> User:
    """Secondary user to validate IDOR boundary protections."""
    user = User(
        email="foreign_user@orchestra.ai",
        password_hash="hashed_pw_foreign_456",
        role="member",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def foreign_project(db_session: Session, foreign_user: User) -> Project:
    """Project owned by foreign_user."""
    project = Project(
        name="Foreign Project",
        description="Foreign workspace",
        owner_id=foreign_user.id,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient overriding get_db and cleaning dependency overrides."""
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture(scope="function")
def set_auth():
    """Helper to dynamically switch authenticated user for API requests."""
    def _set(user: User):
        app.dependency_overrides[get_current_user] = lambda: user
    return _set

