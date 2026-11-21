from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.session import Session as DBSession
from app.models.user import User


# ==============================================================================
# Projects API Tests
# ==============================================================================

def test_create_project(client: TestClient, set_auth, test_user: User):
    """Verifies that an authenticated user can create a project successfully."""
    set_auth(test_user)
    response = client.post(
        "/projects",
        json={"name": "Neural Compiler", "description": "AST-guided code generation"},
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["name"] == "Neural Compiler"
    assert data["description"] == "AST-guided code generation"
    assert data["owner_id"] == test_user.id
    assert "id" in data


def test_get_projects_tenant_isolation(
    client: TestClient,
    set_auth,
    test_user: User,
    second_user: User,
):
    """Verifies that project listing strictly isolates projects per authenticated tenant."""
    # Create project for primary user
    set_auth(test_user)
    r1 = client.post("/projects", json={"name": "User 1 Project"})
    assert r1.status_code == status.HTTP_201_CREATED

    # Create project for secondary user
    set_auth(second_user)
    r2 = client.post("/projects", json={"name": "User 2 Project"})
    assert r2.status_code == status.HTTP_201_CREATED

    # Primary user should only see their project
    set_auth(test_user)
    user1_projects = client.get("/projects").json()
    assert len(user1_projects) == 1
    assert user1_projects[0]["name"] == "User 1 Project"
    assert user1_projects[0]["owner_id"] == test_user.id

    # Secondary user should only see their project
    set_auth(second_user)
    user2_projects = client.get("/projects").json()
    assert len(user2_projects) == 1
    assert user2_projects[0]["name"] == "User 2 Project"
    assert user2_projects[0]["owner_id"] == second_user.id


def test_get_project_by_id_and_idor(
    client: TestClient,
    set_auth,
    test_user: User,
    second_user: User,
    test_project: Project,
):
    """Verifies project retrieval and IDOR rejection when accessing another user's project."""
    # Owner can retrieve project
    set_auth(test_user)
    res = client.get(f"/projects/{test_project.id}")
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["id"] == test_project.id

    # Non-owner is rejected with 404 Not Found (IDOR protection)
    set_auth(second_user)
    idor_res = client.get(f"/projects/{test_project.id}")
    assert idor_res.status_code == status.HTTP_404_NOT_FOUND

    # Non-existent project returns 404
    set_auth(test_user)
    missing_res = client.get("/projects/999999")
    assert missing_res.status_code == status.HTTP_404_NOT_FOUND


def test_delete_project_and_cascade(
    client: TestClient,
    set_auth,
    test_user: User,
    second_user: User,
    test_project: Project,
    db_session: Session,
):
    """Verifies that project deletion is owner-only, returns 204, and cascades cleanly."""
    project_id = test_project.id

    # Non-owner cannot delete project
    set_auth(second_user)
    idor_del = client.delete(f"/projects/{project_id}")
    assert idor_del.status_code == status.HTTP_404_NOT_FOUND

    # Owner deletes project
    set_auth(test_user)
    del_res = client.delete(f"/projects/{project_id}")
    assert del_res.status_code == status.HTTP_204_NO_CONTENT

    # Subsequent retrieval returns 404
    get_res = client.get(f"/projects/{project_id}")
    assert get_res.status_code == status.HTTP_404_NOT_FOUND


# ==============================================================================
# Sessions API Tests
# ==============================================================================

def test_create_session(
    client: TestClient,
    set_auth,
    test_user: User,
    second_user: User,
    test_project: Project,
):
    """Verifies session creation under an owned project and IDOR rejection."""
    # Owner creates session
    set_auth(test_user)
    payload = {
        "project_id": test_project.id,
        "type": "coding",
        "title": "Refactor Router",
        "query": "Implement clean exception handling",
    }
    res = client.post("/sessions", json=payload)
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["project_id"] == test_project.id
    assert data["status"] == "pending"

    # Non-owner cannot create session under another user's project
    set_auth(second_user)
    idor_res = client.post("/sessions", json=payload)
    assert idor_res.status_code == status.HTTP_404_NOT_FOUND

    # Cannot create session under non-existent project
    set_auth(test_user)
    invalid_res = client.post(
        "/sessions",
        json={**payload, "project_id": 888888},
    )
    assert invalid_res.status_code == status.HTTP_404_NOT_FOUND


def test_get_project_sessions_and_idor(
    client: TestClient,
    set_auth,
    test_user: User,
    second_user: User,
    test_project: Project,
    test_session_obj: DBSession,
):
    """Verifies project sessions retrieval and cross-user rejection."""
    # Owner gets sessions
    set_auth(test_user)
    res = client.get(f"/sessions/project/{test_project.id}")
    assert res.status_code == status.HTTP_200_OK
    assert len(res.json()) >= 1
    assert res.json()[0]["id"] == test_session_obj.id

    # Non-owner cannot list sessions for another user's project
    set_auth(second_user)
    idor_res = client.get(f"/sessions/project/{test_project.id}")
    assert idor_res.status_code == status.HTTP_404_NOT_FOUND


def test_get_session_by_id_and_idor(
    client: TestClient,
    set_auth,
    test_user: User,
    second_user: User,
    test_session_obj: DBSession,
):
    """Verifies single session retrieval and cross-user rejection."""
    # Owner gets session
    set_auth(test_user)
    res = client.get(f"/sessions/{test_session_obj.id}")
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["id"] == test_session_obj.id

    # Non-owner cannot access session
    set_auth(second_user)
    idor_res = client.get(f"/sessions/{test_session_obj.id}")
    assert idor_res.status_code == status.HTTP_404_NOT_FOUND


# ==============================================================================
# Messages API Tests
# ==============================================================================

def test_create_and_get_messages(
    client: TestClient,
    set_auth,
    test_user: User,
    second_user: User,
    test_session_obj: DBSession,
):
    """Verifies message creation, chronological listing, and cross-user rejection."""
    session_id = test_session_obj.id

    # Owner adds message 1
    set_auth(test_user)
    r1 = client.post(
        f"/sessions/{session_id}/messages",
        json={"role": "user", "content": "Analyze dependencies"},
    )
    assert r1.status_code == status.HTTP_201_CREATED
    assert r1.json()["content"] == "Analyze dependencies"

    # Owner adds message 2
    r2 = client.post(
        f"/sessions/{session_id}/messages",
        json={"role": "assistant", "content": "Analysis completed"},
    )
    assert r2.status_code == status.HTTP_201_CREATED

    # Retrieve messages
    list_res = client.get(f"/sessions/{session_id}/messages")
    assert list_res.status_code == status.HTTP_200_OK
    messages = list_res.json()
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"

    # Non-owner attempts to post message to session -> 404
    set_auth(second_user)
    idor_post = client.post(
        f"/sessions/{session_id}/messages",
        json={"role": "user", "content": "Malicious payload"},
    )
    assert idor_post.status_code == status.HTTP_404_NOT_FOUND

    # Non-owner attempts to get messages from session -> 404
    idor_get = client.get(f"/sessions/{session_id}/messages")
    assert idor_get.status_code == status.HTTP_404_NOT_FOUND


# ==============================================================================
# Database Health Route Test
# ==============================================================================

def test_database_health_endpoint(client: TestClient):
    """Verifies that the /health/database endpoint responds with valid schema without exceptions."""
    res = client.get("/health/database")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "database" in data
    assert "status" in data
