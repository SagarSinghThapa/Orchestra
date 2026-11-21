import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.models.document import Document
from app.models.project import Project
from app.models.user import User


class TestDocumentIDORIsolation:
    def test_cross_tenant_idor_endpoints_return_404(
        self,
        client: TestClient,
        set_auth,
        test_user: User,
        test_project: Project,
        test_user_b: User,
        test_project_b: Project,
        db_session,
    ):
        """
        Empirically verifies that User B cannot access, list, view, mutate, reindex,
        or delete User A's documents under Project A. Every attempt returns HTTP 404.
        """
        # User A creates a document in Project A
        set_auth(test_user)
        r = client.post(
            f"/projects/{test_project.id}/documents",
            files={"file": ("confidential.txt", b"Confidential research for User A", "text/plain")},
        )
        assert r.status_code == status.HTTP_201_CREATED
        doc_a_id = r.json()["id"]

        # Now authenticate as User B (attacker)
        set_auth(test_user_b)

        # 1. Attacker attempts to upload into Project A
        r_upload = client.post(
            f"/projects/{test_project.id}/documents",
            files={"file": ("malicious.txt", b"Injected data", "text/plain")},
        )
        assert r_upload.status_code == status.HTTP_404_NOT_FOUND
        assert r_upload.json()["detail"] == "Project not found"

        # 2. Attacker attempts to list Project A's documents
        r_list = client.get(f"/projects/{test_project.id}/documents")
        assert r_list.status_code == status.HTTP_404_NOT_FOUND
        assert r_list.json()["detail"] == "Project not found"

        # 3. Attacker attempts to retrieve User A's document details directly
        r_get = client.get(f"/projects/{test_project.id}/documents/{doc_a_id}")
        assert r_get.status_code == status.HTTP_404_NOT_FOUND
        assert r_get.json()["detail"] == "Project not found"

        # 4. Attacker attempts to reindex User A's document
        r_reindex = client.post(f"/projects/{test_project.id}/documents/{doc_a_id}/reindex")
        assert r_reindex.status_code == status.HTTP_404_NOT_FOUND
        assert r_reindex.json()["detail"] == "Project not found"

        # 5. Attacker attempts to delete User A's document
        r_del = client.delete(f"/projects/{test_project.id}/documents/{doc_a_id}")
        assert r_del.status_code == status.HTTP_404_NOT_FOUND
        assert r_del.json()["detail"] == "Project not found"

        # 6. Attacker attempts IDOR passing their own project with User A's document ID
        r_cross = client.get(f"/projects/{test_project_b.id}/documents/{doc_a_id}")
        assert r_cross.status_code == status.HTTP_404_NOT_FOUND
        assert r_cross.json()["detail"] == "Document not found"

        # 7. Verify User A's document in database is completely untouched
        doc_in_db = db_session.query(Document).filter(Document.id == doc_a_id).first()
        assert doc_in_db is not None
        assert doc_in_db.original_filename == "confidential.txt"
        assert doc_in_db.project_id == test_project.id
