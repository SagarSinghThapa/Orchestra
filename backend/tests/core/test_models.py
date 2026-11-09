from datetime import datetime, timedelta
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.project import Project
from app.models.session import Session as DBSession
from app.models.message import Message


def test_user_model_crud_and_uniqueness(db_session: Session):
    """Verifies User model CRUD operations and unique constraint on email."""
    # Create
    user = User(
        email="test_unique@orchestra.ai",
        password_hash="hashed_pw_123",
    )
    db_session.add(user)
    db_session.commit()
    assert user.id is not None
    assert isinstance(user.created_at, datetime)

    # Read
    queried = db_session.query(User).filter(User.email == "test_unique@orchestra.ai").first()
    assert queried is not None
    assert queried.id == user.id

    # Update
    queried.password_hash = "updated_pw_456"
    db_session.commit()
    db_session.refresh(queried)
    assert queried.password_hash == "updated_pw_456"

    # Unique Constraint Validation
    duplicate_user = User(
        email="test_unique@orchestra.ai",
        password_hash="another_pw_789",
    )
    db_session.add(duplicate_user)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_project_model_relationships(db_session: Session, test_user: User, test_project: Project):
    """Verifies Project relationships and bidirectional navigation."""
    assert test_project.owner_id == test_user.id
    assert test_project.owner.email == test_user.email
    assert test_project in test_user.projects


def test_project_cascade_delete(db_session: Session, test_user: User, test_project: Project):
    """Verifies deleting a User cascades and deletes their associated projects."""
    project_id = test_project.id
    user_id = test_user.id

    db_session.delete(test_user)
    db_session.commit()

    # User must be deleted
    assert db_session.query(User).filter(User.id == user_id).first() is None
    # Cascaded Project must be deleted
    assert db_session.query(Project).filter(Project.id == project_id).first() is None


def test_session_model_crud_and_status(
    db_session: Session, test_project: Project, test_session_obj: DBSession
):
    """Verifies Session model CRUD, status transitions, and project relationships."""
    assert test_session_obj.project_id == test_project.id
    assert test_session_obj.status == "pending"
    assert test_session_obj in test_project.sessions

    # Update status
    test_session_obj.status = "completed"
    db_session.commit()
    db_session.refresh(test_session_obj)
    assert test_session_obj.status == "completed"


def test_session_cascade_delete(
    db_session: Session, test_project: Project, test_session_obj: DBSession
):
    """Verifies deleting a Project cascades and deletes its associated sessions."""
    session_id = test_session_obj.id
    project_id = test_project.id

    db_session.delete(test_project)
    db_session.commit()

    assert db_session.query(Project).filter(Project.id == project_id).first() is None
    assert db_session.query(DBSession).filter(DBSession.id == session_id).first() is None


def test_message_model_ordering_and_cascade(db_session: Session, test_session_obj: DBSession):
    """Verifies Message creation, chronological ordering, and cascade deletion from session."""
    now = datetime.utcnow()
    m1 = Message(
        session_id=test_session_obj.id,
        role="user",
        content="Please analyze repo telemetry",
        created_at=now,
    )
    m2 = Message(
        session_id=test_session_obj.id,
        role="assistant",
        content="Repository telemetry analyzed: FastAPI + LangGraph detected",
        created_at=now + timedelta(seconds=1),
    )
    db_session.add_all([m1, m2])
    db_session.commit()

    messages = (
        db_session.query(Message)
        .filter(Message.session_id == test_session_obj.id)
        .order_by(Message.created_at.asc())
        .all()
    )
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"
    assert messages[0].session.id == test_session_obj.id

    # Cascade delete verification
    session_id = test_session_obj.id
    db_session.delete(test_session_obj)
    db_session.commit()

    remaining_messages = (
        db_session.query(Message).filter(Message.session_id == session_id).all()
    )
    assert len(remaining_messages) == 0
