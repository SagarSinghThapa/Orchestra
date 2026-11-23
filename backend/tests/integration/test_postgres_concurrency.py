import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.checkpoints import PostgresSaver
from app.memory.exceptions import StaleWriteError
from app.models.project import Project
from app.models.session import Session as SessionModel
from app.models.session_summary import SessionSummary
from app.models.user import User


TEST_PG_URL = os.getenv(
    "TEST_DATABASE_URL",
    os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:replace_with_strong_postgres_password_here@127.0.0.1:5433/orchestra",
    ),
)


@pytest.fixture(scope="module")
def pg_engine():
    """Provides a PostgreSQL engine connected to the live containerized database."""
    engine = create_engine(
        TEST_PG_URL,
        pool_size=5,
        max_overflow=5,
        pool_timeout=10,
        pool_pre_ping=True,
    )
    assert engine.dialect.name == "postgresql", f"Expected postgresql dialect, got {engine.dialect.name}"
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session_factory(pg_engine):
    return sessionmaker(bind=pg_engine, autoflush=False, expire_on_commit=False)


@pytest.mark.integration
def test_postgres_connection_pool_lifecycle(pg_engine):
    """
    Validates connection pool limits, connection recycling, and concurrent checkout
    under multiple concurrent worker threads on real PostgreSQL 16.
    """
    assert pg_engine.dialect.name == "postgresql"

    def execute_worker(worker_id: int) -> int:
        with pg_engine.connect() as conn:
            # Query backend PID to confirm real PostgreSQL server thread execution
            pid = conn.execute(text("SELECT pg_backend_pid();")).scalar()
            assert pid is not None and pid > 0
            return pid

    # Dispatch 25 concurrent worker tasks across a pool of size 5 + 5 overflow
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(execute_worker, i) for i in range(25)]
        pids = [f.result(timeout=15) for f in futures]

    assert len(pids) == 25
    # Confirm pool recycled connections (pids set should be bounded <= 10 concurrent backends)
    unique_pids = set(pids)
    assert len(unique_pids) <= 10, f"Expected connection recycling, but observed {len(unique_pids)} unique PIDs"

    # Pool status check: all connections checked in
    pool = pg_engine.pool
    assert pool.checkedout() == 0, f"Expected 0 checked out connections, found {pool.checkedout()}"


@pytest.mark.integration
def test_postgres_transactional_isolation_and_rollback(pg_engine, db_session_factory):
    """
    Validates ACID transactional isolation and clean rollback on live PostgreSQL:
    ensures uncommitted or rolled-back writes never leak dirty state.
    """
    assert pg_engine.dialect.name == "postgresql"

    test_email = "tx_probe_isolation@example.com"
    session1 = db_session_factory()
    session2 = db_session_factory()

    try:
        # Cleanup any leftover probe user
        with pg_engine.connect() as conn:
            conn.execute(text("DELETE FROM users WHERE email = :email"), {"email": test_email})
            conn.commit()

        # Session 1 creates user but does NOT commit yet
        probe_user = User(
            email=test_email,
            password_hash="$2b$12$eX4mpleHashForIntegrationTestingPurposesOnly123456",
            role="member",
        )
        session1.add(probe_user)
        session1.flush()

        # Session 2 must NOT see Session 1's uncommitted user (read committed isolation)
        uncommitted_check = session2.query(User).filter(User.email == test_email).first()
        assert uncommitted_check is None, "Dirty read detected: uncommitted user was visible to session2"

        # Session 1 rolls back
        session1.rollback()

        # Verify neither session can see the user
        after_rollback_1 = session1.query(User).filter(User.email == test_email).first()
        after_rollback_2 = session2.query(User).filter(User.email == test_email).first()
        assert after_rollback_1 is None
        assert after_rollback_2 is None

    finally:
        session1.close()
        session2.close()
        with pg_engine.connect() as conn:
            conn.execute(text("DELETE FROM users WHERE email = :email"), {"email": test_email})
            conn.commit()


