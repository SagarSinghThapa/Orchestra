"""
Test configuration, database fixtures, and seeded users for Authentication & RBAC testing.
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
from app.core.config import settings
from app.main import app
from app.models.user import User, UserRole
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
    """Session-scoped engine fixture for auth tests."""
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
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient with overridden get_db and test JWT secret."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    old_secret = settings.jwt_secret
    settings.jwt_secret = "test-secret-key-32-chars-minimum-length!!"
    
    with TestClient(app) as test_client:
        yield test_client
        
    app.dependency_overrides.clear()
    settings.jwt_secret = old_secret


@pytest.fixture
def admin_user(db_session: Session) -> User:
    """Creates a seeded test user with 'admin' role."""
    user = User(
        email="admin@orchestra.ai",
        password_hash=hash_password("AdminSecret123!"),
        role=UserRole.ADMIN.value,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def member_user(db_session: Session) -> User:
    """Creates a seeded test user with canonical 'member' role."""
    user = User(
        email="member@orchestra.ai",
        password_hash=hash_password("MemberSecret123!"),
        role=UserRole.MEMBER.value,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def viewer_user(db_session: Session) -> User:
    """Creates a seeded test user with 'viewer' role."""
    user = User(
        email="viewer@orchestra.ai",
        password_hash=hash_password("ViewerSecret123!"),
        role=UserRole.VIEWER.value,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user
