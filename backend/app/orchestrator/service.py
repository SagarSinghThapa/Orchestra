import asyncio
import logging
import time
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from app.core.checkpoints import PostgresSaver
from app.memory.context_assembler import ContextAssembler
from app.memory.summarizer import SummarizerService
from app.models.session import Session as SessionModel
from app.models.message import Message as MessageModel
from app.orchestrator.classifier import IntentClassifier
from app.orchestrator.direct_qa import DirectQAEngine
from app.orchestrator.graph import compile_orchestrator_graph
from app.orchestrator.schemas import (
    IntentType,
    OrchestratorRequest,
    OrchestratorResponse,
    OrchestratorState,
)
from app.research.llm.base import LLMProvider
from app.research.llm.provider import get_llm_provider
from app.research.schemas import ResearchResponse
from app.research.services.research_service import ResearchService
from app.developer.schemas import DeveloperResponse
from app.developer.services.developer_service import DeveloperService

logger = logging.getLogger("orchestrator.service")


class OrchestratorService:
    """
    Unified multi-agent orchestration facade.
    Coordinates the Main LangGraph state machine, PostgresSaver checkpointer,
    conversational memory context assembly, incremental summarization,
    and a global 60.0s execution timeout ceiling.
    """

    def __init__(
        self,
        db: Session,
        checkpointer: Optional[PostgresSaver] = None,
        llm_provider: Optional[LLMProvider] = None,
        research_service: Optional[ResearchService] = None,
        developer_service: Optional[DeveloperService] = None,
        classifier: Optional[IntentClassifier] = None,
        direct_qa_engine: Optional[DirectQAEngine] = None,
        context_assembler: Optional[ContextAssembler] = None,
        summarizer: Optional[SummarizerService] = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.db = db
        self.timeout_seconds = timeout_seconds

        if llm_provider is not None:
            self.llm_provider = llm_provider
        else:
            try:
                self.llm_provider = get_llm_provider()
            except Exception:
                self.llm_provider = None

        if checkpointer is not None:
            self.checkpointer = checkpointer
        else:
            bind = self.db.get_bind() if self.db else None
            engine = bind.engine if bind and hasattr(bind, "engine") else bind
            self.checkpointer = PostgresSaver(engine=engine)

        self.classifier = classifier or IntentClassifier(llm_provider=self.llm_provider)
        self.direct_qa_engine = direct_qa_engine or DirectQAEngine(llm_provider=self.llm_provider)
        self.research_service = research_service or ResearchService(db=self.db, llm_provider=self.llm_provider)
        self.developer_service = developer_service or DeveloperService(db=self.db, llm_provider=self.llm_provider)

        self.context_assembler = context_assembler or ContextAssembler(db=self.db)
        self.summarizer = summarizer or (
            SummarizerService(db=self.db, llm_provider=self.llm_provider) if self.llm_provider else None
        )

        self.graph = compile_orchestrator_graph(
            classifier=self.classifier,
            research_service=self.research_service,
            developer_service=self.developer_service,
            direct_qa_engine=self.direct_qa_engine,
            checkpointer=self.checkpointer,
        )

    async def orchestrate(
        self,
        project_id: int,
        request: OrchestratorRequest,
        current_user_id: Optional[int] = None,
    ) -> OrchestratorResponse:
        """
        Executes unified orchestration workflow:
          1. Resolves or initializes PostgreSQL Session record.
          2. Logs inbound user Message record.
          3. Assembles bounded memory context (Tier 1-3) under hard cap.
          4. Executes Main LangGraph with namespaced thread_id checkpointing.
          5. Updates Session record status (per-turn) and logs assistant Message record.
          6. Runs post-turn incremental summarization subject to <=5 LLM budget ceiling.
          7. Returns strongly typed OrchestratorResponse.
        """
        start_time = time.perf_counter()
        session: Optional[SessionModel] = None

        try:
            # The global parent deadline covers the ENTIRE request lifecycle
            async with asyncio.timeout(self.timeout_seconds):
                # 1. Resolve or create Session
                if request.session_id is not None:
                    session = (
                        self.db.query(SessionModel)
                        .filter(SessionModel.id == request.session_id, SessionModel.project_id == project_id)
                        .first()
                    )
                    if not session:
                        raise ValueError(f"Session {request.session_id} not found in project {project_id}")
                else:
                    title_text = (request.prompt[:47] + "...") if len(request.prompt) > 50 else request.prompt
                    session = SessionModel(
                        project_id=project_id,
                        type="orchestrator",
                        title=title_text,
                        query=request.prompt,
                        status="pending",
                    )
                    self.db.add(session)
                    self.db.commit()
                    self.db.refresh(session)

                # 2. Record user message
                user_message = MessageModel(
                    session_id=session.id,
                    role="user",
                    content=request.prompt,
                )
                self.db.add(user_message)
                self.db.commit()

                # 3. Assemble memory context (0 LLM calls, hard capped at max_context_chars)
                memory_str: Optional[str] = None
                if self.context_assembler:
                    try:
                        ctx = self.context_assembler.assemble(session_id=session.id, project_id=project_id)
                        formatted = self.context_assembler.format_for_prompt(ctx)
                        if formatted.strip():
                            memory_str = formatted
                    except Exception as exc:
                        logger.warning("Memory context assembly failed (non-fatal): %s", exc)

                # 4. Setup thread identity & initial state
                thread_id = PostgresSaver.format_thread_id(project_id, session.id)
                config = {"configurable": {"thread_id": thread_id}}

                initial_state: OrchestratorState = {
                    "project_id": project_id,
                    "session_id": session.id,
                    "prompt": request.prompt,
                    "forced_intent": request.forced_intent.value if request.forced_intent else None,
                    "intent": None,
                    "developer_params": request.developer_params,
                    "research_params": request.research_params,
                    "memory_context": memory_str,
                    "answer": "",
                    "research_result": None,
                    "developer_result": None,
                    "execution_trace": [],
                    "llm_calls_made": 0,
                    "error": None,
                }

                try:
                    final_state = await self.graph.ainvoke(initial_state, config=config)
                except Exception as exc:
                    session.status = "failed"
                    self.db.commit()
                    logger.error("Orchestration failed for thread %s: %s", thread_id, exc)
                    raise exc

                # 5. Finalize turn and persist assistant message
                # Crucial: session.status='completed' is a PER-TURN status and does NOT finalize conversation!
                session.status = "completed"
                self.db.commit()

                answer_text = final_state.get("answer", "")
                assistant_message = MessageModel(
                    session_id=session.id,
                    role="assistant",
                    content=answer_text,
                )
                self.db.add(assistant_message)
                self.db.commit()

                total_calls = final_state.get("llm_calls_made", 0)

                # 6. Post-Turn Incremental Summarization with Circuit Breaker (<= 5 request-wide LLM budget)
                if self.summarizer and (total_calls + 1 <= 5):
                    try:
                        # Inner 15.0s timeout ensures summarizer cannot starve request
                        async with asyncio.timeout(15.0):
                            summary_res = await self.summarizer.maybe_summarize(
                                session_id=session.id,
                                project_id=project_id,
                            )
                            if summary_res:
                                total_calls += 1
                    except Exception as exc:
                        logger.warning("Post-turn summarization failed or skipped (non-fatal): %s", exc)

                duration_ms = (time.perf_counter() - start_time) * 1000.0
                intent_str = final_state.get("intent") or IntentType.DIRECT_QA.value

                research_res = None
                if final_state.get("research_result"):
                    research_res = ResearchResponse.model_validate(final_state["research_result"])

                developer_res = None
                if final_state.get("developer_result"):
                    developer_res = DeveloperResponse.model_validate(final_state["developer_result"])

                return OrchestratorResponse(
                    session_id=session.id,
                    intent=IntentType(intent_str),
                    answer=answer_text,
                    research_result=research_res,
                    developer_result=developer_res,
                    execution_trace=final_state.get("execution_trace", []),
                    metadata={
                        "duration_ms": duration_ms,
                        "thread_id": thread_id,
                        "llm_calls_made": total_calls,
                    },
                )
        except (TimeoutError, asyncio.TimeoutError) as exc:
            if session is not None:
                session.status = "failed"
                try:
                    self.db.commit()
                except Exception:
                    self.db.rollback()
            sess_id = session.id if session else "unknown"
            logger.error("Global request deadline exceeded (%.1fs) for project %s", self.timeout_seconds, project_id)
            raise TimeoutError(f"Request {sess_id} exceeded global deadline of {self.timeout_seconds}s") from exc
