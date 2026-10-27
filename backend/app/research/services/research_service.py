import asyncio
import logging
import time
from typing import Optional
from sqlalchemy.orm import Session

from app.core.config import settings
from app.research.agents.aggregator import (
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
from app.research.graph.subgraph import compile_research_subgraph
from app.research.llm.base import LLMProvider
from app.research.llm.budget import LLMCallBudget
from app.research.llm.provider import get_llm_provider
from app.research.schemas import (
    ResearchClaim,
    ResearchMetadata,
    ResearchRequest,
    ResearchResponse,
    ResearchStatus,
    VerifiedCitation,
)
from app.research.services.retrieval_service import RetrievalService

logger = logging.getLogger(__name__)


class ResearchService:
    """
    Coordinates end-to-end research intelligence workflow.
    Owns runtime dependencies, compiles the LangGraph state machine, enforces global deadlines,
    and returns strongly-typed ResearchResponse models.
    """

    def __init__(
        self,
        db: Session,
        retrieval_service: Optional[RetrievalService] = None,
        llm_provider: Optional[LLMProvider] = None,
        planner: Optional[ResearchPlanner] = None,
        aggregator: Optional[EvidenceAggregator] = None,
        selector: Optional[EvidenceSelector] = None,
        synthesizer: Optional[ResearchSynthesizer] = None,
        verifier: Optional[CitationVerifier] = None,
    ) -> None:
        self.db = db
        self.llm_provider = llm_provider or get_llm_provider()
        self.retrieval_service = retrieval_service or RetrievalService(db=self.db)
        self.planner = planner or ResearchPlanner(llm_provider=self.llm_provider)
        self.aggregator = aggregator or EvidenceAggregator(retrieval_service=self.retrieval_service)
        self.selector = selector or EvidenceSelector()
        self.synthesizer = synthesizer or ResearchSynthesizer(llm_provider=self.llm_provider)
        self.verifier = verifier or CitationVerifier(db=self.db)

        self.graph = compile_research_subgraph(
            planner=self.planner,
            aggregator=self.aggregator,
            selector=self.selector,
            synthesizer=self.synthesizer,
            verifier=self.verifier,
        )

    async def research(
        self,
        project_id: int,
        request: ResearchRequest,
    ) -> ResearchResponse:
        """
        Executes bounded, authenticated research workflow with global request deadline.
        """
        start_time = time.perf_counter()

        initial_state: ResearchState = {
            "project_id": project_id,
            "question": request.question,
            "max_subqueries": request.max_subqueries,
            "max_evidence": request.max_evidence,
            "response_depth": request.response_depth,
            "subqueries": [],
            "retrieved_evidence": [],
            "selected_evidence": [],
            "draft_answer": None,
            "verified_claims": [],
            "verified_citations": [],
            "status": "pending",
            "answer": "",
            "repair_count": 0,
            "metadata": {},
        }

        deadline = getattr(settings, "research_timeout_seconds", 45.0)
        budget = LLMCallBudget(max_calls=getattr(settings, "max_llm_calls_per_request", 3))
        request_graph = compile_research_subgraph(
            planner=self.planner,
            aggregator=self.aggregator,
            selector=self.selector,
            synthesizer=self.synthesizer,
            verifier=self.verifier,
            call_budget=budget,
        )

        try:
            async with asyncio.timeout(deadline):
                final_state = await request_graph.ainvoke(initial_state)

        except TimeoutError as exc:
            logger.error("Research request exceeded global deadline of %ss for project %s", deadline, project_id)
            raise TimeoutError(f"Research request exceeded global deadline of {deadline}s") from exc

        claims = [ResearchClaim.model_validate(c) for c in final_state.get("verified_claims", [])]
        citations = [VerifiedCitation.model_validate(c) for c in final_state.get("verified_citations", [])]
        execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        llm_calls = budget.used_calls

        metadata = ResearchMetadata(
            model=getattr(settings, "llm_model", "gpt-4o-mini"),
            subqueries_executed=final_state.get("subqueries", [request.question]),
            total_evidence_retrieved=len(final_state.get("retrieved_evidence", [])),
            verified_citations_count=len(citations),
            execution_time_ms=execution_time_ms,
            llm_call_count=llm_calls,
            repair_count=final_state.get("repair_count", 0),
        )

        raw_status = final_state.get("status", ResearchStatus.INSUFFICIENT_EVIDENCE.value)
        status = (
            ResearchStatus.COMPLETED
            if raw_status == ResearchStatus.COMPLETED.value
            else ResearchStatus.INSUFFICIENT_EVIDENCE
        )

        answer = final_state.get("answer") or CANONICAL_INSUFFICIENT_EVIDENCE_ANSWER

        return ResearchResponse(
            question=request.question,
            status=status,
            answer=answer,
            claims=claims,
            citations=citations,
            evidence_count=len(citations),
            metadata=metadata,
        )
