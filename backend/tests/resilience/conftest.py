import os
import sqlite3
from pathlib import Path
from typing import Generator
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

from app.database.base import Base
from app.database.connection import get_db
from app.main import app
from app.core.config import settings

db_file = Path(__file__).resolve().parent.parent.parent / "test-results" / "resilience_test.db"
db_file.parent.mkdir(parents=True, exist_ok=True)

TEST_DATABASE_URL = f"sqlite:///{db_file.as_posix()}"
settings.database_url = TEST_DATABASE_URL
settings.jwt_secret = "test-jwt-secret-key-minimum-32-chars-long"
settings.environment = "test"
settings.rate_limit_backend = "memory"
settings.rate_limit_enabled = False
settings.qdrant_url = ":memory:"
settings.llm_provider = "test"
settings.embedding_provider = "test"


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()


@pytest.fixture(scope="session")
def test_engine():
    if db_file.exists():
        try:
            db_file.unlink()
        except OSError:
            pass

    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False, "timeout": 30},
        poolclass=NullPool,
    )
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
    import app.database.connection as db_conn
    import app.main as app_main
    db_conn.engine = engine
    app_main.engine = engine
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if db_file.exists():
        try:
            db_file.unlink()
        except OSError:
            pass


@pytest.fixture
def db_session(test_engine) -> Generator[Session, None, None]:
    session_factory = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
    test_session = session_factory()

    def override_get_db():
        session = session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        yield test_session
    finally:
        app.dependency_overrides.pop(get_db, None)
        test_session.close()
        with test_engine.connect() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(table.delete())
            conn.commit()

