import asyncio
import json
from typing import Any, AsyncIterator, List, Optional
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
    IntentClassificationResult,
    IntentType,
    OrchestratorRequest,
)
from app.orchestrator.service import OrchestratorService
from app.research.llm.mock import DeterministicTestLLMProvider
from app.research.schemas import (
    ResearchMetadata,
    ResearchRequest,
    ResearchResponse,
    ResearchStatus,
    VerifiedCitation,
)
from app.developer.schemas import (
    DeveloperMode,
    DeveloperRequest,
    DeveloperResponse,
    TaskStatus,
    TaskType,
)


class StreamingMockLLM(DeterministicTestLLMProvider):
    def __init__(self, chunks: List[str], intent: IntentType = IntentType.DIRECT_QA):
        super().__init__(mode="normal")
        self.chunks = chunks
        self.intent = intent

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.0,
    ) -> str:
        self.call_count += 1
        return "".join(self.chunks)

    async def stream_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.0,
    ) -> AsyncIterator[str]:
        self.call_count += 1
        for chunk in self.chunks:
            yield chunk
            await asyncio.sleep(0.001)

    async def generate_structured(
        self,
        prompt: str,
        schema: Any,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.0,
    ) -> Any:
        self.call_count += 1
        return IntentClassificationResult(
            intent=self.intent,
            confidence=0.98,
            rationale="Streaming mock classification",
        )


class MockStreamingResearchService:
    def __init__(self, answer: str = "Verified RAG research answer"):
        self.answer = answer

    async def research(self, project_id: int, request: ResearchRequest) -> ResearchResponse:
        return ResearchResponse(
            status=ResearchStatus.COMPLETED,
            question=request.question,
            answer=self.answer,
            claims=[],
            citations=[
                VerifiedCitation(
                    citation_id="cite_1",
                    evidence_id="ev_1",
                    document_id=1,
                    document_filename="orchestra_demo.txt",
                    page_number=1,
                    chunk_id="chunk_1",
                    start_char=0,
                    end_char=100,
                    text="Verified demo evidence text.",
                    score=0.92,
                )
            ],
            evidence_count=1,
            metadata=ResearchMetadata(
                model="nemotron-3.5",
                subqueries_executed=[request.question],
                total_evidence_retrieved=1,
                verified_citations_count=1,
                execution_time_ms=15.0,
                llm_call_count=1,
            ),
        )


