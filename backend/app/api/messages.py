from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from app.auth.dependencies import get_current_user
from app.database.connection import get_db
from app.models.message import Message
from app.models.project import Project
from app.models.session import Session
from app.models.user import User
from app.schemas.message import MessageCreate, MessageResponse


router = APIRouter(
    prefix="/sessions",
    tags=["Messages"],
)


def get_user_session(
    session_id: int,
    db: DBSession,
    current_user: User,
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


@router.post(
    "/{session_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_message(
    session_id: int,
    request: MessageCreate,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = get_user_session(
        session_id,
        db,
        current_user,
    )

    message = Message(
        session_id=session.id,
        role=request.role.value,
        content=request.content,
    )

    db.add(message)
    db.commit()
    db.refresh(message)

    return message


@router.get(
    "/{session_id}/messages",
    response_model=list[MessageResponse],
)
def get_messages(
    session_id: int,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = get_user_session(
        session_id,
        db,
        current_user,
    )

    return (
        db.query(Message)
        .filter(Message.session_id == session.id)
        .order_by(Message.created_at.asc())
        .all()
    )