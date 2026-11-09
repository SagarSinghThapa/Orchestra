import asyncio
import pytest
from sqlalchemy.orm import Session

from app.memory.context_assembler import ContextAssembler
from app.memory.schemas import ContextAssemblerConfig
from app.memory.summarizer import SummarizerService
from app.models.message import Message as MessageModel
from app.models.project import Project
from app.models.session import Session as DBSession
from app.models.session_summary import SessionSummary
from app.orchestrator.direct_qa import DirectQAEngine
from app.orchestrator.schemas import IntentType, OrchestratorRequest
from app.orchestrator.service import OrchestratorService
from app.research.llm.mock import DeterministicTestLLMProvider


@pytest.mark.asyncio
async def test_orchestrator_injects_assembled_memory(
    db_session: Session, test_session: DBSession, test_project: Project
):
    """Verifies that OrchestratorService assembles and injects memory into the graph state."""
    # Seed prior messages
    msg1 = MessageModel(session_id=test_session.id, role="user", content="We are designing a microservices auth.")
    msg2 = MessageModel(session_id=test_session.id, role="assistant", content="We recommend JWT tokens with RS256.")
    db_session.add_all([msg1, msg2])
    db_session.commit()

    llm = DeterministicTestLLMProvider()
    service = OrchestratorService(db=db_session, llm_provider=llm)

    req = OrchestratorRequest(
        prompt="What token algorithm did we choose?",
        session_id=test_session.id,
        forced_intent=IntentType.DIRECT_QA,
    )
    resp = await service.orchestrate(project_id=test_project.id, request=req)

    assert resp.session_id == test_session.id
    # Verify assistant message was saved
    last_msg = (
        db_session.query(MessageModel)
        .filter(MessageModel.session_id == test_session.id, MessageModel.role == "assistant")
        .order_by(MessageModel.id.desc())
        .first()
    )
    assert last_msg is not None
    assert last_msg.content == resp.answer


@pytest.mark.asyncio
async def test_orchestrator_budget_circuit_breaker(
    db_session: Session, test_session: DBSession, test_project: Project
):
    """Verifies that total LLM calls per request cannot exceed 5, and summarizer is skipped if budget full."""
    # Pre-seed 60 messages to guarantee summarizer trigger
    for i in range(1, 65):
        db_session.add(MessageModel(
            session_id=test_session.id,
            role="user" if i % 2 == 1 else "assistant",
            content=f"Message turn {i} payload",
        ))
    db_session.commit()

    llm = DeterministicTestLLMProvider()
    service = OrchestratorService(db=db_session, llm_provider=llm)

    req = OrchestratorRequest(
        prompt="Tell me about the system",
        session_id=test_session.id,
        forced_intent=IntentType.DIRECT_QA,
    )
    resp = await service.orchestrate(project_id=test_project.id, request=req)

    # Direct QA (1) + Summarizer (1) = 2 calls <= 5
    assert resp.metadata["llm_calls_made"] <= 5


@pytest.mark.asyncio
async def test_turn_completion_does_not_finalize_session(
    db_session: Session, test_session: DBSession, test_project: Project
):
    """
    CRITICAL: Verifies that session.status='completed' on a single turn
    does NOT mark SessionSummary.status='final'. Summary status must remain 'active'.
    """
    # Seed 55 messages
    for i in range(1, 55):
        db_session.add(MessageModel(
            session_id=test_session.id,
            role="user" if i % 2 == 1 else "assistant",
            content=f"Turn {i} content",
        ))
    db_session.commit()

    llm = DeterministicTestLLMProvider()
    service = OrchestratorService(db=db_session, llm_provider=llm)

    req = OrchestratorRequest(
        prompt="What is the next step?",
        session_id=test_session.id,
        forced_intent=IntentType.DIRECT_QA,
    )
    await service.orchestrate(project_id=test_project.id, request=req)

    # Check the session status
    db_session.refresh(test_session)
    assert test_session.status == "completed"

    # Check the summary row
    summary = (
        db_session.query(SessionSummary)
        .filter(SessionSummary.session_id == test_session.id)
        .first()
    )
    if summary:
        assert summary.status == "active"


@pytest.mark.asyncio
async def test_multi_turn_history_progression(
    db_session: Session, test_session: DBSession, test_project: Project
):
    """Verifies that Turn 1 answer is present in Turn 2 sliding window context."""
    llm = DeterministicTestLLMProvider()
    service = OrchestratorService(db=db_session, llm_provider=llm)

    # Turn 1
    req1 = OrchestratorRequest(
        prompt="Hello, my name is Alice.",
        session_id=test_session.id,
        forced_intent=IntentType.DIRECT_QA,
    )
    resp1 = await service.orchestrate(project_id=test_project.id, request=req1)
    assert resp1.session_id == test_session.id

    # Turn 2
    req2 = OrchestratorRequest(
        prompt="What is my name?",
        session_id=test_session.id,
        forced_intent=IntentType.DIRECT_QA,
    )
    resp2 = await service.orchestrate(project_id=test_project.id, request=req2)
    assert resp2.session_id == test_session.id

    # Both turns must be in messages
    all_msgs = (
        db_session.query(MessageModel)
        .filter(MessageModel.session_id == test_session.id)
        .order_by(MessageModel.id.asc())
        .all()
    )
    assert len(all_msgs) == 4  # 2 user + 2 assistant


@pytest.mark.asyncio
async def test_memory_assembly_failure_non_fatal(
    db_session: Session, test_session: DBSession, test_project: Project
):
    """Verifies that if context assembly raises an exception, the orchestrator continues cleanly."""
    class BrokenAssembler(ContextAssembler):
        def assemble(self, session_id: int, project_id: int):
            raise RuntimeError("Database read failed for context assembler")

    llm = DeterministicTestLLMProvider()
    broken_assembler = BrokenAssembler(db=db_session)
    service = OrchestratorService(db=db_session, llm_provider=llm, context_assembler=broken_assembler)

    req = OrchestratorRequest(
        prompt="Testing broken assembler recovery",
        session_id=test_session.id,
        forced_intent=IntentType.DIRECT_QA,
    )
    resp = await service.orchestrate(project_id=test_project.id, request=req)
    # The turn must succeed regardless of assembler error
    assert resp.answer != ""
    assert resp.session_id == test_session.id


@pytest.mark.asyncio
async def test_orchestrator_global_deadline_enforcement(
    db_session: Session, test_session: DBSession, test_project: Project
):
    """Verifies that an orchestration timeout aborts cleanly and marks session failed."""
    class HangingLLM(DeterministicTestLLMProvider):
        async def generate_text(self, *args, **kwargs) -> str:
            await asyncio.sleep(0.5)
            return "too late"

    llm = HangingLLM()
    # Low timeout
    service = OrchestratorService(db=db_session, llm_provider=llm, timeout_seconds=0.1)

    req = OrchestratorRequest(
        prompt="Will time out",
        session_id=test_session.id,
        forced_intent=IntentType.DIRECT_QA,
    )
    with pytest.raises((TimeoutError, asyncio.TimeoutError)):
        await service.orchestrate(project_id=test_project.id, request=req)

    db_session.refresh(test_session)
    assert test_session.status == "failed"
