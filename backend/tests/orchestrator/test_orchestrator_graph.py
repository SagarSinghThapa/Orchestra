import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.models.user import User, UserRole
from app.models.project import Project
from app.models.session import Session as SessionModel
from app.models.message import Message as MessageModel
from app.core.checkpoints import PostgresSaver
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
    def __init__(self, canned_text: str = "Mock answer", structured_res: Any = None):
        super().__init__(mode="normal")
        self.canned_text = canned_text
        self.structured_res = structured_res

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.0,
    ) -> str:
        self.call_count += 1
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt
        return self.canned_text

    async def generate_structured(
        self,
        prompt: str,
        schema: Any,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.0,
    ) -> Any:
        self.call_count += 1
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt
        if self.structured_res is not None:
            return self.structured_res
        return IntentClassificationResult(
            intent=IntentType.RESEARCH,
            confidence=0.95,
            rationale="Mock classified research",
        )


class MockResearchService:
    def __init__(self, answer: str = "Research synthesis output"):
        self.answer = answer
        self.call_count = 0
        self.last_request = None

    async def research(self, project_id: int, request: ResearchRequest) -> ResearchResponse:
        self.call_count += 1
        self.last_request = request
        return ResearchResponse(
            status=ResearchStatus.COMPLETED,
            question=request.question,
            answer=self.answer,
            claims=[],
            citations=[],
            evidence_count=2,
            metadata=ResearchMetadata(
                model="test-model",
                subqueries_executed=[request.question],
                total_evidence_retrieved=2,
                verified_citations_count=0,
                execution_time_ms=10.0,
                llm_call_count=1,
            ),
        )


class MockDeveloperService:
    def __init__(self, summary: str = "Developer patch proposed"):
        self.summary = summary
        self.call_count = 0
        self.last_request = None

    async def execute_task(self, project_id: int, request: DeveloperRequest) -> DeveloperResponse:
        self.call_count += 1
        self.last_request = request
        return DeveloperResponse(
            status=TaskStatus.SUCCESS,
            task_type=request.task_type,
            mode=request.mode,
            summary=self.summary,
            files_analyzed=["math.py"],
            proposed_patches=[],
            documentation="Mock doc",
            warnings=[],
            tool_events=[],
            metadata={"llm_calls_made": 1},
        )


@pytest.fixture
def db_session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    # DDL for checkpoint tables
    with engine.begin() as conn:
        conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS checkpoints (
                thread_id VARCHAR(255) NOT NULL,
                checkpoint_ns VARCHAR(255) NOT NULL DEFAULT '',
                checkpoint_id VARCHAR(255) NOT NULL,
                parent_checkpoint_id VARCHAR(255),
                type VARCHAR(100),
                checkpoint TEXT NOT NULL,
                metadata TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
            );
            """
            )
        )
        conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS checkpoint_writes (
                thread_id VARCHAR(255) NOT NULL,
                checkpoint_ns VARCHAR(255) NOT NULL DEFAULT '',
                checkpoint_id VARCHAR(255) NOT NULL,
                task_id VARCHAR(255) NOT NULL,
                idx INTEGER NOT NULL,
                channel VARCHAR(255) NOT NULL,
                type VARCHAR(100),
                value TEXT NOT NULL,
                PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
            );
            """
            )
        )

    SessionMaker = sessionmaker(bind=engine)
    session = SessionMaker()

    # Seed test user and project
    user = User(
        id=1,
        email="dev@example.com",
        password_hash="pw",
        role=UserRole.MEMBER.value,
    )
    session.add(user)
    session.commit()

    project = Project(
        id=1,
        name="Orchestra Core",
        description="Test project",
        owner_id=user.id,
    )
    session.add(project)
    session.commit()

    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.mark.asyncio
