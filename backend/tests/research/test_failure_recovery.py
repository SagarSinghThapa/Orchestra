import io
import pytest
import pypdf
from unittest.mock import patch
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.models.document import Document, DocumentStatus
from app.models.project import Project
from app.models.user import User
from tests.research.test_parsers import build_synthetic_pdf


class TestFailureRecoveryAndCompensation:
    def test_zero_extractable_text_marks_document_failed(
        self, client: TestClient, set_auth, test_user: User, test_project: Project, db_session
    ):
        set_auth(test_user)
        # Create blank PDF
        w = pypdf.PdfWriter()
        w.add_blank_page(width=100, height=100)
        buf = io.BytesIO()
        w.write(buf)
        blank_pdf = buf.getvalue()

        response = client.post(
            f"/projects/{test_project.id}/documents",
            files={"file": ("blank.pdf", blank_pdf, "application/pdf")},
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["status"] == DocumentStatus.FAILED.value
        assert "no extractable text; OCR is not supported" in data["error_message"]

        # Verify DB state
        doc = db_session.query(Document).filter(Document.id == data["id"]).first()
        assert doc.status == DocumentStatus.FAILED.value
        assert doc.chunk_count == 0

    def test_corrupted_pdf_marks_document_failed(
        self, client: TestClient, set_auth, test_user: User, test_project: Project
    ):
        set_auth(test_user)
        corrupted_pdf = b"%PDF-malformed_pdf_stream_content"

        response = client.post(
            f"/projects/{test_project.id}/documents",
            files={"file": ("corrupt.pdf", corrupted_pdf, "application/pdf")},
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["status"] == DocumentStatus.FAILED.value
        assert "Corrupted or malformed PDF file" in data["error_message"]

    def test_page_limit_guard_marks_document_failed(
        self, client: TestClient, set_auth, test_user: User, test_project: Project, monkeypatch
    ):
        set_auth(test_user)
        monkeypatch.setattr(settings, "max_pdf_pages", 1)
        two_page_pdf = build_synthetic_pdf(page_count=2)

        response = client.post(
            f"/projects/{test_project.id}/documents",
            files={"file": ("twopage.pdf", two_page_pdf, "application/pdf")},
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["status"] == DocumentStatus.FAILED.value
        assert "exceeds maximum allowed limit of 1 pages" in data["error_message"]

    def test_reindex_document_after_issue_resolution(
        self,
        client: TestClient,
        set_auth,
        test_user: User,
        test_project: Project,
        monkeypatch,
        test_vectorstore,
        db_session,
    ):
        set_auth(test_user)

        # 1. Upload 2-page PDF while max_pdf_pages=1 to induce failure
        monkeypatch.setattr(settings, "max_pdf_pages", 1)
        two_page_pdf = build_synthetic_pdf(page_count=2)

        res_upload = client.post(
            f"/projects/{test_project.id}/documents",
            files={"file": ("repairable.pdf", two_page_pdf, "application/pdf")},
        )
        doc_id = res_upload.json()["id"]
        assert res_upload.json()["status"] == DocumentStatus.FAILED.value

        # 2. Resolve the limit
        monkeypatch.setattr(settings, "max_pdf_pages", 500)

        # 3. Trigger reindex
        res_reindex = client.post(f"/projects/{test_project.id}/documents/{doc_id}/reindex")
        assert res_reindex.status_code == status.HTTP_200_OK
        data = res_reindex.json()
        assert data["status"] == DocumentStatus.INDEXED.value
        assert data["error_message"] is None
        assert data["chunk_count"] > 0

        # Verify DB state
        doc_db = db_session.query(Document).filter(Document.id == doc_id).first()
        assert doc_db.status == DocumentStatus.INDEXED.value

    def test_storage_compensation_on_db_insert_failure(
        self,
        client: TestClient,
        set_auth,
        test_user: User,
        test_project: Project,
        test_storage,
    ):
        set_auth(test_user)
        content = b"Transient content subject to DB error."

        # Mock db.commit to raise an unexpected database exception during document insertion
        with patch("sqlalchemy.orm.Session.commit", side_effect=Exception("Database connection terminated")):
            response = client.post(
                f"/projects/{test_project.id}/documents",
                files={"file": ("db_fail.txt", content, "text/plain")},
            )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.json()["detail"] == "Document creation failed"

        # Verify storage compensation: no orphaned files left in storage
        project_dir = test_storage.root_dir / f"projects/{test_project.id}"
        stored_files = list(project_dir.glob("*")) if project_dir.exists() else []
        assert len(stored_files) == 0

    def test_concurrent_duplicate_race_simulation(
        self,
        client: TestClient,
        set_auth,
        test_user: User,
        test_project: Project,
        test_storage,
    ):
        set_auth(test_user)
        content = b"Content simulating concurrent unique constraint collision."

        # Simulate concurrent collision raising IntegrityError on commit
        with patch(
            "sqlalchemy.orm.Session.commit",
            side_effect=IntegrityError("UNIQUE constraint failed", params=None, orig=Exception("uq_project_document_checksum")),
        ):
            response = client.post(
                f"/projects/{test_project.id}/documents",
                files={"file": ("race.txt", content, "text/plain")},
            )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "identical content already exists" in response.json()["detail"]

        # Verify compensating storage deletion occurred
        project_dir = test_storage.root_dir / f"projects/{test_project.id}"
        stored_files = list(project_dir.glob("*")) if project_dir.exists() else []
        assert len(stored_files) == 0
