import logging
import time
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.research.agents.aggregator import (
    AggregatedEvidence,
    EvidenceAggregator,
    EvidenceSelector,
)
from app.research.agents.planner import ResearchPlanner
from app.research.agents.synthesizer import ResearchSynthesizer
from app.research.agents.verifier import (
    CANONICAL_INSUFFICIENT_EVIDENCE_ANSWER,
    CitationVerifier,
)
from app.research.graph.state import ResearchState
from app.research.schemas import DraftResearchAnswer, ResearchStatus

logger = logging.getLogger(__name__)


def create_plan_node(planner: ResearchPlanner):
    async def plan_node(state: ResearchState) -> dict[str, Any]:
        plan = await planner.plan(
            question=state["question"],
            max_subqueries=state.get("max_subqueries", 3),
        )
        return {
            "subqueries": plan.subqueries,
        }

    return plan_node


def create_retrieve_node(aggregator: EvidenceAggregator):
    async def retrieve_node(state: ResearchState) -> dict[str, Any]:
        subqueries = state.get("subqueries", [state["question"]])
        aggregated_items = await aggregator.aggregate(
            project_id=state["project_id"],
            subqueries=subqueries,
            limit_per_query=5,
        )
        return {
            "retrieved_evidence": [item.model_dump() for item in aggregated_items],
        }

    return retrieve_node


def create_select_node(selector: EvidenceSelector):
    def select_node(state: ResearchState) -> dict[str, Any]:
        raw_candidates = state.get("retrieved_evidence", [])
        candidates = [AggregatedEvidence.model_validate(c) for c in raw_candidates]
        selected = selector.select(
            candidates=candidates,
            max_chunks_override=state.get("max_evidence", 10),
        )
        return {
            "selected_evidence": [item.model_dump() for item in selected],
        }

    return select_node


def create_synthesize_node(synthesizer: ResearchSynthesizer):
    async def synthesize_node(state: ResearchState) -> dict[str, Any]:
        raw_evidence = state.get("selected_evidence", [])
        evidence_items = [AggregatedEvidence.model_validate(e) for e in raw_evidence]
        draft = await synthesizer.synthesize(
            question=state["question"],
            evidence=evidence_items,
        )
        return {
            "draft_answer": draft.model_dump(),
        }

    return synthesize_node


def create_verify_node(verifier: CitationVerifier):
    def verify_node(state: ResearchState) -> dict[str, Any]:
        raw_draft = state.get("draft_answer")
        if not raw_draft:
            return {
                "status": ResearchStatus.INSUFFICIENT_EVIDENCE.value,
                "answer": CANONICAL_INSUFFICIENT_EVIDENCE_ANSWER,
                "verified_claims": [],
                "verified_citations": [],
            }

        draft = DraftResearchAnswer.model_validate(raw_draft)
        raw_evidence = state.get("selected_evidence", [])
        evidence_items = [AggregatedEvidence.model_validate(e) for e in raw_evidence]

        claims, citations, answer, is_sufficient = verifier.verify(
            project_id=state["project_id"],
            draft=draft,
            evidence_pool=evidence_items,
        )

        if is_sufficient:
            return {
                "status": ResearchStatus.COMPLETED.value,
                "answer": answer,
                "verified_claims": [c.model_dump() for c in claims],
                "verified_citations": [c.model_dump() for c in citations],
            }
        else:
            return {
                "status": ResearchStatus.INSUFFICIENT_EVIDENCE.value,
                "answer": CANONICAL_INSUFFICIENT_EVIDENCE_ANSWER,
                "verified_claims": [],
                "verified_citations": [],
            }

    return verify_node


def create_repair_node(synthesizer: ResearchSynthesizer):
    async def repair_node(state: ResearchState) -> dict[str, Any]:
        raw_evidence = state.get("selected_evidence", [])
        evidence_items = [AggregatedEvidence.model_validate(e) for e in raw_evidence]
        current_repairs = state.get("repair_count", 0)

        draft = await synthesizer.synthesize(
            question=state["question"],
            evidence=evidence_items,
        )
        return {
            "draft_answer": draft.model_dump(),
            "repair_count": current_repairs + 1,
        }

    return repair_node


def insufficient_evidence_node(state: ResearchState) -> dict[str, Any]:
    return {
        "status": ResearchStatus.INSUFFICIENT_EVIDENCE.value,
        "answer": CANONICAL_INSUFFICIENT_EVIDENCE_ANSWER,
        "verified_claims": [],
        "verified_citations": [],
    }


def finalize_node(state: ResearchState) -> dict[str, Any]:
    return {}


def route_after_retrieval(state: ResearchState) -> str:
    if not state.get("retrieved_evidence"):
        return "insufficient_evidence"
    return "select"


def route_after_verification(state: ResearchState) -> str:
    if state.get("status") == ResearchStatus.COMPLETED.value:
        return "finalize"
    if state.get("repair_count", 0) < 1:
        return "repair"
    return "insufficient_evidence"


def compile_research_subgraph(
    planner: ResearchPlanner,
    aggregator: EvidenceAggregator,
    selector: EvidenceSelector,
    synthesizer: ResearchSynthesizer,
    verifier: CitationVerifier,
):
    """
    Compiles and returns the LangGraph Research Subgraph.
    Enforces strictly bounded conditional transitions and maximum 1 repair cycle.
    """
    graph = StateGraph(ResearchState)

    graph.add_node("plan", create_plan_node(planner))
    graph.add_node("retrieve", create_retrieve_node(aggregator))
    graph.add_node("select", create_select_node(selector))
    graph.add_node("synthesize", create_synthesize_node(synthesizer))
    graph.add_node("verify", create_verify_node(verifier))
    graph.add_node("repair", create_repair_node(synthesizer))
    graph.add_node("insufficient_evidence", insufficient_evidence_node)
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "plan")
    graph.add_edge("plan", "retrieve")

    graph.add_conditional_edges(
        "retrieve",
        route_after_retrieval,
        {
            "select": "select",
            "insufficient_evidence": "insufficient_evidence",
        },
    )

    graph.add_edge("select", "synthesize")
    graph.add_edge("synthesize", "verify")

    graph.add_conditional_edges(
        "verify",
        route_after_verification,
        {
            "finalize": "finalize",
            "repair": "repair",
            "insufficient_evidence": "insufficient_evidence",
        },
    )

    # After repair, verify once more then terminate
    graph.add_edge("repair", "verify")

    graph.add_edge("insufficient_evidence", END)
    graph.add_edge("finalize", END)

    return graph.compile()
