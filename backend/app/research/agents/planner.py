import logging
from typing import Optional

from app.research.chunking.normalizer import TextNormalizer
from app.research.exceptions import ResearchPipelineError
from app.research.llm.base import LLMProvider
from app.research.llm.budget import LLMCallBudget, LLMCallBudgetExceededError
from app.research.prompts.escaping import escape_prompt_data
from app.research.prompts.planner import PLANNER_SYSTEM_PROMPT
from app.research.schemas import ResearchPlan

logger = logging.getLogger(__name__)


class ResearchPlanner:
    """
    Decomposes user research inquiries into 1..4 focused, retrieval-oriented subqueries.
    Enforces strict query count bounds and provides graceful fallback to the original query.
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        normalizer: Optional[TextNormalizer] = None,
    ) -> None:
        self.llm_provider = llm_provider
        self.normalizer = normalizer or TextNormalizer()

    async def plan(
        self,
        question: str,
        max_subqueries: int = 3,
        call_budget: Optional[LLMCallBudget] = None,
    ) -> ResearchPlan:
        """
        Decomposes inquiry into bounded subqueries.
        Guarantees that total subqueries <= clamped_subqueries (max 4 total) and includes the original question.
        Enforces runtime LLM call budget before dispatching generation.
        """
        clean_question = self.normalizer.normalize(question).strip()
        clamped_subqueries = min(max(max_subqueries, 1), 4)

        if not clean_question:
            raise ValueError("Research question cannot be empty or whitespace only")

        safe_question = escape_prompt_data(clean_question)
        prompt = (
            f"<USER_QUESTION>\n{safe_question}\n</USER_QUESTION>\n\n"
            f"Decompose this research inquiry into up to {clamped_subqueries} targeted search subqueries."
        )

        try:
            if call_budget:
                call_budget.consume()

            raw_plan = await self.llm_provider.generate_structured(
                prompt=prompt,
                schema=ResearchPlan,
                system_prompt=PLANNER_SYSTEM_PROMPT,
            )

            # Normalize and deduplicate subqueries case-insensitively
            normalized_queries: list[str] = []
            seen_lower: set[str] = set()

            for sq in raw_plan.subqueries:
                norm = self.normalizer.normalize(sq).strip()
                if norm and norm.lower() not in seen_lower:
                    seen_lower.add(norm.lower())
                    normalized_queries.append(norm)

            # Enforce that the original question is the primary query
            final_subqueries = [clean_question]
            for q in normalized_queries:
                if q.lower() != clean_question.lower():
                    final_subqueries.append(q)
                if len(final_subqueries) >= clamped_subqueries:
                    break

            return ResearchPlan(
                goal=raw_plan.goal or f"Research: {clean_question}",
                subqueries=final_subqueries[:clamped_subqueries],
                strategy_notes=raw_plan.strategy_notes,
            )

        except LLMCallBudgetExceededError:
            raise
        except Exception as exc:
            logger.warning(
                "ResearchPlanner decomposition failed: %s; cleanly falling back to primary query", exc
            )
            return ResearchPlan(
                goal=f"Research: {clean_question}",
                subqueries=[clean_question],
                strategy_notes="Decomposition fallback to primary question.",
            )
