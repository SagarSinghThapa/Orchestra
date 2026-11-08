import asyncio
import inspect
import logging
import time
from typing import Any, AsyncIterator, Dict, Optional
from sqlalchemy.orm import Session

from app.core.checkpoints import PostgresSaver
from app.developer.logging import scrub_secrets
from app.developer.schemas import DeveloperMode, DeveloperRequest, DeveloperResponse, TaskType
from app.developer.services.developer_service import DeveloperService
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
from app.research.schemas import ResearchRequest, ResearchResponse
from app.research.services.research_service import ResearchService

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

    async def orchestrate_stream(
        self,
        project_id: int,
        request: OrchestratorRequest,
        current_user_id: Optional[int] = None,
    ) -> AsyncIterator[dict]:
        """
        Executes unified streaming orchestration workflow:
          1. Resolves or creates Session record and logs inbound user Message record.
          2. Emits session and status events over Server-Sent Events.
          3. Assembles bounded memory context.
          4. Classifies intent and routes to subgraphs or Direct QA.
          5. Streams real-time text chunks, structured payloads, and traces.
          6. Persists single assistant Message record per turn to PostgreSQL.
          7. Runs incremental summarization (budget <= 5).
          8. Emits final 'done' event.
        """
        start_time = time.perf_counter()
        session: Optional[SessionModel] = None
        accumulated_text = ""
        total_calls = 0

        try:
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

            # Emit session created/adopted event
            yield {"event": "session", "data": {"session_id": session.id}}
            yield {"event": "status", "data": {"status": "Analyzing request & assembling context..."}}

            # 3. Assemble memory context (0 LLM calls, hard capped)
            memory_str: Optional[str] = None
            if self.context_assembler:
                try:
                    ctx = self.context_assembler.assemble(session_id=session.id, project_id=project_id)
                    formatted = self.context_assembler.format_for_prompt(ctx)
                    if formatted.strip():
                        memory_str = formatted
                except Exception as exc:
                    logger.warning("Memory context assembly failed (non-fatal): %s", exc)

            # 4. Classify intent
            forced_val = request.forced_intent.value if request.forced_intent else None
            forced_intent = IntentType(forced_val) if forced_val else None

            classification = await self.classifier.classify(request.prompt, forced_intent=forced_intent)
            total_calls += 1
            intent = classification.intent
            intent_str = intent.value

            yield {"event": "intent", "data": {"intent": intent_str}}

            execution_trace = [f"classify_intent:{intent_str}"]
            research_result = None
            developer_result = None

            # 5. Route by intent
            if intent == IntentType.RESEARCH:
                execution_trace.append("research_subgraph:start")
                yield {"event": "status", "data": {"status": "Searching knowledge..."}}
                r_params = request.research_params or {}
                req = ResearchRequest(
                    question=request.prompt,
                    max_subqueries=r_params.get("max_subqueries", 3),
                    max_evidence=r_params.get("max_evidence", 10),
                    response_depth=r_params.get("response_depth", "standard"),
                )

                status_queue: asyncio.Queue[str] = asyncio.Queue()
                async def research_status_cb(st: str):
                    await status_queue.put(st)

                research_kwargs = {"project_id": project_id, "request": req}
                try:
                    if "status_callback" in inspect.signature(self.research_service.research).parameters:
                        research_kwargs["status_callback"] = research_status_cb
                except Exception:
                    pass

                research_task = asyncio.create_task(
                    self.research_service.research(**research_kwargs)
                )

                while not research_task.done():
                    try:
                        st = await asyncio.wait_for(status_queue.get(), timeout=0.1)
                        yield {"event": "status", "data": {"status": st}}
                    except asyncio.TimeoutError:
                        pass

                while not status_queue.empty():
                    st = status_queue.get_nowait()
                    yield {"event": "status", "data": {"status": st}}

                resp = await research_task
                total_calls += 1
                execution_trace.append(f"research_subgraph:completed:{resp.status.value}")
                research_result = resp.model_dump()
                yield {"event": "research_result", "data": research_result}

                # Stream the verified answer text
                accumulated_text = resp.answer or "Insufficient verified evidence."
                words = [w for w in accumulated_text.split(" ") if w]
                for i, word in enumerate(words):
                    chunk = word + (" " if i < len(words) - 1 else "")
                    yield {"event": "text_delta", "data": {"delta": chunk}}
                    await asyncio.sleep(0.01)

            elif intent == IntentType.DEVELOPER:
                execution_trace.append("developer_subgraph:start")
                yield {"event": "status", "data": {"status": "Analyzing repository..."}}
                d_params = request.developer_params or {}
                raw_task = d_params.get("task_type", TaskType.CODE_GEN.value)
                task_type = TaskType(raw_task) if isinstance(raw_task, str) else raw_task
                raw_mode = d_params.get("mode", DeveloperMode.PREVIEW.value)
                mode = DeveloperMode(raw_mode) if isinstance(raw_mode, str) else raw_mode

                d_req = DeveloperRequest(
                    task_type=task_type,
                    prompt=request.prompt,
                    mode=mode,
                    target_files=d_params.get("target_files"),
                    expected_file_hashes=d_params.get("expected_file_hashes"),
                    context_hints=d_params.get("context_hints"),
                )

                dev_status_queue: asyncio.Queue[str] = asyncio.Queue()
                async def dev_status_cb(st: str):
                    await dev_status_queue.put(st)

                dev_kwargs = {"project_id": project_id, "request": d_req}
                try:
                    if "status_callback" in inspect.signature(self.developer_service.execute_task).parameters:
                        dev_kwargs["status_callback"] = dev_status_cb
                except Exception:
                    pass

                dev_task = asyncio.create_task(
                    self.developer_service.execute_task(**dev_kwargs)
                )

                while not dev_task.done():
                    try:
                        st = await asyncio.wait_for(dev_status_queue.get(), timeout=0.1)
                        yield {"event": "status", "data": {"status": st}}
                    except asyncio.TimeoutError:
                        pass

                while not dev_status_queue.empty():
                    st = dev_status_queue.get_nowait()
                    yield {"event": "status", "data": {"status": st}}

                resp = await dev_task
                total_calls += 1
                execution_trace.append(f"developer_subgraph:completed:{resp.status.value}")
                developer_result = resp.model_dump()
                yield {"event": "developer_result", "data": developer_result}

                ans = resp.summary or (resp.documentation if resp.documentation else "Developer task completed.")
                accumulated_text = ans
                words = ans.split(" ")
                for i, word in enumerate(words):
                    chunk = word + (" " if i < len(words) - 1 else "")
                    yield {"event": "text_delta", "data": {"delta": chunk}}
                    await asyncio.sleep(0.01)

            else:  # DIRECT_QA
                execution_trace.append("direct_qa:start")
                yield {"event": "status", "data": {"status": "Thinking..."}}
                total_calls += 1
                async for chunk in self.direct_qa_engine.answer_stream(request.prompt, context=memory_str):
                    accumulated_text += chunk
                    yield {"event": "text_delta", "data": {"delta": chunk}}
                execution_trace.append("direct_qa:completed")

            execution_trace.append("synthesize_output:finalized")

            # 6. Finalize turn and persist assistant message (Single message in DB!)
            session.status = "completed"
            self.db.commit()

            final_answer = scrub_secrets(accumulated_text.strip())
            assistant_message = MessageModel(
                session_id=session.id,
                role="assistant",
                content=final_answer,
            )
            self.db.add(assistant_message)
            self.db.commit()

            # 7. Post-Turn Incremental Summarization
            if self.summarizer and (total_calls + 1 <= 5):
                try:
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

            # 8. Emit final done event
            yield {
                "event": "done",
                "data": {
                    "session_id": session.id,
                    "intent": intent_str,
                    "answer": final_answer,
                    "research_result": research_result,
                    "developer_result": developer_result,
                    "execution_trace": execution_trace,
                    "metadata": {
                        "duration_ms": duration_ms,
                        "thread_id": PostgresSaver.format_thread_id(project_id, session.id),
                        "llm_calls_made": total_calls,
                    },
                },
            }

        except asyncio.CancelledError:
            logger.info("Stream cancelled by client (session_id=%s)", session.id if session else "unknown")
            if session is not None:
                if accumulated_text.strip():
                    final_answer = scrub_secrets(accumulated_text.strip())
                    assistant_message = MessageModel(
                        session_id=session.id,
                        role="assistant",
                        content=final_answer,
                    )
                    self.db.add(assistant_message)
                    session.status = "completed"
                else:
                    session.status = "cancelled"
                try:
                    self.db.commit()
                except Exception:
                    self.db.rollback()
            raise
        except Exception as exc:
            clean_err = scrub_secrets(str(exc))
            logger.error("Error in orchestrate_stream: %s", clean_err)
            if session is not None:
                session.status = "failed"
                try:
                    self.db.commit()
                except Exception:
                    self.db.rollback()
            yield {"event": "error", "data": {"detail": clean_err}}

