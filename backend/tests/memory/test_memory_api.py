import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.message import Message as MessageModel
from app.models.project import Project
from app.models.session import Session as DBSession
from app.models.session_summary import SessionSummary
from app.models.user import User


def test_get_summary_success(
    client: TestClient,
    set_auth,
    db_session: Session,
    test_user: User,
    test_project: Project,
    test_session: DBSession,
):
    """Verifies that project owner can retrieve existing session summary."""
    summary = SessionSummary(
        session_id=test_session.id,
        project_id=test_project.id,
        summary_text="Architectural design discussion concluded RS256 JWT.",
        message_watermark_id=10,
        message_count_summarized=10,
        status="active",
        version=1,
    )
    db_session.add(summary)
    db_session.commit()

    set_auth(test_user)
    resp = client.get(f"/projects/{test_project.id}/sessions/{test_session.id}/memory")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["session_id"] == test_session.id
    assert data["project_id"] == test_project.id
    assert data["summary_text"] == "Architectural design discussion concluded RS256 JWT."
    assert data["message_watermark_id"] == 10
    assert data["version"] == 1
    assert data["status"] == "active"


def test_get_summary_not_found(
    client: TestClient,
    set_auth,
    test_user: User,
    test_project: Project,
    test_session: DBSession,
):
    """Verifies that requesting summary for a session without one returns 404."""
    set_auth(test_user)
    resp = client.get(f"/projects/{test_project.id}/sessions/{test_session.id}/memory")
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    assert "No summary found" in resp.json()["detail"]


def test_get_summary_idor_foreign_user(
    client: TestClient,
    set_auth,
    db_session: Session,
    test_project: Project,
    test_session: DBSession,
    foreign_user: User,
):
    """
    Verifies that a foreign user requesting another user's session memory
    receives 404 (preventing information disclosure via IDOR).
    """
    summary = SessionSummary(
        session_id=test_session.id,
        project_id=test_project.id,
        summary_text="Classified business intelligence.",
        message_watermark_id=5,
        message_count_summarized=5,
        status="active",
        version=1,
    )
    db_session.add(summary)
    db_session.commit()

    set_auth(foreign_user)
    resp = client.get(f"/projects/{test_project.id}/sessions/{test_session.id}/memory")
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_get_summary_cross_project_mismatch(
    client: TestClient,
    set_auth,
    db_session: Session,
    test_user: User,
    test_project: Project,
    test_session: DBSession,
    foreign_project: Project,
):
    """
    Verifies that requesting a valid session with a mismatched project_id returns 404.
    """
    set_auth(test_user)
    resp = client.get(f"/projects/{foreign_project.id}/sessions/{test_session.id}/memory")
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_get_memory_stats_success(
    client: TestClient,
    set_auth,
    db_session: Session,
    test_user: User,
    test_project: Project,
    test_session: DBSession,
):
    """
    Verifies clean memory telemetry inspection without exposing internal prompt templates or raw XML.
    """
    # Seed messages and summary
    for i in range(1, 15):
        db_session.add(
            MessageModel(
                session_id=test_session.id,
                role="user" if i % 2 == 1 else "assistant",
                content=f"Message {i} telemetry content",
            )
        )
    summary = SessionSummary(
        session_id=test_session.id,
        project_id=test_project.id,
        summary_text="Summarized context for telemetry test.",
        message_watermark_id=10,
        message_count_summarized=10,
        status="active",
        version=1,
    )
    db_session.add(summary)
    db_session.commit()

    set_auth(test_user)
    resp = client.get(f"/projects/{test_project.id}/sessions/{test_session.id}/memory/stats")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()

    assert data["session_id"] == test_session.id
    assert data["summary_exists"] is True
    assert data["summary_version"] == 1
    assert data["message_watermark_id"] == 10
    assert data["messages_summarized_count"] == 10
    assert data["sliding_window_message_count"] == 14  # 14 recent messages retrieved within window_size (30)
    assert data["assembled_context_chars"] > 0
    # Crucial guarantee: no XML tags or internal prompt templates leaked in stats response
    assert "<SystemInstructions>" not in str(data)
    assert "<ConversationSummary>" not in str(data)


def test_delete_memory_preserves_messages(
    client: TestClient,
    set_auth,
    db_session: Session,
    test_user: User,
    test_project: Project,
    test_session: DBSession,
):
    """
    Verifies that DELETE /memory removes the derived SessionSummary row
    while preserving all underlying raw Message rows.
    """
    # Seed messages
    for i in range(1, 6):
        db_session.add(
            MessageModel(
                session_id=test_session.id,
                role="user" if i % 2 == 1 else "assistant",
                content=f"Turn {i} message to preserve",
            )
        )
    summary = SessionSummary(
        session_id=test_session.id,
        project_id=test_project.id,
        summary_text="Summary to be reset.",
        message_watermark_id=5,
        message_count_summarized=5,
        status="active",
        version=1,
    )
    db_session.add(summary)
    db_session.commit()

    set_auth(test_user)
    resp = client.delete(f"/projects/{test_project.id}/sessions/{test_session.id}/memory")
    assert resp.status_code == status.HTTP_204_NO_CONTENT

    # Verify SessionSummary deleted
    check_summary = (
        db_session.query(SessionSummary)
        .filter(SessionSummary.session_id == test_session.id)
        .first()
    )
    assert check_summary is None

    # Verify Message rows untouched
    remaining_msgs = (
        db_session.query(MessageModel)
        .filter(MessageModel.session_id == test_session.id)
        .all()
    )
    assert len(remaining_msgs) == 5


def test_delete_memory_idor(
    client: TestClient,
    set_auth,
    db_session: Session,
    test_project: Project,
    test_session: DBSession,
    foreign_user: User,
):
    """
    Verifies that a foreign user cannot delete another user's session memory.
    """
    summary = SessionSummary(
        session_id=test_session.id,
        project_id=test_project.id,
        summary_text="Protected summary.",
        message_watermark_id=5,
        message_count_summarized=5,
        status="active",
        version=1,
    )
    db_session.add(summary)
    db_session.commit()

    set_auth(foreign_user)
    resp = client.delete(f"/projects/{test_project.id}/sessions/{test_session.id}/memory")
    assert resp.status_code == status.HTTP_404_NOT_FOUND

    # Summary must still exist
    check = (
        db_session.query(SessionSummary)
        .filter(SessionSummary.session_id == test_session.id)
        .first()
    )
    assert check is not None


def test_rebuild_summary_explicit(
    client: TestClient,
    set_auth,
    db_session: Session,
    test_user: User,
    test_project: Project,
    test_session: DBSession,
):
    """
    Verifies that POST /memory/rebuild deletes existing summary and forces clean rebuild.
    """
    # Seed messages
    for i in range(1, 55):
        db_session.add(
            MessageModel(
                session_id=test_session.id,
                role="user" if i % 2 == 1 else "assistant",
                content=f"Message {i} content for rebuild",
            )
        )
    old_summary = SessionSummary(
        session_id=test_session.id,
        project_id=test_project.id,
        summary_text="Old outdated summary.",
        message_watermark_id=10,
        message_count_summarized=10,
        status="active",
        version=1,
    )
    db_session.add(old_summary)
    db_session.commit()

    set_auth(test_user)
    resp = client.post(f"/projects/{test_project.id}/sessions/{test_session.id}/memory/rebuild")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()

    assert data["session_id"] == test_session.id
    assert data["summary_text"] != "Old outdated summary."
    assert data["message_watermark_id"] > 10
