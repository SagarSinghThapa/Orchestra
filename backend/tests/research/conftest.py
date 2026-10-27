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
from app.research.embeddings.mock import DeterministicTestEmbeddingProvider
from app.research.services.ingestion_service import IngestionService
from app.research.storage.local import LocalStorageBackend
from app.research.vectorstore.qdrant import QdrantVectorStore

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")


@pytest.fixture(autouse=True)
def test_environment(monkeypatch):
    """Enforces test environment mode during research test runs."""
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


@pytest.fixture
def test_storage(tmp_path):
    """Isolated storage backend rooted in test temporary directory."""
    return LocalStorageBackend(root_dir=str(tmp_path / "storage"))


@pytest.fixture
def test_vectorstore():
    """Isolated in-memory Qdrant vector store."""
    return QdrantVectorStore(location=":memory:", collection_name="test_orchestra_knowledge")


@pytest.fixture
def test_embedding_provider():
    """Deterministic offline embedding provider for test suite."""
    return DeterministicTestEmbeddingProvider(dimension=settings.embedding_dimension)


@pytest.fixture
def test_ingestion_service(
    db_session: Session, test_storage, test_vectorstore, test_embedding_provider
):
    """Configured test IngestionService with isolated storage and in-memory vector store."""
    return IngestionService(
        db=db_session,
        storage=test_storage,
        vector_store=test_vectorstore,
        embedding_provider=test_embedding_provider,
    )


@pytest.fixture
def test_retrieval_service(
    db_session: Session, test_vectorstore, test_embedding_provider
):
    """Configured test RetrievalService with isolated in-memory vector store."""
    from app.research.services.retrieval_service import RetrievalService

    return RetrievalService(
        db=db_session,
        vector_store=test_vectorstore,
        embedding_provider=test_embedding_provider,
    )


@pytest.fixture
def test_llm_provider():
    """Deterministic offline LLM provider for test suite."""
    from app.research.llm.mock import DeterministicTestLLMProvider

    return DeterministicTestLLMProvider()


@pytest.fixture
def test_research_service(
    db_session: Session, test_retrieval_service, test_llm_provider
):
    """Configured test ResearchService with isolated retrieval and deterministic LLM."""
    from app.research.services.research_service import ResearchService

    return ResearchService(
        db=db_session,
        retrieval_service=test_retrieval_service,
        llm_provider=test_llm_provider,
    )


@pytest.fixture
def client(
    db_session: Session, test_ingestion_service, test_retrieval_service, test_research_service
) -> Generator[TestClient, None, None]:
    """TestClient overriding get_db, get_ingestion_service, get_retrieval_service, and get_research_service."""
    from app.auth.dependencies import get_current_user
    from app.api.documents import get_ingestion_service
    from app.api.search import get_retrieval_service
    from app.api.research import get_research_service

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_ingestion_service] = lambda: test_ingestion_service
    app.dependency_overrides[get_retrieval_service] = lambda: test_retrieval_service
    app.dependency_overrides[get_research_service] = lambda: test_research_service

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_ingestion_service, None)
    app.dependency_overrides.pop(get_retrieval_service, None)
    app.dependency_overrides.pop(get_research_service, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def set_auth():
    """Helper to dynamically switch authenticated user for API requests."""
    from app.auth.dependencies import get_current_user

    def _set(user: User):
        app.dependency_overrides[get_current_user] = lambda: user

    yield _set
    app.dependency_overrides.pop(get_current_user, None)