class TestOrchestratorGraph:
    async def test_direct_qa_routing_and_db_logging(self, db_session: Session):
        llm = MockLLM(canned_text="Quantum computing utilizes qubits for superposition.")
        direct_qa = DirectQAEngine(llm_provider=llm)
        classifier = IntentClassifier(llm_provider=llm)
        checkpointer = PostgresSaver(engine=db_session.get_bind())

        service = OrchestratorService(
            db=db_session,
            checkpointer=checkpointer,
            llm_provider=llm,
            classifier=classifier,
            direct_qa_engine=direct_qa,
        )

        req = OrchestratorRequest(prompt="What is quantum computing?")
        resp = await service.orchestrate(project_id=1, request=req, current_user_id=1)

        assert resp.intent == IntentType.DIRECT_QA
        assert "Quantum computing" in resp.answer
        assert resp.research_result is None
        assert resp.developer_result is None
        assert "classify_intent:direct_qa" in resp.execution_trace
        assert "direct_qa:completed" in resp.execution_trace

        # Verify DB session & messages
        db_sess = db_session.query(SessionModel).filter(SessionModel.id == resp.session_id).first()
        assert db_sess is not None
        assert db_sess.status == "completed"
        assert db_sess.project_id == 1

        msgs = db_session.query(MessageModel).filter(MessageModel.session_id == resp.session_id).all()
        assert len(msgs) == 2
        assert msgs[0].role == "user"
        assert msgs[0].content == "What is quantum computing?"
        assert msgs[1].role == "assistant"
        assert "Quantum computing" in msgs[1].content

        # Verify checkpoint persistence
        thread_id = f"proj_1_sess_{resp.session_id}"
        cp_tuple = checkpointer.get_tuple({"configurable": {"thread_id": thread_id}})
        assert cp_tuple is not None
        assert cp_tuple.checkpoint["channel_values"]["answer"] == resp.answer

    async def test_research_routing_and_subgraph_execution(self, db_session: Session):
        llm = MockLLM()
        classifier = IntentClassifier(llm_provider=llm)
        mock_research = MockResearchService(answer="Survey of deep learning architectures.")
        checkpointer = PostgresSaver(engine=db_session.get_bind())

        service = OrchestratorService(
            db=db_session,
            checkpointer=checkpointer,
            llm_provider=llm,
            classifier=classifier,
            research_service=mock_research,
        )

        req = OrchestratorRequest(
            prompt="Search scientific papers and perform literature review on transformer attention",
            research_params={"response_depth": "detailed"},
        )
        resp = await service.orchestrate(project_id=1, request=req, current_user_id=1)

        assert resp.intent == IntentType.RESEARCH
        assert mock_research.call_count == 1
        assert resp.research_result is not None
        assert resp.research_result.status == ResearchStatus.COMPLETED
        assert resp.answer == "Survey of deep learning architectures."
        assert "classify_intent:research" in resp.execution_trace
        assert "research_subgraph:completed:completed" in resp.execution_trace

    async def test_developer_routing_and_subgraph_execution(self, db_session: Session):
        llm = MockLLM()
        classifier = IntentClassifier(llm_provider=llm)
        mock_developer = MockDeveloperService(summary="Added fibonacci calculation function.")
        checkpointer = PostgresSaver(engine=db_session.get_bind())

        service = OrchestratorService(
            db=db_session,
            checkpointer=checkpointer,
            llm_provider=llm,
            classifier=classifier,
            developer_service=mock_developer,
        )

        req = OrchestratorRequest(
            prompt="Refactor git code and fix bug in math.py",
            developer_params={"task_type": "code_gen", "mode": "preview", "target_files": ["math.py"]},
        )
        resp = await service.orchestrate(project_id=1, request=req, current_user_id=1)

        assert resp.intent == IntentType.DEVELOPER
        assert mock_developer.call_count == 1
        assert resp.developer_result is not None
        assert resp.developer_result.status == TaskStatus.SUCCESS
        assert resp.answer == "Added fibonacci calculation function."
        assert "classify_intent:developer" in resp.execution_trace
        assert "developer_subgraph:completed:success" in resp.execution_trace

    async def test_forced_intent_override(self, db_session: Session):
        llm = MockLLM()
        classifier = IntentClassifier(llm_provider=llm)
        mock_developer = MockDeveloperService(summary="Forced developer task execution.")
        checkpointer = PostgresSaver(engine=db_session.get_bind())

        service = OrchestratorService(
            db=db_session,
            checkpointer=checkpointer,
            llm_provider=llm,
            classifier=classifier,
            developer_service=mock_developer,
        )

        # Prompt looks like direct QA, but forced_intent is DEVELOPER
        req = OrchestratorRequest(
            prompt="Hello there, what is your name?",
            forced_intent=IntentType.DEVELOPER,
        )
        resp = await service.orchestrate(project_id=1, request=req, current_user_id=1)

        assert resp.intent == IntentType.DEVELOPER
        assert mock_developer.call_count == 1

    async def test_multi_turn_session_continuation(self, db_session: Session):
        llm = MockLLM(canned_text="First response")
        classifier = IntentClassifier(llm_provider=llm)
        direct_qa = DirectQAEngine(llm_provider=llm)
        checkpointer = PostgresSaver(engine=db_session.get_bind())

        service = OrchestratorService(
            db=db_session,
            checkpointer=checkpointer,
            llm_provider=llm,
            classifier=classifier,
            direct_qa_engine=direct_qa,
        )

        # Turn 1
        req1 = OrchestratorRequest(prompt="Hello turn 1")
        resp1 = await service.orchestrate(project_id=1, request=req1, current_user_id=1)
        sess_id = resp1.session_id

        # Turn 2 continuing sess_id
        llm.canned_text = "Second response"
        req2 = OrchestratorRequest(prompt="Hello turn 2", session_id=sess_id)
        resp2 = await service.orchestrate(project_id=1, request=req2, current_user_id=1)

        assert resp2.session_id == sess_id
        msgs = db_session.query(MessageModel).filter(MessageModel.session_id == sess_id).all()
        assert len(msgs) == 4
        assert [m.role for m in msgs] == ["user", "assistant", "user", "assistant"]

    async def test_invalid_session_id_aborts_without_execution(self, db_session: Session):
        llm = MockLLM()
        service = OrchestratorService(db=db_session, llm_provider=llm)

        req = OrchestratorRequest(prompt="Test prompt", session_id=9999)
        with pytest.raises(ValueError, match="Session 9999 not found in project 1"):
            await service.orchestrate(project_id=1, request=req, current_user_id=1)

    async def test_timeout_deadline_marks_session_failed(self, db_session: Session):
        class SlowQAEngine(DirectQAEngine):
            async def answer(self, prompt: str) -> str:
                await asyncio.sleep(0.5)
                return "Delayed"

        llm = MockLLM()
        classifier = IntentClassifier(llm_provider=llm)
        slow_qa = SlowQAEngine(llm_provider=llm)

        service = OrchestratorService(
            db=db_session,
            llm_provider=llm,
            classifier=classifier,
            direct_qa_engine=slow_qa,
            timeout_seconds=0.05,
        )

        req = OrchestratorRequest(prompt="Explain slow processes")
        with pytest.raises(TimeoutError, match="exceeded global deadline"):
            await service.orchestrate(project_id=1, request=req, current_user_id=1)

        # Verify session marked as failed in DB
        sess = db_session.query(SessionModel).filter(SessionModel.project_id == 1).first()
        assert sess is not None
        assert sess.status == "failed"
