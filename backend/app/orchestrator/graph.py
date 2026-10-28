import logging
from typing import Any, Callable, Dict, List, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.base import BaseCheckpointSaver

from app.orchestrator.schemas import (
    IntentType,
    OrchestratorState,
)
from app.orchestrator.classifier import IntentClassifier
from app.orchestrator.direct_qa import DirectQAEngine
from app.research.services.research_service import ResearchService
from app.research.schemas import ResearchRequest
from app.developer.services.developer_service import DeveloperService
from app.developer.schemas import DeveloperRequest, TaskType, DeveloperMode

logger = logging.getLogger("orchestrator.graph")


def create_orchestrator_graph(
    classifier: IntentClassifier,
    research_service: ResearchService,
    developer_service: DeveloperService,
    direct_qa_engine: DirectQAEngine,
) -> StateGraph:
    """
    Constructs the top-level Main LangGraph state machine.
    Nodes:
      - classify_intent: Classifies user prompt into RESEARCH, DEVELOPER, or DIRECT_QA.
      - research_subgraph: Delegates to ResearchService.
      - developer_subgraph: Delegates to DeveloperService.
      - direct_qa: Answers general inquiries directly.
      - synthesize_output: Finalizes state and execution trace.
    """

    async def classify_intent_node(state: OrchestratorState) -> Dict[str, Any]:
        prompt = state.get("prompt", "")
        forced_val = state.get("forced_intent")
        forced_intent = IntentType(forced_val) if forced_val else None

        classification = await classifier.classify(prompt, forced_intent=forced_intent)
        trace = list(state.get("execution_trace", []))
        trace.append(f"classify_intent:{classification.intent.value}")
        return {
            "intent": classification.intent.value,
            "execution_trace": trace,
        }

    def route_by_intent(state: OrchestratorState) -> str:
        intent = state.get("intent")
        if intent == IntentType.RESEARCH.value:
            return "research_subgraph"
        elif intent == IntentType.DEVELOPER.value:
            return "developer_subgraph"
        return "direct_qa"

    async def research_subgraph_node(state: OrchestratorState) -> Dict[str, Any]:
        project_id = state["project_id"]
        prompt = state["prompt"]
        r_params = state.get("research_params") or {}

        req = ResearchRequest(
            question=prompt,
            max_subqueries=r_params.get("max_subqueries", 3),
            max_evidence=r_params.get("max_evidence", 10),
            response_depth=r_params.get("response_depth", "standard"),
        )
        trace = list(state.get("execution_trace", []))
        trace.append("research_subgraph:start")

        try:
            resp = await research_service.research(project_id=project_id, request=req)
            trace.append(f"research_subgraph:completed:{resp.status.value}")
            return {
                "research_result": resp.model_dump(),
                "answer": resp.answer,
                "execution_trace": trace,
            }
        except Exception as exc:
            logger.error("Research subgraph failure: %s", exc)
            trace.append(f"research_subgraph:error:{str(exc)}")
            return {
                "error": str(exc),
                "answer": f"Research execution failed: {str(exc)}",
                "execution_trace": trace,
            }

    async def developer_subgraph_node(state: OrchestratorState) -> Dict[str, Any]:
        project_id = state["project_id"]
        prompt = state["prompt"]
        d_params = state.get("developer_params") or {}

        raw_task = d_params.get("task_type", TaskType.CODE_GEN.value)
        if isinstance(raw_task, str):
            try:
                task_type = TaskType(raw_task)
            except ValueError:
                task_type = TaskType.CODE_GEN
        else:
            task_type = raw_task

        raw_mode = d_params.get("mode", DeveloperMode.PREVIEW.value)
        if isinstance(raw_mode, str):
            try:
                mode = DeveloperMode(raw_mode)
            except ValueError:
                mode = DeveloperMode.PREVIEW
        else:
            mode = raw_mode

        req = DeveloperRequest(
            task_type=task_type,
            prompt=prompt,
            mode=mode,
            target_files=d_params.get("target_files"),
            expected_file_hashes=d_params.get("expected_file_hashes"),
            context_hints=d_params.get("context_hints"),
        )
        trace = list(state.get("execution_trace", []))
        trace.append("developer_subgraph:start")

        try:
            resp = await developer_service.execute_task(project_id=project_id, request=req)
            trace.append(f"developer_subgraph:completed:{resp.status.value}")
            ans = resp.summary or (resp.documentation if resp.documentation else "Developer task completed.")
            return {
                "developer_result": resp.model_dump(),
                "answer": ans,
                "execution_trace": trace,
            }
        except Exception as exc:
            logger.error("Developer subgraph failure: %s", exc)
            trace.append(f"developer_subgraph:error:{str(exc)}")
            return {
                "error": str(exc),
                "answer": f"Developer task execution failed: {str(exc)}",
                "execution_trace": trace,
            }

    async def direct_qa_node(state: OrchestratorState) -> Dict[str, Any]:
        prompt = state["prompt"]
        trace = list(state.get("execution_trace", []))
        trace.append("direct_qa:start")

        try:
            ans = await direct_qa_engine.answer(prompt)
            trace.append("direct_qa:completed")
            return {
                "answer": ans,
                "execution_trace": trace,
            }
        except Exception as exc:
            logger.error("Direct QA failure: %s", exc)
            trace.append(f"direct_qa:error:{str(exc)}")
            return {
                "error": str(exc),
                "answer": f"Direct QA execution failed: {str(exc)}",
                "execution_trace": trace,
            }

    async def synthesize_output_node(state: OrchestratorState) -> Dict[str, Any]:
        trace = list(state.get("execution_trace", []))
        trace.append("synthesize_output:finalized")
        return {
            "execution_trace": trace,
        }

    workflow = StateGraph(OrchestratorState)
    workflow.add_node("classify_intent", classify_intent_node)
    workflow.add_node("research_subgraph", research_subgraph_node)
    workflow.add_node("developer_subgraph", developer_subgraph_node)
    workflow.add_node("direct_qa", direct_qa_node)
    workflow.add_node("synthesize_output", synthesize_output_node)

    workflow.set_entry_point("classify_intent")
    workflow.add_conditional_edges(
        "classify_intent",
        route_by_intent,
        {
            "research_subgraph": "research_subgraph",
            "developer_subgraph": "developer_subgraph",
            "direct_qa": "direct_qa",
        },
    )
    workflow.add_edge("research_subgraph", "synthesize_output")
    workflow.add_edge("developer_subgraph", "synthesize_output")
    workflow.add_edge("direct_qa", "synthesize_output")
    workflow.add_edge("synthesize_output", END)

    return workflow


def compile_orchestrator_graph(
    classifier: IntentClassifier,
    research_service: ResearchService,
    developer_service: DeveloperService,
    direct_qa_engine: DirectQAEngine,
    checkpointer: Optional[BaseCheckpointSaver] = None,
):
    """
    Compiles and returns the executable Main LangGraph instance with optional checkpoint saver.
    """
    graph = create_orchestrator_graph(
        classifier=classifier,
        research_service=research_service,
        developer_service=developer_service,
        direct_qa_engine=direct_qa_engine,
    )
    return graph.compile(checkpointer=checkpointer)
