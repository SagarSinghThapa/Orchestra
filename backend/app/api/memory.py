from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.documents import get_user_project
from app.auth.dependencies import get_current_user
from app.database.connection import get_db
from app.memory.context_assembler import ContextAssembler
from app.memory.schemas import MemoryStats, SessionSummarySchema
from app.memory.summarizer import SummarizerService
from app.models.session import Session as SessionModel
from app.models.session_summary import SessionSummary
from app.models.user import User
from app.research.llm.provider import get_llm_provider

router = APIRouter(
    prefix="/projects/{project_id}/sessions/{session_id}/memory",
    tags=["Memory"],
)


def _get_user_session(
    project_id: int,
    session_id: int,
    current_user: User,
    db: Session,
) -> SessionModel:
    """
    Enforces project ownership and session-to-project boundary binding.
    Returns 404 for unauthorized access, preventing information disclosure.
    Cost: 0 LLM calls.
    """
    project = get_user_project(project_id, current_user, db)
    session = (
        db.query(SessionModel)
        .filter(SessionModel.id == session_id, SessionModel.project_id == project.id)
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found in project {project_id}.",
        )
    return session


@router.get(
    "",
    response_model=SessionSummarySchema,
    status_code=status.HTTP_200_OK,
)
def get_session_summary(
    project_id: int,
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionSummarySchema:
    """
    Retrieves the persisted summary for a session.
    Returns 404 if project/session not owned, or if no summary exists yet.
    """
    _get_user_session(project_id, session_id, current_user, db)
    summary = (
        db.query(SessionSummary)
        .filter(SessionSummary.session_id == session_id)
        .first()
    )
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No summary found for this session.",
        )
    return SessionSummarySchema.model_validate(summary)


@router.get(
    "/stats",
    response_model=MemoryStats,
    status_code=status.HTTP_200_OK,
)
def get_memory_stats(
    project_id: int,
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MemoryStats:
    """
    Inspects clean memory telemetry without exposing internal prompt templates or raw XML layout.
    Pure read operation — 0 LLM calls.
    """
    _get_user_session(project_id, session_id, current_user, db)
    summary = (
        db.query(SessionSummary)
        .filter(SessionSummary.session_id == session_id)
        .first()
    )
    assembler = ContextAssembler(db=db)
    ctx = assembler.assemble(session_id=session_id, project_id=project_id)

    return MemoryStats(
        session_id=session_id,
        summary_exists=summary is not None,
        summary_version=summary.version if summary else 0,
        message_watermark_id=summary.message_watermark_id if summary else 0,
        messages_summarized_count=summary.message_count_summarized if summary else 0,
        sliding_window_message_count=len(ctx.recent_messages),
        assembled_context_chars=ctx.total_chars,
    )


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
)
def reset_session_memory(
    project_id: int,
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """
    Resets conversational summary for a session.
    Preserves raw Message rows, deletes only the derived SessionSummary row.
    Next turn will assemble context from raw messages only.
    """
    _get_user_session(project_id, session_id, current_user, db)
    summary = (
        db.query(SessionSummary)
        .filter(SessionSummary.session_id == session_id)
        .first()
    )
    if summary:
        db.delete(summary)
        db.commit()


@router.post(
    "/rebuild",
    response_model=SessionSummarySchema,
    status_code=status.HTTP_200_OK,
)
async def rebuild_session_summary(
    project_id: int,
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionSummarySchema:
    """
    Explicitly forces a rebuild of the session summary from conversation messages.
    Deletes any existing summary and re-summarizes from message 0.
    Cost: <= 1 LLM call.
    """
    _get_user_session(project_id, session_id, current_user, db)
    llm = get_llm_provider()
    summarizer = SummarizerService(db=db, llm_provider=llm)

    # Delete existing summary to force clean rebuild
    existing = (
        db.query(SessionSummary)
        .filter(SessionSummary.session_id == session_id)
        .first()
    )
    if existing:
        db.delete(existing)
        db.commit()

    # Trigger summarization covering available messages
    summary = await summarizer.maybe_summarize(session_id=session_id, project_id=project_id)
    if not summary:
        # If below threshold, create an initial summary row for message 0
        summary = summarizer._upsert_summary(
            session_id=session_id,
            project_id=project_id,
            summary_text="Initial conversation state.",
            watermark_id=0,
            message_count=0,
            expected_version=None,
        )
    return SessionSummarySchema.model_validate(summary)

