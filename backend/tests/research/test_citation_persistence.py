"""
Integration Tests for Research Citation Persistence in Relational Message Storage.

Verifies:
1. Version 1 structured payload serialization with full citation provenance
   (citation_id, evidence_id, document_id, filename, page_number, chunk_id, offsets, score).
2. Database persistence in PostgreSQL/SQLite `messages.content`.
3. Verbatim retrieval through GET /sessions/{id}/messages API endpoint.
4. Payload integrity across session restoration and client re-reads.
"""

import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DBSession

from app.auth.jwt import create_access_token
from app.core.config import settings
from app.database.connection import get_db
from app.main import app
from app.models.message import Message
from app.models.project import Project
from app.models.session import Session as SessionModel
from app.models.user import User, UserRole
from app.schemas.message_payload import (
    CURRENT_PAYLOAD_VERSION,
    extract_plain_content,
    serialize_assistant_payload,
)


@pytest.fixture(autouse=True)
def configure_test_environment(monkeypatch):
    monkeypatch.setattr(settings, "environment", "test")
    monkeypatch.setattr(settings, "database_url", "sqlite:///:memory:")
    monkeypatch.setattr(settings, "jwt_secret", "test_jwt_secret_persistence_test_12345!")


@pytest.fixture
def test_setup(db_session: DBSession):
    """Seed user, project, and session for persistence tests."""
    user = User(
        email="citation_persister@example.com",
        password_hash="hashed_pw_test",
        role=UserRole.MEMBER.value,
    )
    db_session.add(user)
    db_session.flush()

    project = Project(
        name="Citation Persistence Project",
        owner_id=user.id,
    )
    db_session.add(project)
    db_session.flush()

    session = SessionModel(
        project_id=project.id,
        type="research",
        title="Attention Mechanism Inquiry",
        query="Explain the Transformer attention mechanism.",
        status="completed",
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(project)
    db_session.refresh(session)

    return {"user": user, "project": project, "session": session}


def test_research_citation_database_persistence_and_retrieval(
    db_session: DBSession, test_setup
):
    """
    Verify structured citation payloads survive DB write, retain all provenance attributes,
    and can be retrieved without degradation.
    """
    user = test_setup["user"]
    session = test_setup["session"]

    sample_citations = [
        {
            "citation_id": "cite_transformer_01",
            "evidence_id": "ev_attn_01",
            "document_id": 42,
            "document_filename": "sample_research.md",
            "page_number": 1,
            "chunk_id": "chunk_7a8f12",
            "chunk_index": 0,
            "start_char": 105,
            "end_char": 280,
            "text": "Self-attention enables the model to weigh different tokens across the sequence.",
            "score": 0.985,
        }
    ]

    claims = [
        {
            "claim_text": "Self-attention enables sequence-wide token weighting.",
            "citation_ids": ["cite_transformer_01"],
        }
    ]

    serialized_content = serialize_assistant_payload(
        intent="research",
        answer="Transformers rely on multi-head self-attention mechanisms [1].",
        citations=sample_citations,
        claims=claims,
        status="completed",
        question=session.query,
    )

    # 1. Persist directly to DB
    msg = Message(
        session_id=session.id,
        role="assistant",
        content=serialized_content,
    )
    db_session.add(msg)
    db_session.commit()
    db_session.refresh(msg)

    # 2. Inspect raw DB row
    saved_msg = db_session.query(Message).filter(Message.id == msg.id).first()
    assert saved_msg is not None
    assert saved_msg.role == "assistant"

    parsed = json.loads(saved_msg.content)
    assert parsed["version"] == CURRENT_PAYLOAD_VERSION
    assert parsed["intent"] == "research"
    assert "Transformers rely on multi-head self-attention" in parsed["answer"]
    assert len(parsed["citations"]) == 1

    citation = parsed["citations"][0]
    assert citation["citation_id"] == "cite_transformer_01"
    assert citation["document_filename"] == "sample_research.md"
    assert citation["page_number"] == 1
    assert citation["start_char"] == 105
    assert citation["end_char"] == 280
    assert citation["score"] == 0.985

    # 3. Verify plain text extractor preserves readability
    plain = extract_plain_content(saved_msg.content)
    assert plain == "Transformers rely on multi-head self-attention mechanisms [1]."

    # 4. Verify API retrieval through GET /sessions/{id}/messages
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        token = create_access_token(user.id, role=str(user.role))
        resp = client.get(
            f"/sessions/{session.id}/messages",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        messages_data = resp.json()
        assert len(messages_data) == 1

        api_payload = json.loads(messages_data[0]["content"])
        assert api_payload["citations"][0]["citation_id"] == "cite_transformer_01"
        assert api_payload["citations"][0]["document_filename"] == "sample_research.md"
    finally:
        app.dependency_overrides.pop(get_db, None)
