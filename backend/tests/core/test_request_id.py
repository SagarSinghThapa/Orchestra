import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.context import get_request_id, request_id_ctx
from app.core.middleware import RequestIDMiddleware


@pytest.fixture
def app_with_request_id():
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/success")
    def success():
        return {"status": "ok", "context_id": get_request_id()}

    @app.get("/error-400")
    def error_400():
        raise HTTPException(status_code=400, detail="Bad input")

    @app.get("/error-401")
    def error_401():
        raise HTTPException(status_code=401, detail="Unauthorized")

    @app.get("/error-403")
    def error_403():
        raise HTTPException(status_code=403, detail="Forbidden")

    @app.get("/error-500")
    def error_500():
        raise RuntimeError("Simulated crash")

    return app


def test_generated_request_id(app_with_request_id):
    client = TestClient(app_with_request_id, raise_server_exceptions=False)
    resp = client.get("/success")
    assert resp.status_code == 200
    assert "X-Request-ID" in resp.headers
    req_id = resp.headers["X-Request-ID"]
    assert req_id.startswith("req_")
    assert resp.json()["context_id"] == req_id


def test_custom_valid_request_id(app_with_request_id):
    client = TestClient(app_with_request_id, raise_server_exceptions=False)
    custom_id = "trace-client-12345_abc"
    resp = client.get("/success", headers={"X-Request-ID": custom_id})
    assert resp.status_code == 200
    assert resp.headers["X-Request-ID"] == custom_id
    assert resp.json()["context_id"] == custom_id


def test_malformed_request_id_replaced(app_with_request_id):
    client = TestClient(app_with_request_id, raise_server_exceptions=False)
    malformed_id = "bad id with spaces and <script>"
    resp = client.get("/success", headers={"X-Request-ID": malformed_id})
    assert resp.status_code == 200
    # Must NOT use the malformed header
    returned_id = resp.headers["X-Request-ID"]
    assert returned_id != malformed_id
    assert returned_id.startswith("req_")
    assert " " not in returned_id


def test_oversized_request_id_replaced(app_with_request_id):
    client = TestClient(app_with_request_id, raise_server_exceptions=False)
    oversized_id = "a" * 65
    resp = client.get("/success", headers={"X-Request-ID": oversized_id})
    assert resp.status_code == 200
    returned_id = resp.headers["X-Request-ID"]
    assert returned_id != oversized_id
    assert returned_id.startswith("req_")


def test_request_id_on_error_responses(app_with_request_id):
    client = TestClient(app_with_request_id, raise_server_exceptions=False)

    for path in ["/error-400", "/error-401", "/error-403", "/error-500", "/non-existent"]:
        resp = client.get(path)
        assert "X-Request-ID" in resp.headers, f"Missing X-Request-ID on {path}"
        assert resp.headers["X-Request-ID"].startswith("req_")


def test_contextvar_clean_reset(app_with_request_id):
    client = TestClient(app_with_request_id, raise_server_exceptions=False)
    # Outside request, context must be empty
    assert request_id_ctx.get() == ""
    assert get_request_id() == "req_untracked"

    resp = client.get("/success")
    assert resp.status_code == 200

    # After request completes, context variable MUST be reset to default
    assert request_id_ctx.get() == ""
    assert get_request_id() == "req_untracked"
