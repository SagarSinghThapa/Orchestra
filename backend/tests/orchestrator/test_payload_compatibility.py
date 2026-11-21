"""
Unit tests for versioned message payload serialization, reader extraction, and safe rollback.
"""

import json
import pytest
from sqlalchemy.orm import Session

from app.models.message import Message
from app.models.session import Session as SessionModel
from app.models.project import Project
from app.models.user import User, UserRole
from app.schemas.message_payload import (
    CURRENT_PAYLOAD_VERSION,
    StructuredMessagePayload,
    extract_plain_content,
    serialize_assistant_payload,
)
from scripts.revert_message_payloads import revert_payloads


def test_serialize_assistant_payload_research():
    """Verify research payload serialization adheres to version 1 schema."""
    citations = [
        {
            "citation_id": "c1",
            "evidence_id": "e1",
            "document_id": 1,
            "document_filename": "arch.pdf",
            "page_number": 2,
            "chunk_id": "ch1",
            "start_char": 0,
            "end_char": 100,
            "text": "Orchestra uses LangGraph.",
            "score": 0.95,
        }
    ]
    claims = [{"claim_text": "Orchestra uses LangGraph.", "citation_ids": ["c1"]}]
    raw_json = serialize_assistant_payload(
        intent="research",
        answer="Orchestra is an agentic platform.",
        citations=citations,
        claims=claims,
        status="completed",
        question="What is Orchestra?",
    )

    data = json.loads(raw_json)
    assert data["version"] == CURRENT_PAYLOAD_VERSION
    assert data["intent"] == "research"
    assert data["answer"] == "Orchestra is an agentic platform."
    assert len(data["citations"]) == 1
    assert data["citations"][0]["citation_id"] == "c1"
    assert data["evidence_count"] == 1


def test_extract_plain_content_plain_text():
    """Verify extract_plain_content returns raw plain text verbatim."""
    plain = "This is a direct answer without any JSON formatting."
    assert extract_plain_content(plain) == plain


def test_extract_plain_content_version_1_payload():
    """Verify extract_plain_content extracts answer from versioned JSON."""
    raw_json = serialize_assistant_payload(
        intent="research",
        answer="Clean markdown answer text.",
        citations=[{"citation_id": "c1"}],
    )
    assert extract_plain_content(raw_json) == "Clean markdown answer text."


def test_extract_plain_content_legacy_payload():
    """Verify extract_plain_content extracts answer from unversioned legacy JSON."""
    legacy_json = json.dumps({"answer": "Legacy answer", "citations": []})
    assert extract_plain_content(legacy_json) == "Legacy answer"

    dev_json = json.dumps({"summary": "Developer patch applied", "status": "success"})
    assert extract_plain_content(dev_json) == "Developer patch applied"


def test_extract_plain_content_malformed_json():
    """Verify extract_plain_content safely falls back on malformed JSON without raising."""
    malformed = '{"version": 1, "answer": "broken json without closing'
    assert extract_plain_content(malformed) == malformed


def test_extract_plain_content_empty_or_none():
    """Verify empty or None inputs return empty string."""
    assert extract_plain_content("") == ""
    assert extract_plain_content(None) == ""


def test_rollback_script_safeguards_and_execution(db_session: Session):
    """
    Verify rollback script:
    1. Dry-run mode does not modify records.
    2. Apply mode without backup fails closed.
    3. Apply mode with backup converts versioned payload to plain text.
    """
    # Setup test project and session
    user = User(
        email="rollback_test@orchestra.ai",
        password_hash="hash",
        role=UserRole.MEMBER.value,
    )
    db_session.add(user)
    db_session.commit()

    project = Project(name="Rollback Test Project", owner_id=user.id)
    db_session.add(project)
    db_session.commit()

    session = SessionModel(
        project_id=project.id,
        title="Research Session Title",
        query="What are the findings?",
        type="research",
        status="completed",
    )
    db_session.add(session)
    db_session.commit()

    # Create one versioned assistant message and one legacy plain message
    versioned_payload = serialize_assistant_payload(
        intent="research",
        answer="Preserved research findings.",
        citations=[{"citation_id": "c1"}],
    )
    msg_versioned = Message(
        session_id=session.id,
        role="assistant",
        content=versioned_payload,
    )
    msg_plain = Message(
        session_id=session.id,
        role="user",
        content="What are the findings?",
    )
    db_session.add(msg_versioned)
    db_session.add(msg_plain)
    db_session.commit()

    # 1. Dry run execution
    revert_payloads(db=db_session, dry_run=True)
    db_session.refresh(msg_versioned)
    assert msg_versioned.content.startswith('{"version":')

    # 2. Apply without backup confirmation -> MUST FAIL
    with pytest.raises(RuntimeError, match="Missing required backup confirmation"):
        revert_payloads(db=db_session, dry_run=False, backup_confirmation=None)

    # 3. Apply with backup confirmation -> converts versioned JSON to plain text
    revert_payloads(
        db=db_session,
        dry_run=False,
        backup_confirmation="test_backup_verified_20261121",
    )
    db_session.refresh(msg_versioned)
    assert msg_versioned.content == "Preserved research findings."
    db_session.refresh(msg_plain)
    assert msg_plain.content == "What are the findings?"