class MockStreamingDeveloperService:
    def __init__(self, summary: str = "Generated unified patch preview"):
        self.summary = summary

    async def execute_task(self, project_id: int, request: DeveloperRequest) -> DeveloperResponse:
        return DeveloperResponse(
            status=TaskStatus.SUCCESS,
            task_type=request.task_type,
            mode=request.mode,
            summary=self.summary,
            files_analyzed=["main.py"],
            proposed_patches=[],
            documentation=None,
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

    user = User(
        id=1,
        email="operator@orchestra.io",
        password_hash="pw_hash",
        role=UserRole.MEMBER.value,
    )
    session.add(user)
    session.commit()

    project = Project(
        id=1,
        name="Orchestra Streaming Test",
        description="Testing SSE streaming",
        owner_id=user.id,
    )
    session.add(project)
    session.commit()

    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.mark.asyncio
class TestOrchestratorStreaming:
    async def test_direct_qa_streaming_events_and_ordering(self, db_session: Session):
        chunks = ["Orchestra ", "coordinates ", "multi-agent ", "workflows."]
        llm = StreamingMockLLM(chunks=chunks, intent=IntentType.DIRECT_QA)
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

        req = OrchestratorRequest(prompt="How does Orchestra work?")
        events = []
        async for event in service.orchestrate_stream(project_id=1, request=req, current_user_id=1):
            events.append(event)

        event_names = [e["event"] for e in events]
        assert "session" in event_names
        assert "status" in event_names
        assert "intent" in event_names
        assert "text_delta" in event_names
        assert "done" in event_names

        # Validate event ordering
        assert event_names[0] == "session"
        assert event_names[-1] == "done"

        # Check reconstructed text delta
        text_deltas = [e["data"]["delta"] for e in events if e["event"] == "text_delta"]
        reconstructed = "".join(text_deltas)
        assert reconstructed == "Orchestra coordinates multi-agent workflows."

        # Check final done event data
        done_data = events[-1]["data"]
        assert done_data["intent"] == "direct_qa"
        assert done_data["answer"] == "Orchestra coordinates multi-agent workflows."
        assert len(done_data["execution_trace"]) >= 4

        # Validate single-message persistence invariant in database:
        # Exactly 1 user message and 1 assistant message
        messages = (
            db_session.query(MessageModel)
            .filter(MessageModel.session_id == done_data["session_id"])
            .order_by(MessageModel.id)
            .all()
        )
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[0].content == "How does Orchestra work?"
        assert messages[1].role == "assistant"
        assert messages[1].content == "Orchestra coordinates multi-agent workflows."

    async def test_research_streaming_structured_citations(self, db_session: Session):
        llm = StreamingMockLLM(chunks=[], intent=IntentType.RESEARCH)
        classifier = IntentClassifier(llm_provider=llm)
        research_svc = MockStreamingResearchService(answer="Ground truth verified fact.")

        service = OrchestratorService(
            db=db_session,
            llm_provider=llm,
            classifier=classifier,
            research_service=research_svc,
        )

        req = OrchestratorRequest(
            prompt="What is the deployment procedure in documents?",
            forced_intent=IntentType.RESEARCH,
        )
        events = []
        async for event in service.orchestrate_stream(project_id=1, request=req, current_user_id=1):
            events.append(event)

        event_names = [e["event"] for e in events]
        assert "research_result" in event_names
        assert "text_delta" in event_names
        assert "done" in event_names

        # Check research result payload has verified citations
        res_event = next(e for e in events if e["event"] == "research_result")
        assert len(res_event["data"]["citations"]) == 1
        assert res_event["data"]["citations"][0]["document_filename"] == "orchestra_demo.txt"

        done_event = events[-1]
        assert done_event["data"]["answer"] == "Ground truth verified fact."

    async def test_developer_streaming_structured_payload(self, db_session: Session):
        llm = StreamingMockLLM(chunks=[], intent=IntentType.DEVELOPER)
        classifier = IntentClassifier(llm_provider=llm)
        dev_svc = MockStreamingDeveloperService(summary="Code refactor complete.")

        service = OrchestratorService(
            db=db_session,
            llm_provider=llm,
            classifier=classifier,
            developer_service=dev_svc,
        )

        req = OrchestratorRequest(
            prompt="Refactor math module",
            forced_intent=IntentType.DEVELOPER,
        )
        events = []
        async for event in service.orchestrate_stream(project_id=1, request=req, current_user_id=1):
            events.append(event)

        event_names = [e["event"] for e in events]
        assert "developer_result" in event_names
        assert "done" in event_names

        dev_event = next(e for e in events if e["event"] == "developer_result")
        assert dev_event["data"]["summary"] == "Code refactor complete."

    async def test_cancellation_saves_partial_turn(self, db_session: Session):
        class AbortingLLM(DeterministicTestLLMProvider):
            async def stream_text(self, *args, **kwargs):
                yield "Partial answer before"
                yield " user cancelled."
                raise asyncio.CancelledError()

        llm = AbortingLLM()
        direct_qa = DirectQAEngine(llm_provider=llm)
        classifier = IntentClassifier(llm_provider=llm)

        service = OrchestratorService(
            db=db_session,
            llm_provider=llm,
            classifier=classifier,
            direct_qa_engine=direct_qa,
        )

        req = OrchestratorRequest(prompt="Long generation that will cancel")
        with pytest.raises(asyncio.CancelledError):
            async for _ in service.orchestrate_stream(project_id=1, request=req, current_user_id=1):
                pass

        # Verify database has preserved partial response without crashing
        session = db_session.query(SessionModel).filter(SessionModel.project_id == 1).first()
        assert session is not None
        assert session.status == "completed"

        messages = db_session.query(MessageModel).filter(MessageModel.session_id == session.id).all()
        assert len(messages) == 2
        assert messages[1].content == "Partial answer before user cancelled."

    async def test_error_handling_emits_error_event(self, db_session: Session):
        class FailingLLM(DeterministicTestLLMProvider):
            async def stream_text(self, *args, **kwargs):
                if True:
                    raise RuntimeError("Simulated provider outage")
                yield ""

        llm = FailingLLM()
        direct_qa = DirectQAEngine(llm_provider=llm)
        classifier = IntentClassifier(llm_provider=llm)

        service = OrchestratorService(
            db=db_session,
            llm_provider=llm,
            classifier=classifier,
            direct_qa_engine=direct_qa,
        )

        req = OrchestratorRequest(prompt="Fail prompt")
        events = []
        async for event in service.orchestrate_stream(project_id=1, request=req, current_user_id=1):
            events.append(event)

        error_event = next(e for e in events if e["event"] == "error")
        assert "Simulated provider outage" in error_event["data"]["detail"]

        session = db_session.query(SessionModel).filter(SessionModel.project_id == 1).first()
        assert session is not None
        assert session.status == "failed"
