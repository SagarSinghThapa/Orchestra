import io
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.core.config import settings
from app.models.document import Document, DocumentStatus
from app.models.project import Project
from app.models.user import User
from tests.research.test_parsers import build_synthetic_pdf


class TestDocumentAPI:
    def test_upload_valid_pdf_success(
        self, client: TestClient, set_auth, test_user: User, test_project: Project
    ):
        set_auth(test_user)
        pdf_bytes = build_synthetic_pdf(page_count=2)

        response = client.post(
            f"/projects/{test_project.id}/documents",
            files={"file": ("quantum_research.pdf", pdf_bytes, "application/pdf")},
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["original_filename"] == "quantum_research.pdf"
        assert data["status"] == DocumentStatus.INDEXED.value
        assert data["chunk_count"] > 0
        assert data["project_id"] == test_project.id
        assert "id" in data

    def test_upload_valid_txt_and_md_success(
        self, client: TestClient, set_auth, test_user: User, test_project: Project
    ):
        set_auth(test_user)

        # 1. TXT upload
        txt_content = b"Orchestra platform plain text research notes on autonomous multi-agent pipelines."
        r_txt = client.post(
            f"/projects/{test_project.id}/documents",
            files={"file": ("notes.txt", txt_content, "text/plain")},
        )
        assert r_txt.status_code == status.HTTP_201_CREATED
        assert r_txt.json()["status"] == DocumentStatus.INDEXED.value
        assert r_txt.json()["chunk_count"] >= 1

        # 2. Markdown upload
        md_content = b"# Architectural Decisions\n\n- Phase 04 Ingestion\n- Strict tenancy and provenance"
        r_md = client.post(
            f"/projects/{test_project.id}/documents",
            files={"file": ("architecture.md", md_content, "text/markdown")},
        )
        assert r_md.status_code == status.HTTP_201_CREATED
        assert r_md.json()["status"] == DocumentStatus.INDEXED.value
        assert r_md.json()["chunk_count"] >= 1

    def test_pdf_signature_failure_rejected(
        self, client: TestClient, set_auth, test_user: User, test_project: Project
    ):
        set_auth(test_user)
        fake_pdf = b"NOT_A_PDF_STREAM_WITHOUT_MAGIC_BYTES"
        response = client.post(
            f"/projects/{test_project.id}/documents",
            files={"file": ("fake.pdf", fake_pdf, "application/pdf")},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid PDF file signature" in response.json()["detail"]

    def test_text_null_byte_rejected(
        self, client: TestClient, set_auth, test_user: User, test_project: Project
    ):
        set_auth(test_user)
        binary_txt = b"Text with null \x00 byte payload"
        response = client.post(
            f"/projects/{test_project.id}/documents",
            files={"file": ("binary.txt", binary_txt, "text/plain")},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Binary content not allowed" in response.json()["detail"]

    def test_empty_file_rejected(
        self, client: TestClient, set_auth, test_user: User, test_project: Project
    ):
        set_auth(test_user)
        response = client.post(
            f"/projects/{test_project.id}/documents",
            files={"file": ("empty.txt", b"", "text/plain")},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Uploaded file is empty" in response.json()["detail"]

    def test_unsupported_extension_rejected(
        self, client: TestClient, set_auth, test_user: User, test_project: Project
    ):
        set_auth(test_user)
        response = client.post(
            f"/projects/{test_project.id}/documents",
            files={"file": ("script.exe", b"binary", "application/octet-stream")},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Unsupported file extension" in response.json()["detail"]

    def test_oversized_upload_rejected(
        self, client: TestClient, set_auth, test_user: User, test_project: Project, monkeypatch
    ):
        set_auth(test_user)
        monkeypatch.setattr(settings, "max_upload_size_bytes", 50)
        large_bytes = b"This string exceeds the monkeypatched 50 byte upload limit comfortably."

        response = client.post(
            f"/projects/{test_project.id}/documents",
            files={"file": ("large.txt", large_bytes, "text/plain")},
        )
        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        assert "exceeds maximum upload size" in response.json()["detail"]

    def test_duplicate_upload_in_same_project_conflict(
        self, client: TestClient, set_auth, test_user: User, test_project: Project
    ):
        set_auth(test_user)
        content = b"Unique content for duplicate collision test."

        # First upload succeeds
        r1 = client.post(
            f"/projects/{test_project.id}/documents",
            files={"file": ("doc_v1.txt", content, "text/plain")},
        )
        assert r1.status_code == status.HTTP_201_CREATED

        # Second upload with identical content into same project returns 409
        r2 = client.post(
            f"/projects/{test_project.id}/documents",
            files={"file": ("doc_v2.txt", content, "text/plain")},
        )
        assert r2.status_code == status.HTTP_409_CONFLICT
        assert "identical content already exists" in r2.json()["detail"]

    def test_duplicate_upload_across_different_projects_succeeds(
        self,
        client: TestClient,
        set_auth,
        test_user: User,
        test_project: Project,
        test_user_b: User,
        test_project_b: Project,
    ):
        content = b"Cross-project duplicate content that is valid in separate tenant boundaries."

        # User A uploads to Project A
        set_auth(test_user)
        r_a = client.post(
            f"/projects/{test_project.id}/documents",
            files={"file": ("shared.txt", content, "text/plain")},
        )
        assert r_a.status_code == status.HTTP_201_CREATED

        # User B uploads identical content to Project B
        set_auth(test_user_b)
        r_b = client.post(
            f"/projects/{test_project_b.id}/documents",
            files={"file": ("shared.txt", content, "text/plain")},
        )
        assert r_b.status_code == status.HTTP_201_CREATED
        assert r_a.json()["id"] != r_b.json()["id"]

    def test_list_and_get_documents(
        self, client: TestClient, set_auth, test_user: User, test_project: Project
    ):
        set_auth(test_user)

        client.post(
            f"/projects/{test_project.id}/documents",
            files={"file": ("doc1.txt", b"First doc content", "text/plain")},
        )
        client.post(
            f"/projects/{test_project.id}/documents",
            files={"file": ("doc2.txt", b"Second doc content", "text/plain")},
        )

        list_res = client.get(f"/projects/{test_project.id}/documents")
        assert list_res.status_code == status.HTTP_200_OK
        docs = list_res.json()
        assert len(docs) == 2

        # Get detail
        doc_id = docs[0]["id"]
        detail_res = client.get(f"/projects/{test_project.id}/documents/{doc_id}")
        assert detail_res.status_code == status.HTTP_200_OK
        detail = detail_res.json()
        assert detail["id"] == doc_id
        assert detail["status"] == DocumentStatus.INDEXED.value
        assert "chunk_count" in detail

    def test_delete_document_success_and_idempotency(
        self,
        client: TestClient,
        set_auth,
        test_user: User,
        test_project: Project,
        db_session,
        test_storage,
    ):
        set_auth(test_user)

        r = client.post(
            f"/projects/{test_project.id}/documents",
            files={"file": ("delete_me.txt", b"Data to be deleted completely.", "text/plain")},
        )
        doc_id = r.json()["id"]

        doc_record = db_session.query(Document).filter(Document.id == doc_id).first()
        storage_key = doc_record.storage_key
        assert test_storage.exists(storage_key)

        # 1. Delete document
        del_res = client.delete(f"/projects/{test_project.id}/documents/{doc_id}")
        assert del_res.status_code == status.HTTP_204_NO_CONTENT

        # Verify DB row removed
        assert db_session.query(Document).filter(Document.id == doc_id).first() is None
        # Verify storage file deleted
        assert not test_storage.exists(storage_key)

        # 2. Deleting non-existent document yields 404
        del_again = client.delete(f"/projects/{test_project.id}/documents/{doc_id}")
        assert del_again.status_code == status.HTTP_404_NOT_FOUND
