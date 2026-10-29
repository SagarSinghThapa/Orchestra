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
from app.models.session_summary import SessionSummary


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


@pytest.fixture(scope="function")
def db_session(test_engine: Engine) -> Generator[Session, None, None]:
    """Function-scoped database session wrapped in a transaction rollback."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, expire_on_commit=False)
    session = session_factory()

    yield session

    session.close()
    transaction.rollback()
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

