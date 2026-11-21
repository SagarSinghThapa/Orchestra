from datetime import datetime
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentStatus
from app.models.project import Project


def test_document_model_creation_and_defaults(db_session: Session, test_project: Project):
    """Verifies Document ORM creation, default values, and foreign key mapping."""
    doc = Document(
        project_id=test_project.id,
        original_filename="sample_paper.pdf",
        storage_key="projects/1/sample_paper_uuid.pdf",
        content_type="application/pdf",
        size_bytes=1024,
        checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    assert doc.id is not None
    assert doc.status == DocumentStatus.UPLOADED.value
    assert doc.chunk_count == 0
    assert doc.error_message is None
    assert isinstance(doc.created_at, datetime)
    assert isinstance(doc.updated_at, datetime)
    assert doc.project.id == test_project.id
    assert doc in test_project.documents


def test_document_project_cascade_delete(db_session: Session, test_project: Project):
    """Verifies deleting a Project cascades and removes associated Document records."""
    doc = Document(
        project_id=test_project.id,
        original_filename="cascade_test.txt",
        storage_key="projects/1/cascade_test.txt",
        content_type="text/plain",
        size_bytes=42,
        checksum="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
    )
    db_session.add(doc)
    db_session.commit()
    doc_id = doc.id

    db_session.delete(test_project)
    db_session.commit()

    queried_doc = db_session.query(Document).filter(Document.id == doc_id).first()
    assert queried_doc is None


def test_duplicate_checksum_in_same_project_rejected(db_session: Session, test_project: Project):
    """Verifies that duplicate content checksum within the same project raises IntegrityError."""
    checksum = "1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff"
    doc1 = Document(
        project_id=test_project.id,
        original_filename="first_upload.pdf",
        storage_key="projects/1/first_upload.pdf",
        content_type="application/pdf",
        size_bytes=100,
        checksum=checksum,
    )
    db_session.add(doc1)
    db_session.commit()

    # Second document in SAME project with IDENTICAL checksum
    doc2 = Document(
        project_id=test_project.id,
        original_filename="second_upload_different_name.pdf",
        storage_key="projects/1/second_upload.pdf",
        content_type="application/pdf",
        size_bytes=100,
        checksum=checksum,
    )
    db_session.add(doc2)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_identical_checksum_in_different_projects_allowed(
    db_session: Session, test_project: Project, test_project_b: Project
):
    """Verifies that duplicate content checksum across DIFFERENT projects is permitted."""
    checksum = "shared_checksum_hash_1234567890abcdef1234567890abcdef1234567890"
    doc_a = Document(
        project_id=test_project.id,
        original_filename="doc_project_a.pdf",
        storage_key="projects/1/doc_project_a.pdf",
        content_type="application/pdf",
        size_bytes=200,
        checksum=checksum,
    )
    doc_b = Document(
        project_id=test_project_b.id,
        original_filename="doc_project_b.pdf",
        storage_key="projects/2/doc_project_b.pdf",
        content_type="application/pdf",
        size_bytes=200,
        checksum=checksum,
    )

    db_session.add(doc_a)
    db_session.add(doc_b)
    db_session.commit()

    assert doc_a.id is not None
    assert doc_b.id is not None
    assert doc_a.project_id != doc_b.project_id
    assert doc_a.checksum == doc_b.checksum
