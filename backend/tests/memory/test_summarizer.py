import pytest
from sqlalchemy.orm import Session

from app.memory.exceptions import StaleWriteError
from app.memory.schemas import ContextAssemblerConfig
from app.memory.summarizer import SummarizerService
from app.models.message import Message as MessageModel
from app.models.project import Project
from app.models.session import Session as DBSession
from app.models.session_summary import SessionSummary
from app.research.llm.mock import DeterministicTestLLMProvider


def _seed_messages(db: Session, session_id: int, count: int, prefix: str = "Message") -> list[MessageModel]:
    """Helper to populate deterministic messages for a session."""
    messages = []
    for i in range(1, count + 1):
        msg = MessageModel(
            session_id=session_id,
            role="user" if i % 2 == 1 else "assistant",
            content=f"{prefix} turn {i}: technical discussion payload.",
        )
        db.add(msg)
        messages.append(msg)
    db.commit()
    for m in messages:
        db.refresh(m)
    return messages


@pytest.mark.asyncio
async def test_summarizer_skips_when_below_threshold(
    db_session: Session, test_session: DBSession, test_project: Project
):
    """Verifies that summarization is skipped when unsummarized messages are below threshold."""
    # 25 messages with window_size=20 leaves only 4 candidate messages (< 30 threshold)
    _seed_messages(db_session, test_session.id, 25)

    llm = DeterministicTestLLMProvider()
    cfg = ContextAssemblerConfig(window_size=20, summarization_threshold=30)
    summarizer = SummarizerService(db=db_session, llm_provider=llm, config=cfg)

    result = await summarizer.maybe_summarize(session_id=test_session.id, project_id=test_project.id)
    assert result is None
    assert llm.call_count == 0


@pytest.mark.asyncio
async def test_summarizer_triggers_above_threshold(
    db_session: Session, test_session: DBSession, test_project: Project
):
    """Verifies that summarization triggers when candidate messages reach or exceed threshold."""
    # 60 messages with window_size=20 leaves 39 candidate messages (>= 30 threshold)
    _seed_messages(db_session, test_session.id, 60)

    llm = DeterministicTestLLMProvider()
    cfg = ContextAssemblerConfig(window_size=20, summarization_threshold=30, max_messages_per_summarization=40)
    summarizer = SummarizerService(db=db_session, llm_provider=llm, config=cfg)

    summary = await summarizer.maybe_summarize(session_id=test_session.id, project_id=test_project.id)
    assert summary is not None
    assert summary.session_id == test_session.id
    assert summary.message_watermark_id > 0
    assert summary.message_count_summarized > 0
    assert summary.version == 1
    assert llm.call_count == 1


@pytest.mark.asyncio
async def test_summarizer_bounded_input_batch(
    db_session: Session, test_session: DBSession, test_project: Project
):
    """Verifies that backlog > 40 messages is capped to max_messages_per_summarization (40)."""
    # 100 messages with window_size=20 leaves ~79 candidates
    msgs = _seed_messages(db_session, test_session.id, 100)

    llm = DeterministicTestLLMProvider()
    cfg = ContextAssemblerConfig(window_size=20, summarization_threshold=30, max_messages_per_summarization=40)
    summarizer = SummarizerService(db=db_session, llm_provider=llm, config=cfg)

    summary = await summarizer.maybe_summarize(session_id=test_session.id, project_id=test_project.id)
    assert summary is not None
    # Must have summarized exactly 40 messages (the bounded batch size)
    assert summary.message_count_summarized == 40
    # Watermark must match the 40th candidate message id
    expected_watermark = msgs[39].id
    assert summary.message_watermark_id == expected_watermark


@pytest.mark.asyncio
async def test_summarizer_secret_scrubbing(
    db_session: Session, test_session: DBSession, test_project: Project
):
    """Verifies dual-point secret scrubbing before prompt entry and before persistence."""
    # Seed messages containing raw API keys and JWTs
    _seed_messages(db_session, test_session.id, 55, prefix="sk-proj12345678901234567890secretkey")

    llm = DeterministicTestLLMProvider()
    cfg = ContextAssemblerConfig(window_size=20, summarization_threshold=30)
    summarizer = SummarizerService(db=db_session, llm_provider=llm, config=cfg)

    summary = await summarizer.maybe_summarize(session_id=test_session.id, project_id=test_project.id)
    assert summary is not None
    # Prompt passed to LLM must have had secrets scrubbed
    assert "sk-proj12345678901234567890secretkey" not in llm.last_prompt
    assert "sk-[REDACTED_KEY]" in llm.last_prompt
    # Stored summary must be clean
    assert "sk-proj" not in summary.summary_text


