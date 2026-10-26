import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.models.project import Project
from app.models.user import User


class TestSearchAPI:
    def test_search_hybrid_success(
        self,
        client: TestClient,
        set_auth,
        test_user: User,
        test_project: Project,
    ):
        set_auth(test_user)

        # 1. Ingest a document
        doc_content = (
            b"Quantum computing algorithms utilize quantum superposition and entanglement. "
            b"Shor's algorithm can factor integers in polynomial time. "
            b"Grover's algorithm provides quadratic speedup for unstructured database searches."
        )
        r_upload = client.post(
            f"/projects/{test_project.id}/documents",
            files={"file": ("quantum_research.txt", doc_content, "text/plain")},
        )
        assert r_upload.status_code == status.HTTP_201_CREATED
        doc_id = r_upload.json()["id"]

        # 2. Search using hybrid mode
        search_payload = {
            "query": "quantum computing algorithms",
            "limit": 5,
            "mode": "hybrid",
            "dense_weight": 1.0,
            "sparse_weight": 1.0,
        }
        r_search = client.post(
            f"/projects/{test_project.id}/search",
            json=search_payload,
        )
        assert r_search.status_code == status.HTTP_200_OK
        data = r_search.json()
        assert data["query"] == "quantum computing algorithms"
        assert data["mode"] == "hybrid"
        assert data["total_results"] >= 1

        top_result = data["results"][0]
        assert top_result["document_id"] == doc_id
        assert top_result["document_filename"] == "quantum_research.txt"
        assert top_result["page_number"] == 1
        assert "evidence_id" in top_result
        assert top_result["evidence_id"].startswith(f"cite_{doc_id}_")
        assert top_result["start_char"] >= 0
        assert top_result["end_char"] > top_result["start_char"]
        assert "quantum" in top_result["text"].lower()

    def test_search_dense_mode(
        self,
        client: TestClient,
        set_auth,
        test_user: User,
        test_project: Project,
    ):
        set_auth(test_user)
        # Ingest a document
        doc_content = b"Quantum physics principles including superposition and entanglement."
        r_upload = client.post(
            f"/projects/{test_project.id}/documents",
            files={"file": ("quantum_dense.txt", doc_content, "text/plain")},
        )
        assert r_upload.status_code == status.HTTP_201_CREATED

        r_search = client.post(
            f"/projects/{test_project.id}/search",
            json={"query": "superposition entanglement", "mode": "dense", "limit": 3},
        )
        assert r_search.status_code == status.HTTP_200_OK
        data = r_search.json()
        assert data["mode"] == "dense"
        assert data["total_results"] >= 1

    def test_search_sparse_mode(
        self,
        client: TestClient,
        set_auth,
        test_user: User,
        test_project: Project,
    ):
        set_auth(test_user)
        # Ingest a document
        doc_content = b"Grover quadratic speedup for unstructured database searches."
        r_upload = client.post(
            f"/projects/{test_project.id}/documents",
            files={"file": ("quantum_sparse.txt", doc_content, "text/plain")},
        )
        assert r_upload.status_code == status.HTTP_201_CREATED

        # Search for exact keyword
        r_search = client.post(
            f"/projects/{test_project.id}/search",
            json={"query": "Grover quadratic speedup", "mode": "sparse", "limit": 3},
        )
        assert r_search.status_code == status.HTTP_200_OK
        data = r_search.json()
        assert data["mode"] == "sparse"
        assert data["total_results"] >= 1
        assert "grover" in data["results"][0]["text"].lower()

    def test_search_cross_tenant_idor_rejected(
        self,
        client: TestClient,
        set_auth,
        test_user: User,
        test_project: Project,
        test_user_b: User,
    ):
        # Authenticate as User B (attacker)
        set_auth(test_user_b)

        # Attacker tries to search User A's Project
        r = client.post(
            f"/projects/{test_project.id}/search",
            json={"query": "quantum computing", "limit": 5},
        )
        # Must return 404 Not Found to prevent existence leakage
        assert r.status_code == status.HTTP_404_NOT_FOUND
        assert r.json()["detail"] == "Project not found"

    def test_search_empty_or_whitespace_query_rejected(
        self,
        client: TestClient,
        set_auth,
        test_user: User,
        test_project: Project,
    ):
        set_auth(test_user)

        # Empty string
        r1 = client.post(
            f"/projects/{test_project.id}/search",
            json={"query": ""},
        )
        assert r1.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY)

        # Whitespace-only string
        r2 = client.post(
            f"/projects/{test_project.id}/search",
            json={"query": "     \n\t  "},
        )
        assert r2.status_code == status.HTTP_400_BAD_REQUEST

    def test_search_oversized_query_rejected(
        self,
        client: TestClient,
        set_auth,
        test_user: User,
        test_project: Project,
    ):
        set_auth(test_user)
        oversized = "a" * 1001
        r = client.post(
            f"/projects/{test_project.id}/search",
            json={"query": oversized},
        )
        assert r.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_search_document_id_filtering(
        self,
        client: TestClient,
        set_auth,
        test_user: User,
        test_project: Project,
    ):
        set_auth(test_user)

        # Upload Doc A
        r_a = client.post(
            f"/projects/{test_project.id}/documents",
            files={"file": ("doc_alpha.txt", b"Alpha document regarding aerospace dynamics", "text/plain")},
        )
        doc_a_id = r_a.json()["id"]

        # Upload Doc B
        r_b = client.post(
            f"/projects/{test_project.id}/documents",
            files={"file": ("doc_beta.txt", b"Beta document regarding deep sea robotics", "text/plain")},
        )
        doc_b_id = r_b.json()["id"]

        # Search filtered only to Doc A
        r_search = client.post(
            f"/projects/{test_project.id}/search",
            json={
                "query": "document dynamics robotics",
                "document_ids": [doc_a_id],
                "limit": 5,
            },
        )
        assert r_search.status_code == status.HTTP_200_OK
        results = r_search.json()["results"]
        assert len(results) > 0
        assert all(res["document_id"] == doc_a_id for res in results)
        assert all(res["document_filename"] == "doc_alpha.txt" for res in results)

    def test_search_unauthenticated_rejected(
        self,
        client: TestClient,
        test_project: Project,
    ):
        # No set_auth call (anonymous request)
        r = client.post(
            f"/projects/{test_project.id}/search",
            json={"query": "test query"},
        )
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_search_empty_project_returns_empty_results(
        self,
        client: TestClient,
        set_auth,
        test_user: User,
        test_project_b: Project,
    ):
        set_auth(test_user)
        # test_project_b belongs to test_user_b normally, but let's test a clean project owned by user
        # create new project for test_user
        r_create = client.post("/projects", json={"name": "Empty Project", "description": "No docs"})
        assert r_create.status_code == status.HTTP_201_CREATED
        empty_proj_id = r_create.json()["id"]

        r_search = client.post(
            f"/projects/{empty_proj_id}/search",
            json={"query": "anything at all"},
        )
        assert r_search.status_code == status.HTTP_200_OK
        data = r_search.json()
        assert data["total_results"] == 0
        assert data["results"] == []

    def test_search_deleted_document_not_returned(
        self,
        client: TestClient,
        set_auth,
        test_user: User,
        test_project: Project,
    ):
        set_auth(test_user)

        # Upload ephemeral document
        r_upload = client.post(
            f"/projects/{test_project.id}/documents",
            files={"file": ("ephemeral.txt", b"UniqueTransientKeywordForDeletionTest", "text/plain")},
        )
        doc_id = r_upload.json()["id"]

        # Verify it can be found
        r_before = client.post(
            f"/projects/{test_project.id}/search",
            json={"query": "UniqueTransientKeywordForDeletionTest", "mode": "sparse"},
        )
        assert r_before.status_code == status.HTTP_200_OK
        assert r_before.json()["total_results"] >= 1

        # Delete document
        r_del = client.delete(f"/projects/{test_project.id}/documents/{doc_id}")
        assert r_del.status_code == status.HTTP_204_NO_CONTENT

        # Verify it is no longer returned
        r_after = client.post(
            f"/projects/{test_project.id}/search",
            json={"query": "UniqueTransientKeywordForDeletionTest", "mode": "sparse"},
        )
        assert r_after.status_code == status.HTTP_200_OK
        assert r_after.json()["total_results"] == 0
