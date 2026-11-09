from typing import Optional
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.orchestrator import get_orchestrator_service
from app.main import app
from app.models.project import Project
from app.models.user import User
from app.orchestrator.classifier import IntentClassifier
from app.orchestrator.direct_qa import DirectQAEngine
from app.orchestrator.schemas import (
    IntentType,
    OrchestratorRequest,
    OrchestratorResponse,
)
from app.orchestrator.service import OrchestratorService
from app.research.llm.mock import DeterministicTestLLMProvider
from app.research.schemas import (
    ResearchMetadata,
    ResearchRequest,
    ResearchResponse,
    ResearchStatus,
)
from app.developer.schemas import (
    DeveloperMode,
    DeveloperRequest,
    DeveloperResponse,
    TaskStatus,
    TaskType,
)


class MockLLM(DeterministicTestLLMProvider):
    def __init__(self, canned_text: str = "Mock answer"):
        super().__init__(mode="normal")
        self.canned_text = canned_text

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.0,
    ) -> str:
        self.call_count += 1
        return self.canned_text


class MockResearchService:
    def __init__(self):
        self.call_count = 0

    async def research(self, project_id: int, request: ResearchRequest) -> ResearchResponse:
        self.call_count += 1
        return ResearchResponse(
            status=ResearchStatus.COMPLETED,
            question=request.question,
            answer="Research findings on transformer attention mechanisms.",
            claims=[],
            citations=[],
            evidence_count=3,
            metadata=ResearchMetadata(
                model="test-model",
                subqueries_executed=[request.question],
                total_evidence_retrieved=3,
                verified_citations_count=0,
                execution_time_ms=12.5,
                llm_call_count=1,
            ),
        )


class MockDeveloperService:
    def __init__(self):
        self.call_count = 0

    async def execute_task(self, project_id: int, request: DeveloperRequest) -> DeveloperResponse:
        self.call_count += 1
        return DeveloperResponse(
            status=TaskStatus.SUCCESS,
            task_type=request.task_type,
            mode=request.mode,
            summary="Refactored module successfully.",
            files_analyzed=["auth.py"],
            proposed_patches=[],
            documentation=None,
            warnings=[],
            tool_events=[],
            metadata={"llm_calls_made": 1},
        )


@pytest.fixture
def mock_orchestrator_service(db_session: Session):
    llm = MockLLM()
    classifier = IntentClassifier(llm_provider=llm)
    direct_qa = DirectQAEngine(llm_provider=llm)
    research_svc = MockResearchService()
    dev_svc = MockDeveloperService()

    service = OrchestratorService(
        db=db_session,
        llm_provider=llm,
        classifier=classifier,
        direct_qa_engine=direct_qa,
        research_service=research_svc,
        developer_service=dev_svc,
    )
    return service, llm, research_svc, dev_svc