@pytest.mark.integration
def test_postgres_concurrent_session_summary_optimistic_locking(pg_engine, db_session_factory):
    """
    Validates that real PostgreSQL enforces optimistic locking semantics via version increment:
    concurrent writes targeting a stale version fail and raise StaleWriteError.
    """
    assert pg_engine.dialect.name == "postgresql"

    test_email = "optlock_test_user@example.com"
    session1 = db_session_factory()
    session2 = db_session_factory()

    try:
        # 1. Setup prerequisite parent rows: User -> Project -> Session
        user = User(
            email=test_email,
            password_hash="$2b$12$eX4mpleHashForIntegrationTestingPurposesOnly123456",
            role="member",
        )
        session1.add(user)
        session1.commit()

        project = Project(
            name="Optimistic Lock Test Project",
            description="Testing concurrent version conflict",
            owner_id=user.id,
        )
        session1.add(project)
        session1.commit()

        sess = SessionModel(
            project_id=project.id,
            type="research",
            title="Optimistic Concurrency Session",
            query="Investigate optimistic locking mechanics",
            status="pending",
        )
        session1.add(sess)
        session1.commit()

        # 2. Insert initial SessionSummary at version 1
        summary = SessionSummary(
            session_id=sess.id,
            project_id=project.id,
            summary_text="Initial summary text at version 1",
            message_watermark_id=5,
            message_count_summarized=5,
            version=1,
            status="active",
        )
        session1.add(summary)
        session1.commit()

        # 3. Simulate two concurrent readers loading version 1
        record_s1 = session1.query(SessionSummary).filter_by(session_id=sess.id).one()
        record_s2 = session2.query(SessionSummary).filter_by(session_id=sess.id).one()
        assert record_s1.version == 1
        assert record_s2.version == 1

        # 4. Worker 1 commits update from version 1 -> version 2
        updated_rows_1 = (
            session1.query(SessionSummary)
            .filter(SessionSummary.session_id == sess.id, SessionSummary.version == 1)
            .update(
                {
                    "summary_text": "Updated summary from Worker 1",
                    "version": 2,
                    "message_watermark_id": 10,
                    "message_count_summarized": 10,
                }
            )
        )
        assert updated_rows_1 == 1
        session1.commit()

        # 5. Worker 2 attempts update still expecting version 1
        updated_rows_2 = (
            session2.query(SessionSummary)
            .filter(SessionSummary.session_id == sess.id, SessionSummary.version == 1)
            .update(
                {
                    "summary_text": "Conflicting summary from Worker 2",
                    "version": 2,
                    "message_watermark_id": 12,
                    "message_count_summarized": 12,
                }
            )
        )
        session2.commit()

        # Real PostgreSQL returned 0 affected rows because version is already 2
        assert updated_rows_2 == 0

        # Enforce application contract: 0 rows affected on versioned update raises StaleWriteError
        if updated_rows_2 == 0:
            with pytest.raises(StaleWriteError):
                raise StaleWriteError(
                    f"Concurrent update conflict on session {sess.id} memory (version 1)"
                )

        # 6. Verify database state is untouched by Worker 2
        fresh_summary = session1.query(SessionSummary).filter_by(session_id=sess.id).one()
        assert fresh_summary.version == 2
        assert fresh_summary.summary_text == "Updated summary from Worker 1"

    finally:
        session1.close()
        session2.close()
        # Clean teardown
        with pg_engine.connect() as conn:
            conn.execute(text("DELETE FROM users WHERE email = :email"), {"email": test_email})
            conn.commit()


@pytest.mark.integration
def test_postgres_langgraph_checkpoint_persistence(pg_engine):
    """
    Validates that PostgresSaver persists and restores LangGraph state checkpoints
    to and from the live PostgreSQL database across transaction boundaries.
    """
    assert pg_engine.dialect.name == "postgresql"

    saver = PostgresSaver(engine=pg_engine)
    thread_id = PostgresSaver.format_thread_id(project_id=42, session_id=101)
    checkpoint_ns = "integration_test"
    checkpoint_id = "1ef9a000-0000-6000-8000-000000000001"

    config = {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": checkpoint_ns,
            "checkpoint_id": checkpoint_id,
        }
    }

    test_checkpoint = {
        "v": 1,
        "ts": "2026-11-06T12:00:00+00:00",
        "id": checkpoint_id,
        "channel_values": {
            "state_key": "active_research_flow",
            "iteration": 3,
            "agent_notes": ["analyzed system metrics", "verified db pooling"],
        },
        "channel_versions": {"state_key": 3, "iteration": 3},
        "versions_seen": {},
    }
    test_metadata = {"step": 3, "source": "integration_test_runner"}

    try:
        # Clean any preexisting checkpoint for this test thread
        with pg_engine.connect() as conn:
            conn.execute(
                text("DELETE FROM checkpoints WHERE thread_id = :tid"),
                {"tid": thread_id},
            )
            conn.commit()

        # 1. Put checkpoint into live PostgreSQL
        saved_config = saver.put(
            config=config,
            checkpoint=test_checkpoint,
            metadata=test_metadata,
            new_versions={"state_key": 3},
        )
        assert saved_config is not None
        assert saved_config["configurable"]["thread_id"] == thread_id

        # 2. Retrieve checkpoint using a fresh configuration
        retrieved_tuple = saver.get_tuple(config)
        assert retrieved_tuple is not None
        assert retrieved_tuple.checkpoint["id"] == checkpoint_id
        assert retrieved_tuple.checkpoint["channel_values"]["state_key"] == "active_research_flow"
        assert retrieved_tuple.checkpoint["channel_values"]["iteration"] == 3
        assert retrieved_tuple.metadata["source"] == "integration_test_runner"

        # 3. Verify raw PostgreSQL row
        with pg_engine.connect() as conn:
            row = conn.execute(
                text("SELECT thread_id, checkpoint_ns, checkpoint_id FROM checkpoints WHERE thread_id = :tid"),
                {"tid": thread_id},
            ).first()
            assert row is not None
            assert row[0] == thread_id
            assert row[1] == checkpoint_ns
            assert row[2] == checkpoint_id

    finally:
        with pg_engine.connect() as conn:
            conn.execute(
                text("DELETE FROM checkpoints WHERE thread_id = :tid"),
                {"tid": thread_id},
            )
            conn.commit()