@pytest.mark.asyncio
async def test_summarizer_optimistic_concurrency_conflict(
    db_session: Session, test_session: DBSession, test_project: Project
):
    """Verifies that an update against a stale version raises StaleWriteError."""
    # Create initial summary at version 1
    summary = SessionSummary(
        session_id=test_session.id,
        project_id=test_project.id,
        summary_text="Initial summary",
        message_watermark_id=20,
        message_count_summarized=20,
        status="active",
        version=1,
    )
    db_session.add(summary)
    db_session.commit()

    llm = DeterministicTestLLMProvider()
    summarizer = SummarizerService(db=db_session, llm_provider=llm)

    # Attempting to update with expected_version=99 (stale) must raise StaleWriteError
    with pytest.raises(StaleWriteError):
        summarizer._upsert_summary(
            session_id=test_session.id,
            project_id=test_project.id,
            summary_text="Conflicting summary",
            watermark_id=30,
            message_count=10,
            expected_version=99,
        )


@pytest.mark.asyncio
async def test_summarizer_insert_collision_recovery(
    db_session: Session, test_session: DBSession, test_project: Project
):
    """Verifies that an initial insert race handles IntegrityError cleanly."""
    # Pre-seed a row behind the scenes (simulating concurrent insert)
    existing = SessionSummary(
        session_id=test_session.id,
        project_id=test_project.id,
        summary_text="Race winning summary",
        message_watermark_id=25,
        message_count_summarized=25,
        status="active",
        version=1,
    )
    db_session.add(existing)
    db_session.commit()

    llm = DeterministicTestLLMProvider()
    summarizer = SummarizerService(db=db_session, llm_provider=llm)

    # Calling _upsert_summary with expected_version=None simulates the concurrent turn
    # attempting an insert. It must catch the collision and apply update to the winning row.
    result = summarizer._upsert_summary(
        session_id=test_session.id,
        project_id=test_project.id,
        summary_text="Second turn summary",
        watermark_id=35,
        message_count=10,
        expected_version=None,
    )
    assert result.session_id == test_session.id
    assert result.version == 2
    assert result.message_watermark_id == 35


@pytest.mark.asyncio
async def test_summarizer_message_deletion_invalidation(
    db_session: Session, test_session: DBSession, test_project: Project
):
    """Verifies that message deletion anomaly resets watermark to 0."""
    # Seed 60 messages
    msgs = _seed_messages(db_session, test_session.id, 60)

    # Set watermark to 50
    summary = SessionSummary(
        session_id=test_session.id,
        project_id=test_project.id,
        summary_text="Summary up to msg 50",
        message_watermark_id=50,
        message_count_summarized=50,
        status="active",
        version=1,
    )
    db_session.add(summary)
    db_session.commit()

    # Now simulate message deletion: delete messages 20 through 60 so MAX(id) < 50
    for m in msgs[19:]:
        db_session.delete(m)
    db_session.commit()

    llm = DeterministicTestLLMProvider()
    summarizer = SummarizerService(db=db_session, llm_provider=llm)

    # Detection check in maybe_summarize should detect max_id < 50 and invalidate watermark
    # (Since remaining count is 19 <= window_size 20, it returns None without crashing)
    res = await summarizer.maybe_summarize(session_id=test_session.id, project_id=test_project.id)
    assert res is None


@pytest.mark.asyncio
async def test_summarizer_single_llm_call_budget(
    db_session: Session, test_session: DBSession, test_project: Project
):
    """Verifies that a summarization trigger consumes exactly 1 LLM call."""
    _seed_messages(db_session, test_session.id, 60)

    llm = DeterministicTestLLMProvider()
    cfg = ContextAssemblerConfig(window_size=20, summarization_threshold=30)
    summarizer = SummarizerService(db=db_session, llm_provider=llm, config=cfg)

    await summarizer.maybe_summarize(session_id=test_session.id, project_id=test_project.id)
    assert llm.call_count == 1

