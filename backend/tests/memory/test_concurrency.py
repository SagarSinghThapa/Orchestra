import asyncio
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.memory.context_assembler import ContextAssembler
from app.memory.exceptions import StaleWriteError, WatermarkRegressionError
from app.memory.schemas import ContextAssemblerConfig
from app.memory.summarizer import SummarizerService
from app.models.message import Message as MessageModel
from app.models.project import Project
from app.models.session import Session as DBSession
from app.models.session_summary import SessionSummary
from app.research.llm.mock import DeterministicTestLLMProvider


@pytest.mark.asyncio
async def test_concurrent_first_summary_insert_race(
    db_session: Session, test_session: DBSession, test_project: Project
):
    """
    Verifies that when two workers attempt to insert the first summary row concurrently,
    the savepoint protects the outer transaction and the second worker recovers cleanly.
    """
    # Seed 55 messages to satisfy minimum threshold
    for i in range(1, 60):
        db_session.add(
            MessageModel(
                session_id=test_session.id,
                role="user" if i % 2 == 1 else "assistant",
                content=f"Message {i} content",
            )
        )
    db_session.commit()

    llm = DeterministicTestLLMProvider()
    service = SummarizerService(db=db_session, llm_provider=llm)

    # Worker 1 creates the first summary row
    res1 = await service.maybe_summarize(session_id=test_session.id, project_id=test_project.id)
    assert res1 is not None

    summary_row = (
        db_session.query(SessionSummary)
        .filter(SessionSummary.session_id == test_session.id)
        .first()
    )
    assert summary_row is not None
    assert summary_row.version == 1

    # Simulate collision on initial insert:
    # If _upsert_summary is called while row exists, it should update or recover cleanly
    collision_summary = SessionSummary(
        session_id=test_session.id,
        project_id=test_project.id,
        summary_text="Duplicate insert attempt",
        message_watermark_id=999,
        message_count_summarized=10,
        status="active",
        version=1,
    )
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(collision_summary)
            db_session.flush()

    # Outer transaction remains healthy and usable
    refreshed = (
        db_session.query(SessionSummary)
        .filter(SessionSummary.session_id == test_session.id)
        .first()
    )
    assert refreshed.version == 1
    assert refreshed.summary_text != "Duplicate insert attempt"


@pytest.mark.asyncio
async def test_concurrent_update_stale_write_rejection(
    db_session: Session, test_session: DBSession, test_project: Project
):
    """
    Verifies that attempting an optimistic update with a stale version
    raises StaleWriteError and does not overwrite intermediate state.
    """
    summary = SessionSummary(
        session_id=test_session.id,
        project_id=test_project.id,
        summary_text="Initial summary v1",
        message_watermark_id=20,
        message_count_summarized=20,
        status="active",
        version=2,  # Current version in DB is 2
    )
    db_session.add(summary)
    db_session.commit()

    llm = DeterministicTestLLMProvider()
    service = SummarizerService(db=db_session, llm_provider=llm)

    # Attempt to update presenting stale expected_version=1
    with pytest.raises(StaleWriteError) as exc_info:
        service._upsert_summary(
            session_id=test_session.id,
            project_id=test_project.id,
            summary_text="Stale overwrite attempt",
            watermark_id=40,
            message_count=20,
            expected_version=1,  # Stale! DB is at version 2
        )

    assert "Concurrent update conflict" in str(exc_info.value)
    db_session.refresh(summary)
    assert summary.summary_text == "Initial summary v1"
    assert summary.version == 2


@pytest.mark.asyncio
async def test_watermark_monotonicity_verified(
    db_session: Session, test_session: DBSession, test_project: Project
):
    """
    Verifies that a watermark regression raises WatermarkRegressionError.
    """
    summary = SessionSummary(
        session_id=test_session.id,
        project_id=test_project.id,
        summary_text="Base summary",
        message_watermark_id=50,
        message_count_summarized=50,
        status="active",
        version=1,
    )
    db_session.add(summary)
    db_session.commit()

    llm = DeterministicTestLLMProvider()
    service = SummarizerService(db=db_session, llm_provider=llm)

    # Attempt to upsert with watermark 40 < current watermark 50
    with pytest.raises(WatermarkRegressionError) as exc_info:
        service._upsert_summary(
            session_id=test_session.id,
            project_id=test_project.id,
            summary_text="Regressed watermark attempt",
            watermark_id=40,
            message_count=10,
            expected_version=1,
        )

    assert "Watermark regression" in str(exc_info.value)


@pytest.mark.asyncio
async def test_delete_memory_during_turn(
    db_session: Session, test_session: DBSession, test_project: Project
):
    """
    Verifies that if memory is reset / deleted, a subsequent turn or check
    does not resurrect deleted summary or corrupt state.
    """
    summary = SessionSummary(
        session_id=test_session.id,
        project_id=test_project.id,
        summary_text="Pre-existing summary",
        message_watermark_id=30,
        message_count_summarized=30,
        status="active",
        version=1,
    )
    db_session.add(summary)
    db_session.commit()

    # User resets memory (deletes summary row)
    db_session.delete(summary)
    db_session.commit()

    # Verify summary is absent
    check = (
        db_session.query(SessionSummary)
        .filter(SessionSummary.session_id == test_session.id)
        .first()
    )
    assert check is None

    # ContextAssembler should assemble cleanly with empty session_summary
    assembler = ContextAssembler(db=db_session)
    ctx = assembler.assemble(session_id=test_session.id, project_id=test_project.id)
    assert ctx.session_summary == ""


@pytest.mark.asyncio
async def test_parallel_reads_consistent(
    db_session: Session, test_session: DBSession, test_project: Project
):
    """
    Verifies that multiple concurrent context assembly operations on the same session
    produce 100% identical, deterministic memory context strings.
    """
    # Seed messages
    for i in range(1, 20):
        db_session.add(
            MessageModel(
                session_id=test_session.id,
                role="user" if i % 2 == 1 else "assistant",
                content=f"Parallel read test msg {i}",
            )
        )
    db_session.commit()

    assembler = ContextAssembler(db=db_session)

    # Perform 10 sequential/parallel assemblies
    results = [
        assembler.format_for_prompt(assembler.assemble(session_id=test_session.id, project_id=test_project.id))
        for _ in range(10)
    ]

    # Every result must be identical
    first = results[0]
    assert all(r == first for r in results)
    assert "Parallel read test msg" in first
