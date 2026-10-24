import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import Settings


def test_app_import_pure():
    """Verify that app initializes with expected metadata and routes."""
    assert app.title == "Orchestra"
    paths = [route.path for route in app.routes if hasattr(route, "path")]
    assert "/" in paths
    assert "/health" in paths
    assert "/health/database" in paths


def test_health_endpoints():
    """Verify that health endpoints return standard JSON responses without database connection."""
    client = TestClient(app)
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "healthy"}

    res_db = client.get("/health/database")
    assert res_db.status_code == 200
    data = res_db.json()
    assert "status" in data
    assert "database" in data


def test_config_validation_missing_secrets():
    """Verify that Settings.validate_runtime_requirements fails fast when secrets are absent."""
    s = Settings(database_url=None, jwt_secret=None)
    with pytest.raises(RuntimeError) as exc_info:
        s.validate_runtime_requirements()
    assert "Missing required environment configuration" in str(exc_info.value)
    assert "DATABASE_URL" in str(exc_info.value)
    assert "JWT_SECRET" in str(exc_info.value)