class TestOrchestratorAPI:
    def test_unauthenticated_request_rejected(
        self,
        client: TestClient,
        test_project: Project,
    ):
        """Unauthenticated requests must be rejected with 401 Unauthorized."""
        payload = {"prompt": "What is the architecture?"}
        response = client.post(f"/projects/{test_project.id}/orchestrate", json=payload)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_idor_unowned_project_returns_404(
        self,
        client: TestClient,
        set_auth,
        test_user_b: User,
        test_project: Project,
        mock_orchestrator_service,
    ):
        """Accessing a foreign project must return 404 without executing LLM or subgraphs."""
        service, llm, res_svc, dev_svc = mock_orchestrator_service
        app.dependency_overrides[get_orchestrator_service] = lambda: service
        set_auth(test_user_b)

        llm.call_count = 0
        payload = {"prompt": "What is the system design?"}
        response = client.post(f"/projects/{test_project.id}/orchestrate", json=payload)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Project not found"
        # 0 LLM / 0 research / 0 developer calls
        assert llm.call_count == 0
        assert res_svc.call_count == 0
        assert dev_svc.call_count == 0

    def test_mismatched_session_returns_404(
        self,
        client: TestClient,
        set_auth,
        test_user: User,
        test_project: Project,
        mock_orchestrator_service,
    ):
        """Non-existent or cross-project session ID must return 404."""
        service, _, _, _ = mock_orchestrator_service
        app.dependency_overrides[get_orchestrator_service] = lambda: service
        set_auth(test_user)

        payload = {"prompt": "Continue conversation", "session_id": 99999}
        response = client.post(f"/projects/{test_project.id}/orchestrate", json=payload)
        assert response.status_code == status.HTTP_404_NOT_FOUND

        response_path = client.post(f"/projects/{test_project.id}/orchestrate/sessions/99999", json={"prompt": "test"})
        assert response_path.status_code == status.HTTP_404_NOT_FOUND

    def test_viewer_role_cannot_apply_modifications(
        self,
        client: TestClient,
        set_auth,
        test_viewer_user: User,
        test_viewer_project: Project,
        mock_orchestrator_service,
    ):
        """Users with VIEWER role must be forbidden (HTTP 403) from apply mode developer tasks."""
        service, _, _, _ = mock_orchestrator_service
        app.dependency_overrides[get_orchestrator_service] = lambda: service
        set_auth(test_viewer_user)

        payload = {
            "prompt": "Apply bug fix to auth.py",
            "developer_params": {"mode": "apply"},
        }
        response = client.post(f"/projects/{test_viewer_project.id}/orchestrate", json=payload)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "Viewer role is not authorized" in response.json()["detail"]

    def test_viewer_role_can_execute_direct_qa(
        self,
        client: TestClient,
        set_auth,
        test_viewer_user: User,
        test_viewer_project: Project,
        mock_orchestrator_service,
    ):
        """Users with VIEWER role can execute read-only Direct QA or preview."""
        service, _, _, _ = mock_orchestrator_service
        app.dependency_overrides[get_orchestrator_service] = lambda: service
        set_auth(test_viewer_user)

        payload = {"prompt": "What is Python?"}
        response = client.post(f"/projects/{test_viewer_project.id}/orchestrate", json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["intent"] == "direct_qa"
        assert data["answer"] == "Mock answer"

    def test_e2e_research_orchestration(
        self,
        client: TestClient,
        set_auth,
        test_user: User,
        test_project: Project,
        mock_orchestrator_service,
    ):
        """End-to-end research flow via orchestrator endpoint."""
        service, _, res_svc, _ = mock_orchestrator_service
        app.dependency_overrides[get_orchestrator_service] = lambda: service
        set_auth(test_user)

        payload = {
            "prompt": "Search scientific papers and perform literature review on transformer models",
            "research_params": {"response_depth": "detailed"},
        }
        response = client.post(f"/projects/{test_project.id}/orchestrate", json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["intent"] == "research"
        assert res_svc.call_count == 1
        assert data["research_result"] is not None
        assert data["research_result"]["status"] == "completed"
        assert "Research findings" in data["answer"]

    def test_e2e_developer_orchestration(
        self,
        client: TestClient,
        set_auth,
        test_user: User,
        test_project: Project,
        mock_orchestrator_service,
    ):
        """End-to-end developer intelligence flow via orchestrator endpoint."""
        service, _, _, dev_svc = mock_orchestrator_service
        app.dependency_overrides[get_orchestrator_service] = lambda: service
        set_auth(test_user)

        payload = {
            "prompt": "Fix bug and refactor code in auth.py",
            "developer_params": {"task_type": "code_gen", "mode": "preview", "target_files": ["auth.py"]},
        }
        response = client.post(f"/projects/{test_project.id}/orchestrate", json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["intent"] == "developer"
        assert dev_svc.call_count == 1
        assert data["developer_result"] is not None
        assert data["developer_result"]["status"] == "success"
        assert data["answer"] == "Refactored module successfully."

    def test_session_continuation_via_path_param(
        self,
        client: TestClient,
        set_auth,
        test_user: User,
        test_project: Project,
        mock_orchestrator_service,
    ):
        """Multi-turn session continuation via /sessions/{session_id} route."""
        service, _, _, _ = mock_orchestrator_service
        app.dependency_overrides[get_orchestrator_service] = lambda: service
        set_auth(test_user)

        # Turn 1
        resp1 = client.post(
            f"/projects/{test_project.id}/orchestrate",
            json={"prompt": "What is unit testing?"},
        )
        assert resp1.status_code == status.HTTP_200_OK
        sess_id = resp1.json()["session_id"]

        # Turn 2
        resp2 = client.post(
            f"/projects/{test_project.id}/orchestrate/sessions/{sess_id}",
            json={"prompt": "How does pytest work?"},
        )
        assert resp2.status_code == status.HTTP_200_OK
        assert resp2.json()["session_id"] == sess_id

    def test_timeout_error_maps_to_504(
        self,
        client: TestClient,
        set_auth,
        test_user: User,
        test_project: Project,
        db_session: Session,
    ):
        """TimeoutError during orchestration must be mapped to 504 Gateway Timeout."""
        class TimingOutService(OrchestratorService):
            async def orchestrate(self, *args, **kwargs):
                raise TimeoutError("Execution exceeded deadline")

        timeout_svc = TimingOutService(db=db_session)
        app.dependency_overrides[get_orchestrator_service] = lambda: timeout_svc
        set_auth(test_user)

        response = client.post(
            f"/projects/{test_project.id}/orchestrate",
            json={"prompt": "Trigger timeout"},
        )
        assert response.status_code == status.HTTP_504_GATEWAY_TIMEOUT
        assert "timed out" in response.json()["detail"].lower()
