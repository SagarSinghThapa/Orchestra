"""
Role-Based Access Control (RBAC) tests validating semantic permissions and ownership isolation.
"""

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient

from app.auth.dependencies import require_role
from app.auth.jwt import create_access_token
from app.main import app
from app.models.user import User, UserRole


# Define test router protected by require_role
rbac_test_router = APIRouter(prefix="/test-rbac", tags=["RBAC Test"])


@rbac_test_router.get("/admin-only")
def admin_only_endpoint(current_user: User = Depends(require_role(UserRole.ADMIN.value))):
    return {"message": "Admin access granted", "user_id": current_user.id}


@rbac_test_router.get("/member-or-admin")
def member_or_admin_endpoint(
    current_user: User = Depends(require_role(UserRole.MEMBER.value, UserRole.ADMIN.value))
):
    return {"message": "Member/Admin access granted", "user_id": current_user.id}


@rbac_test_router.get("/viewer-allowed")
def viewer_allowed_endpoint(
    current_user: User = Depends(
        require_role(UserRole.VIEWER.value, UserRole.MEMBER.value, UserRole.ADMIN.value)
    )
):
    return {"message": "Viewer access granted", "user_id": current_user.id}


# Register router once on app
if not any(getattr(r, "path", None) == "/test-rbac/admin-only" for r in app.routes):
    app.include_router(rbac_test_router)


def test_admin_user_has_full_access(client: TestClient, admin_user: User):
    """Admin user is permitted on admin-only, member-or-admin, and viewer-allowed endpoints."""
    token = create_access_token(admin_user.id, role=admin_user.role)
    headers = {"Authorization": f"Bearer {token}"}

    res_admin = client.get("/test-rbac/admin-only", headers=headers)
    assert res_admin.status_code == 200

    res_member = client.get("/test-rbac/member-or-admin", headers=headers)
    assert res_member.status_code == 200

    res_viewer = client.get("/test-rbac/viewer-allowed", headers=headers)
    assert res_viewer.status_code == 200


def test_member_user_access_boundaries(client: TestClient, member_user: User):
    """Member user is permitted on member-or-admin, but gets 403 Forbidden on admin-only."""
    token = create_access_token(member_user.id, role=member_user.role)
    headers = {"Authorization": f"Bearer {token}"}

    # Forbidden on admin-only
    res_admin = client.get("/test-rbac/admin-only", headers=headers)
    assert res_admin.status_code == 403
    assert res_admin.json()["detail"] == "Insufficient permissions"

    # Allowed on member-or-admin
    res_member = client.get("/test-rbac/member-or-admin", headers=headers)
    assert res_member.status_code == 200

    # Allowed on viewer-allowed
    res_viewer = client.get("/test-rbac/viewer-allowed", headers=headers)
    assert res_viewer.status_code == 200


def test_viewer_user_access_boundaries(client: TestClient, viewer_user: User):
    """Viewer user is forbidden on admin and member endpoints, permitted only on viewer endpoints."""
    token = create_access_token(viewer_user.id, role=viewer_user.role)
    headers = {"Authorization": f"Bearer {token}"}

    res_admin = client.get("/test-rbac/admin-only", headers=headers)
    assert res_admin.status_code == 403
    assert res_admin.json()["detail"] == "Insufficient permissions"

    res_member = client.get("/test-rbac/member-or-admin", headers=headers)
    assert res_member.status_code == 403
    assert res_member.json()["detail"] == "Insufficient permissions"

    res_viewer = client.get("/test-rbac/viewer-allowed", headers=headers)
    assert res_viewer.status_code == 200


def test_unauthenticated_request_returns_401_not_403(client: TestClient):
    """Unauthenticated request must return 401 Unauthorized, NOT 403 Forbidden."""
    client.cookies.clear()
    res = client.get("/test-rbac/admin-only")
    assert res.status_code == 401
