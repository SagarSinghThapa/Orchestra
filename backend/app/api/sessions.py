from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from app.auth.dependencies import get_current_user
from app.database.connection import get_db
from app.models.project import Project
from app.models.session import Session
from app.models.user import User
from app.schemas.session import SessionCreate, SessionResponse


router = APIRouter(
    prefix="/sessions",
    tags=["Sessions"],
)


@router.post(
    "",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_session(
    request: SessionCreate,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = (
        db.query(Project)
        .filter(
            Project.id == request.project_id,
            Project.owner_id == current_user.id,
        )
        .first()
    )

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    session = Session(
        project_id=project.id,
        type=request.type.value,
        title=request.title,
        query=request.query,
        status="pending",
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    return session


@router.get(
    "/project/{project_id}",
    response_model=list[SessionResponse],
)
def get_project_sessions(
    project_id: int,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = (
        db.query(Project)
        .filter(
            Project.id == project_id,
            Project.owner_id == current_user.id,
        )
        .first()
    )

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return (
        db.query(Session)
        .filter(Session.project_id == project_id)
        .order_by(Session.created_at.desc())
        .all()
    )


@router.get(
    "/{session_id}",
    response_model=SessionResponse,
)
def get_session(
    session_id: int,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = (
        db.query(Session)
        .join(Project, Session.project_id == Project.id)
        .filter(
            Session.id == session_id,
            Project.owner_id == current_user.id,
        )
        .first()
    )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return session