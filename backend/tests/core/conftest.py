"""
Portable Database & API Test Harness for Orchestra Platform Core.

TESTING BOUNDARY NOTICE:
-----------------------
These in-memory SQLite fixtures provide fast, deterministic ORM mapping,
relationship validation, and API contract/IDOR verification.
They do NOT prove PostgreSQL-specific dialect compatibility (e.g. JSONB operators,
Postgres-specific indexing, or complex concurrency locks), which will be validated
in dedicated containerized integration environments (Phase 14).
"""

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
from app.auth.dependencies import get_current_user
from app.main import app
from app.models.user import User
from app.models.project import Project
from app.models.session import Session as DBSession
from app.models.message import Message


# Optional TEST_DATABASE_URL hook for future CI / containerized testing
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")


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
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_session(test_engine) -> Generator[Session, None, None]:
    """
    Function-scoped isolated session with clean database state.
    Explicitly deletes all table data after each test to ensure 100% deterministic isolation.
    """
    connection = test_engine.connect()
    session_factory = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = session_factory()

    try:
        yield session
    finally:
        session.close()
        # Clean all tables in reverse dependency order
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())
        connection.commit()
        connection.close()


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Creates a seeded primary test user."""
    user = User(
        email="developer@orchestra.ai",
        password_hash="$2b$12$e80Mbp1K42bYQZzHkmfWyeiE5R.2oZ27sEw7bH46d0aT7uKGy6s2O",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def second_user(db_session: Session) -> User:
    """Creates a seeded secondary test user to verify cross-user isolation / IDOR."""
    user = User(
        email="analyst@orchestra.ai",
        password_hash="$2b$12$e80Mbp1K42bYQZzHkmfWyeiE5R.2oZ27sEw7bH46d0aT7uKGy6s2O",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_project(db_session: Session, test_user: User) -> Project:
    """Creates a seeded project owned by the primary test user."""
    project = Project(
        name="Orchestra Core",
        description="Autonomous Platform Engineering Workspace",
        owner_id=test_user.id,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


@pytest.fixture
def test_session_obj(db_session: Session, test_project: Project) -> DBSession:
    """Creates a seeded interactive session under test_project."""
    session = DBSession(
        project_id=test_project.id,
        type="coding",
        title="AST Parser Refactor",
        query="Refactor coding agent AST validation",
        status="pending",
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with get_db overridden to use isolated db_session."""
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def set_auth():
    """Helper to dynamically switch authenticated user for API requests."""
    def _set(user: User):
        app.dependency_overrides[get_current_user] = lambda: user
    yield _set
    app.dependency_overrides.pop(get_current_user, None)
