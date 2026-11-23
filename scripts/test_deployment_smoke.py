#!/usr/bin/env python3
"""
Automated Deployment Smoke Verification Runner for Orchestra.
Executes end-to-end black-box integration stages against the live containerized stack
probing the public Nginx entry point (default http://127.0.0.1:8080).

Verification stages:
1. Health check: GET /health -> 200 OK
2. Readiness check: GET /health/ready -> 200 OK (all dependencies healthy)
3. Metrics privacy check: GET /metrics -> 404 Not Found (blocked by reverse proxy)
4. Auth flow: registers new user, logs in, obtains session cookie and JWT
5. Tenancy: creates project workspace 'Project Alpha'
6. Ingestion: uploads Markdown document fixture via POST /projects/{id}/documents
7. Research: submits grounded research query and verifies verified citations
8. Developer: previews developer task diff in isolated workspace via POST /projects/{id}/developer
9. Teardown: deletes project workspace cleanly and asserts 404
"""

import os
import sys
import time
import uuid
import httpx


def log_stage(stage_num: int, name: str, passed: bool, detail: str = ""):
    status_tag = "[PASS]" if passed else "[FAIL]"
    print(f"Stage {stage_num:02d}: {status_tag} - {name} {f'({detail})' if detail else ''}")


def run_deployment_smoke():
    base_url = os.getenv("ORCHESTRA_URL", f"http://127.0.0.1:{os.getenv('ORCHESTRA_PORT', '8080')}")
    print(f"=== Orchestra Deployment Smoke Verification ===")
    print(f"Target URL: {base_url}")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    print("=" * 48)

    client = httpx.Client(base_url=base_url, timeout=30.0)
    failed_stages = []

    try:
        # Stage 1: Health Check
        try:
            r = client.get("/health")
            assert r.status_code == 200, f"Expected HTTP 200, got {r.status_code}"
            body = r.json()
            assert body.get("status") == "healthy", f"Expected status 'healthy', got {body.get('status')}"
            log_stage(1, "Public Health Endpoint", True, "200 OK, status: healthy")
        except Exception as exc:
            log_stage(1, "Public Health Endpoint", False, str(exc))
            failed_stages.append(1)

        # Stage 2: Readiness Check
        try:
            r = client.get("/health/ready")
            assert r.status_code == 200, f"Expected HTTP 200, got {r.status_code}"
            body = r.json()
            deps = body.get("dependencies", {})
            assert deps.get("database") == "healthy", f"Database dependency unhealthy: {deps.get('database')}"
            assert deps.get("redis") == "healthy", f"Redis dependency unhealthy: {deps.get('redis')}"
            assert deps.get("qdrant") == "healthy", f"Qdrant dependency unhealthy: {deps.get('qdrant')}"
            log_stage(2, "Multi-Dependency Readiness Probe", True, "DB, Redis, Qdrant all healthy")
        except Exception as exc:
            log_stage(2, "Multi-Dependency Readiness Probe", False, str(exc))
            failed_stages.append(2)

        # Stage 3: Metrics Privacy Check
        try:
            r = client.get("/metrics")
            assert r.status_code == 404, f"Expected HTTP 404 for blocked /metrics, got {r.status_code}"
            log_stage(3, "Internal Metrics Access Isolation", True, "404 Not Found (blocked by proxy)")
        except Exception as exc:
            log_stage(3, "Internal Metrics Access Isolation", False, str(exc))
            failed_stages.append(3)

        # Stage 4: Auth Flow (Registration & Login)
        user_email = f"smoke_runner_{uuid.uuid4().hex[:8]}@example.com"
        user_password = "SmokeTestSecurePassword2026!"
        auth_headers = {}
        try:
            r_reg = client.post("/auth/register", json={"email": user_email, "password": user_password})
            assert r_reg.status_code == 201, f"Register failed: HTTP {r_reg.status_code}: {r_reg.text}"

            r_login = client.post("/auth/login", json={"email": user_email, "password": user_password})
            assert r_login.status_code == 200, f"Login failed: HTTP {r_login.status_code}: {r_login.text}"
            tokens = r_login.json()
            access_token = tokens.get("access_token")
            assert access_token, "Missing access_token in login response"
            auth_headers = {"Authorization": f"Bearer {access_token}"}
            # Verify session cookies present
            assert "access_token" in r_login.cookies, "Missing access_token cookie"
            log_stage(4, "End-to-End Authentication Flow", True, f"Registered & logged in as {user_email}")
        except Exception as exc:
            log_stage(4, "End-to-End Authentication Flow", False, str(exc))
            failed_stages.append(4)

        # Stage 5: Tenancy / Project Workspace Creation
        project_id = None
        try:
            r_proj = client.post(
                "/projects",
                json={"name": "Project Alpha", "description": "Automated deployment smoke test workspace"},
                headers=auth_headers,
            )
            assert r_proj.status_code == 201, f"Project creation failed: HTTP {r_proj.status_code}: {r_proj.text}"
            proj_data = r_proj.json()
            project_id = proj_data["id"]
            assert proj_data["name"] == "Project Alpha"
            log_stage(5, "Tenant Project Workspace Creation", True, f"Created project ID {project_id}")
        except Exception as exc:
            log_stage(5, "Tenant Project Workspace Creation", False, str(exc))
            failed_stages.append(5)

        # Stage 6: Document Ingestion Pipeline
        doc_id = None
        if project_id:
            try:
                markdown_fixture = (
                    b"# Orchestra Architecture Specification\n\n"
                    b"The Orchestra platform provides multi-agent developer intelligence.\n"
                    b"Services run containerized across PostgreSQL 16, Redis 7, and Qdrant 1.12.\n"
                    b"All communications route through the unprivileged Nginx reverse proxy on port 8080.\n"
                )
                r_upload = client.post(
                    f"/projects/{project_id}/documents",
                    files={"file": ("architecture_spec.md", markdown_fixture, "text/markdown")},
                    headers=auth_headers,
                )
                assert r_upload.status_code == 201, f"Upload failed: HTTP {r_upload.status_code}: {r_upload.text}"
                doc_data = r_upload.json()
                doc_id = doc_data["id"]
                assert doc_data["status"] == "indexed", f"Expected status 'indexed', got {doc_data['status']}"
                assert doc_data["chunk_count"] > 0, "Expected at least 1 indexed chunk"
                log_stage(6, "Document Ingestion & Dense Indexing", True, f"Indexed doc ID {doc_id} with {doc_data['chunk_count']} chunks")
            except Exception as exc:
                log_stage(6, "Document Ingestion & Dense Indexing", False, str(exc))
                failed_stages.append(6)
        else:
            log_stage(6, "Document Ingestion & Dense Indexing", False, "Skipped due to project creation failure")
            failed_stages.append(6)

        # Stage 7: Grounded Research Workflow
        if project_id:
            try:
                r_research = client.post(
                    f"/projects/{project_id}/research",
                    json={"question": "What services does the Orchestra platform run?"},
                    headers=auth_headers,
                )
                assert r_research.status_code == 200, f"Research failed: HTTP {r_research.status_code}: {r_research.text}"
                res_data = r_research.json()
                assert res_data.get("status") == "completed", f"Expected completed research status, got {res_data.get('status')}"
                assert len(res_data.get("citations", [])) > 0, "Expected at least one verified citation"
                log_stage(7, "Grounded Research & Citation Verification", True, f"Answer synthesized with {len(res_data.get('citations', []))} citations")
            except Exception as exc:
                log_stage(7, "Grounded Research & Citation Verification", False, str(exc))
                failed_stages.append(7)
        else:
            log_stage(7, "Grounded Research & Citation Verification", False, "Skipped due to project creation failure")
            failed_stages.append(7)

        # Stage 8: Developer Subgraph Diff Preview
        if project_id:
            try:
                r_dev = client.post(
                    f"/projects/{project_id}/developer",
                    json={
                        "task_type": "repo_analysis",
                        "prompt": "Analyze project architecture and workspace boundaries.",
                        "mode": "preview",
                    },
                    headers=auth_headers,
                )
                assert r_dev.status_code == 200, f"Developer task failed: HTTP {r_dev.status_code}: {r_dev.text}"
                dev_data = r_dev.json()
                assert dev_data.get("status") == "success", f"Expected developer task success, got {dev_data.get('status')}"
                log_stage(8, "Developer Intelligence Preview", True, f"Task status: {dev_data.get('status')}")
            except Exception as exc:
                log_stage(8, "Developer Intelligence Preview", False, str(exc))
                failed_stages.append(8)
        else:
            log_stage(8, "Developer Intelligence Preview", False, "Skipped due to project creation failure")
            failed_stages.append(8)

        # Stage 9: Tenancy Teardown
        if project_id:
            try:
                r_del = client.delete(f"/projects/{project_id}", headers=auth_headers)
                assert r_del.status_code in (200, 204), f"Delete project failed: HTTP {r_del.status_code}"

                # Verify clean 404 post-deletion
                r_check = client.get(f"/projects/{project_id}", headers=auth_headers)
                assert r_check.status_code == 404, f"Expected 404 after deletion, got {r_check.status_code}"
                log_stage(9, "Tenant Workspace Teardown", True, f"Project {project_id} deleted and verified 404")
            except Exception as exc:
                log_stage(9, "Tenant Workspace Teardown", False, str(exc))
                failed_stages.append(9)
        else:
            log_stage(9, "Tenant Workspace Teardown", False, "Skipped due to project creation failure")
            failed_stages.append(9)

    finally:
        client.close()

    print("=" * 48)
    if not failed_stages:
        print("RESULT: ALL 9 DEPLOYMENT SMOKE STAGES PASSED (0 FAILURES)")
        return 0
    else:
        print(f"RESULT: {len(failed_stages)} STAGE(S) FAILED: {failed_stages}")
        return 1


if __name__ == "__main__":
    sys.exit(run_deployment_smoke())
