from sqlalchemy.orm import Session

from app.memory.context_assembler import ContextAssembler
from app.memory.schemas import ContextAssemblerConfig
from app.models.message import Message as MessageModel
from app.models.project import Project
from app.models.session import Session as DBSession
from app.models.session_summary import SessionSummary


def _seed_messages(db: Session, session_id: int, count: int, content_generator=None) -> list[MessageModel]:
    messages = []
    for i in range(1, count + 1):
        content = content_generator(i) if content_generator else f"Message payload {i}"
        msg = MessageModel(
            session_id=session_id,
            role="user" if i % 2 == 1 else "assistant",
            content=content,
        )
        db.add(msg)
        messages.append(msg)
    db.commit()
    for m in messages:
        db.refresh(m)
    return messages


def test_assembler_empty_session(db_session: Session, test_session: DBSession, test_project: Project):
    """Verifies that an empty session produces a clean empty MemoryContext."""
    assembler = ContextAssembler(db=db_session)
    ctx = assembler.assemble(session_id=test_session.id, project_id=test_project.id)

    assert ctx.total_chars == 0
    assert len(ctx.recent_messages) == 0
    assert ctx.session_summary == ""
    assert ctx.project_context == ""
    assert assembler.format_for_prompt(ctx) == ""


def test_assembler_sliding_window_order(db_session: Session, test_session: DBSession, test_project: Project):
    """Verifies that sliding window messages are in chronological order."""
    _seed_messages(db_session, test_session.id, 10)

    assembler = ContextAssembler(db=db_session, config=ContextAssemblerConfig(window_size=5))
    ctx = assembler.assemble(session_id=test_session.id, project_id=test_project.id)

    assert len(ctx.recent_messages) == 5
    # Must be in strictly ascending order: message 6 through 10
    assert "payload 6" in ctx.recent_messages[0]["content"]
    assert "payload 10" in ctx.recent_messages[-1]["content"]


def test_assembler_hard_cap_guaranteed(db_session: Session, test_session: DBSession, test_project: Project):
    """Verifies that under pathological massive message loads, total_chars <= max_context_chars."""
    # Seed 20 messages, each 2,000 characters long (total 40,000 chars)
    _seed_messages(db_session, test_session.id, 20, content_generator=lambda i: "X" * 2000)

    # Seed an oversized session summary and sibling summaries
    summary = SessionSummary(
        session_id=test_session.id,
        project_id=test_project.id,
        summary_text="S" * 3000,
        message_watermark_id=1,
    )
    db_session.add(summary)
    db_session.commit()

    cfg = ContextAssemblerConfig(max_context_chars=4000)
    assembler = ContextAssembler(db=db_session, config=cfg)
    ctx = assembler.assemble(session_id=test_session.id, project_id=test_project.id)

    # Invariant assertion: hard cap must never be violated!
    assert ctx.total_chars <= 4000
    assert len(assembler.format_for_prompt(ctx)) <= 4000 + 300


def test_assembler_single_massive_message_truncated(
    db_session: Session, test_session: DBSession, test_project: Project
):
    """Verifies that even if a single message exceeds budget, it is truncated with a safety marker."""
    msg = MessageModel(
        session_id=test_session.id,
        role="user",
        content="A" * 15000,
    )
    db_session.add(msg)
    db_session.commit()

    cfg = ContextAssemblerConfig(max_context_chars=2000)
    assembler = ContextAssembler(db=db_session, config=cfg)
    ctx = assembler.assemble(session_id=test_session.id, project_id=test_project.id)

    assert ctx.total_chars <= 2000
    assert len(ctx.recent_messages) == 1
    assert "... [truncated to fit context budget]" in ctx.recent_messages[0]["content"]


def test_assembler_truncation_order(db_session: Session, test_session: DBSession, test_project: Project):
    """Verifies that project context is truncated before session summary."""
    # Create sibling session in same project
    sib = DBSession(
        project_id=test_project.id,
        type="orchestrator",
        title="Sibling Session",
        query="Sibling query",
        status="active",
    )
    db_session.add(sib)
    db_session.commit()

    # Add summaries to both
    curr_summary = SessionSummary(
        session_id=test_session.id,
        project_id=test_project.id,
        summary_text="Current summary",
        message_watermark_id=5,
    )
    sib_summary = SessionSummary(
        session_id=sib.id,
        project_id=test_project.id,
        summary_text="P" * 1000,
        message_watermark_id=5,
    )
    db_session.add_all([curr_summary, sib_summary])
    db_session.commit()

    # Small budget to force project context truncation
    cfg = ContextAssemblerConfig(max_context_chars=600)
    assembler = ContextAssembler(db=db_session, config=cfg)
    ctx = assembler.assemble(session_id=test_session.id, project_id=test_project.id)

    assert ctx.total_chars <= 600
    assert ctx.session_summary == "Current summary"
    # Project context must have been truncated to fit
    assert len(ctx.project_context) < 1000


def test_assembler_sibling_sessions_included(
    db_session: Session, test_session: DBSession, test_project: Project
):
    """Verifies that sibling sessions in the same project are included in project memory."""
    sib = DBSession(
        project_id=test_project.id,
        type="orchestrator",
        title="Sibling",
        query="Q",
        status="active",
    )
    db_session.add(sib)
    db_session.commit()

    sib_summary = SessionSummary(
        session_id=sib.id,
        project_id=test_project.id,
        summary_text="Sibling architectural decision: PostgreSQL over Redis.",
        message_watermark_id=10,
    )
    db_session.add(sib_summary)
    db_session.commit()

    assembler = ContextAssembler(db=db_session)
    ctx = assembler.assemble(session_id=test_session.id, project_id=test_project.id)

    assert "PostgreSQL over Redis" in ctx.project_context


def test_assembler_current_session_excluded_from_project_context(
    db_session: Session, test_session: DBSession, test_project: Project
):
    """Verifies that the current session's summary is never duplicated into project context."""
    summary = SessionSummary(
        session_id=test_session.id,
        project_id=test_project.id,
        summary_text="Unique current session string 98765.",
        message_watermark_id=5,
    )
    db_session.add(summary)
    db_session.commit()

    assembler = ContextAssembler(db=db_session)
    ctx = assembler.assemble(session_id=test_session.id, project_id=test_project.id)

    assert ctx.session_summary == "Unique current session string 98765."
    assert "Unique current session string 98765." not in ctx.project_context


def test_assembler_format_for_prompt(db_session: Session, test_session: DBSession, test_project: Project):
    """Verifies the XML structural formatting of MemoryContext."""
    _seed_messages(db_session, test_session.id, 2)
    summary = SessionSummary(
        session_id=test_session.id,
        project_id=test_project.id,
        summary_text="Test session summary",
        message_watermark_id=1,
    )
    db_session.add(summary)
    db_session.commit()

    assembler = ContextAssembler(db=db_session)
    ctx = assembler.assemble(session_id=test_session.id, project_id=test_project.id)
    formatted = assembler.format_for_prompt(ctx)

    assert "<SYSTEM_CONTEXT>" in formatted
    assert "<SESSION_SUMMARY>\nTest session summary\n</SESSION_SUMMARY>" in formatted
    assert "<RECENT_MESSAGES>" in formatted
    assert "</SYSTEM_CONTEXT>" in formatted

