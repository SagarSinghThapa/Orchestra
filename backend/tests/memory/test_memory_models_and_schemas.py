from datetime import datetime
import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.session import Session as DBSession
from app.models.session_summary import SessionSummary
from app.models.user import User
from app.memory.schemas import (
    ContextAssemblerConfig,
    MemoryContext,
    MemoryStats,
    SessionSummarySchema,
    SummarizationResponse,
    SummaryStatus,
)


def test_session_summary_model_creation(test_session: DBSession, test_project: Project):
    """Verifies SessionSummary model instantiation and basic attributes."""
    summary = SessionSummary(
        session_id=test_session.id,
        project_id=test_project.id,
        summary_text="Initial conversation covered basic architecture.",
        message_watermark_id=10,
        message_count_summarized=10,
    )
    assert summary.session_id == test_session.id
    assert summary.project_id == test_project.id
    assert summary.summary_text == "Initial conversation covered basic architecture."
    assert summary.message_watermark_id == 10
    assert summary.message_count_summarized == 10


def test_session_summary_model_defaults(db_session: Session, test_session: DBSession, test_project: Project):
    """Verifies default values on SessionSummary model upon insertion."""
    summary = SessionSummary(
        session_id=test_session.id,
        project_id=test_project.id,
        summary_text="Testing default values.",
        message_watermark_id=5,
    )
    db_session.add(summary)
    db_session.commit()
    db_session.refresh(summary)

    assert summary.status == "active"
    assert summary.version == 1
    assert summary.message_count_summarized == 0
    assert isinstance(summary.created_at, datetime)
    assert isinstance(summary.updated_at, datetime)


def test_session_summary_persists_and_retrieves(db_session: Session, test_session: DBSession, test_project: Project):
    """Verifies round-trip persistence and query of SessionSummary in database."""
    summary = SessionSummary(
        session_id=test_session.id,
        project_id=test_project.id,
        summary_text="Persistence validation test.",
        message_watermark_id=15,
        message_count_summarized=15,
        status="active",
        version=2,
    )
    db_session.add(summary)
    db_session.commit()

    retrieved = db_session.query(SessionSummary).filter(SessionSummary.session_id == test_session.id).first()
    assert retrieved is not None
    assert retrieved.id == summary.id
    assert retrieved.summary_text == "Persistence validation test."
    assert retrieved.version == 2
    assert retrieved.session.id == test_session.id
    assert test_session.summary.id == summary.id


def test_session_summary_unique_session_constraint(db_session: Session, test_session: DBSession, test_project: Project):
    """Verifies that each Session can have at most one SessionSummary row."""
    summary1 = SessionSummary(
        session_id=test_session.id,
        project_id=test_project.id,
        summary_text="First summary row.",
        message_watermark_id=5,
    )
    db_session.add(summary1)
    db_session.commit()

    # Attempting to insert a duplicate for the same session_id must fail
    summary2 = SessionSummary(
        session_id=test_session.id,
        project_id=test_project.id,
        summary_text="Colliding summary row.",
        message_watermark_id=10,
    )
    db_session.add(summary2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_session_summary_cascade_delete(db_session: Session, test_session: DBSession, test_project: Project):
    """Verifies that deleting a Session cascades to delete its SessionSummary."""
    summary = SessionSummary(
        session_id=test_session.id,
        project_id=test_project.id,
        summary_text="Summary to be cascade deleted.",
        message_watermark_id=7,
    )
    db_session.add(summary)
    db_session.commit()
    summary_id = summary.id

    # Delete the parent session
    db_session.delete(test_session)
    db_session.commit()

    # Verify summary was cascade-deleted
    orphan = db_session.query(SessionSummary).filter(SessionSummary.id == summary_id).first()
    assert orphan is None


def test_memory_context_schema_validation():
    """Verifies MemoryContext pydantic schema validation and extra fields rejection."""
    ctx = MemoryContext(
        project_context="Sibling session summary context.",
        session_summary="Current session summary.",
        recent_messages=[{"role": "user", "content": "Hello"}],
        total_chars=120,
    )
    assert ctx.total_chars == 120
    assert len(ctx.recent_messages) == 1

    with pytest.raises(ValidationError):
        MemoryContext(
            project_context="Test",
            unexpected_field="disallowed",
        )


def test_context_assembler_config_defaults():
    """Verifies ContextAssemblerConfig default parameters."""
    cfg = ContextAssemblerConfig()
    assert cfg.window_size == 20
    assert cfg.summarization_threshold == 30
    assert cfg.max_project_summaries == 5
    assert cfg.max_context_chars == 4000
    assert cfg.max_messages_per_summarization == 40
    assert cfg.max_summarization_input_chars == 12000


def test_context_assembler_config_bounds():
    """Verifies that ContextAssemblerConfig enforces ge/le parameter bounds."""
    with pytest.raises(ValidationError):
        ContextAssemblerConfig(window_size=1)  # ge=2

    with pytest.raises(ValidationError):
        ContextAssemblerConfig(window_size=101)  # le=100

    with pytest.raises(ValidationError):
        ContextAssemblerConfig(max_context_chars=400)  # ge=500


def test_summarization_response_min_length():
    """Verifies that SummarizationResponse requires non-empty summary text."""
    with pytest.raises(ValidationError):
        SummarizationResponse(summary="")

    resp = SummarizationResponse(
        summary="Valid condensed summary.",
        key_topics=["testing", "architecture"],
        decisions_made=["Approved schema"],
    )
    assert resp.summary == "Valid condensed summary."
    assert len(resp.key_topics) == 2


def test_session_summary_schema_from_attributes(db_session: Session, test_session: DBSession, test_project: Project):
    """Verifies that SessionSummarySchema can be constructed from ORM instances."""
    summary = SessionSummary(
        session_id=test_session.id,
        project_id=test_project.id,
        summary_text="ORM translation test summary.",
        message_watermark_id=20,
        message_count_summarized=20,
        status="active",
        version=1,
    )
    db_session.add(summary)
    db_session.commit()

    schema = SessionSummarySchema.model_validate(summary)
    assert schema.id == summary.id
    assert schema.session_id == test_session.id
    assert schema.summary_text == "ORM translation test summary."
    assert schema.status == SummaryStatus.ACTIVE
    assert schema.version == 1


def test_memory_stats_schema():
    """Verifies MemoryStats schema validation."""
    stats = MemoryStats(
        session_id=42,
        summary_exists=True,
        summary_version=3,
        message_watermark_id=35,
        messages_summarized_count=35,
        sliding_window_message_count=20,
        assembled_context_chars=3120,
    )
    assert stats.session_id == 42
    assert stats.summary_exists is True
    assert stats.assembled_context_chars == 3120

