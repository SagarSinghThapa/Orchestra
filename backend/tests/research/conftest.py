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

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enforces foreign key constraint checks in SQLite."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@pytest.fixture(scope="session")
def test_engine():
    """Session-scoped engine fixture for research tests."""
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
    """Primary test user."""
    user = User(
        email="researcher_a@orchestra.ai",
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
        name="Project Alpha",
        description="Knowledge base for Project Alpha",
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
        email="researcher_b@orchestra.ai",
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
        name="Project Beta",
        description="Knowledge base for Project Beta",
        owner_id=test_user_b.id,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project
