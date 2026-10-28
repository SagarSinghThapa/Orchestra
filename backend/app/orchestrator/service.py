import asyncio
import logging
import time
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from app.core.checkpoints import PostgresSaver
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
    PostgreSQL conversation session/message records, and a 60.0s execution timeout ceiling.
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
          3. Executes Main LangGraph with namespaced thread_id checkpointing.
          4. Updates Session record status and logs assistant Message record.
          5. Returns strongly typed OrchestratorResponse.
        """
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

        # 3. Setup thread identity & initial state
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
            "answer": "",
            "research_result": None,
            "developer_result": None,
            "execution_trace": [],
            "llm_calls_made": 0,
            "error": None,
        }

        start_time = time.perf_counter()
        try:
            async with asyncio.timeout(self.timeout_seconds):
                final_state = await self.graph.ainvoke(initial_state, config=config)
        except TimeoutError:
            session.status = "failed"
            self.db.commit()
            logger.error("Orchestration exceeded deadline of %ss for thread %s", self.timeout_seconds, thread_id)
            raise TimeoutError(f"Orchestration exceeded global deadline of {self.timeout_seconds}s")
        except Exception as exc:
            session.status = "failed"
            self.db.commit()
            logger.error("Orchestration failed for thread %s: %s", thread_id, exc)
            raise exc

        # 4. Finalize database session and assistant message
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
                "llm_calls_made": final_state.get("llm_calls_made", 0),
            },
        )
