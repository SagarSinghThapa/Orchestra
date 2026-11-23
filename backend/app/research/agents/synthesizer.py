import logging
from typing import Optional, TYPE_CHECKING

from app.research.exceptions import ResearchPipelineError
from app.research.llm.base import LLMProvider
from app.research.llm.budget import LLMCallBudget, LLMCallBudgetExceededError
from app.research.prompts.synthesizer import (
    SYNTHESIS_SYSTEM_PROMPT,
    build_synthesis_user_prompt,
)
from app.research.schemas import DraftResearchAnswer

if TYPE_CHECKING:
    from app.research.agents.aggregator import AggregatedEvidence

logger = logging.getLogger(__name__)


class ResearchSynthesizer:
    """
    Synthesizes claim-grounded draft answers using request-local evidence IDs.
    Enforces prompt injection containment and bounded repair retry behavior.
    """

    def __init__(self, llm_provider: LLMProvider) -> None:
        self.llm_provider = llm_provider

    async def synthesize(
        self,
        question: str,
        evidence: list["AggregatedEvidence"],
        call_budget: Optional[LLMCallBudget] = None,
    ) -> DraftResearchAnswer:
        """
        Executes grounded synthesis against selected evidence chunks.
        Falls back to insufficient evidence if evidence is empty or synthesis fails after 1 retry.
        Enforces runtime LLM call budget across initial and retry attempts.
        """
        if not evidence:
            return DraftResearchAnswer(
                claims=[],
                summary_notes="No evidence chunks supplied.",
                has_sufficient_evidence=False,
            )

        prompt = build_synthesis_user_prompt(question=question, evidence_items=evidence)

        try:
            if call_budget:
                call_budget.consume()
            return await self.llm_provider.generate_structured(
                prompt=prompt,
                schema=DraftResearchAnswer,
                system_prompt=SYNTHESIS_SYSTEM_PROMPT,
            )
        except LLMCallBudgetExceededError:
            raise
        except Exception as exc:
            logger.warning("Grounded synthesis initial attempt failed: %s; attempting 1 bounded repair", exc)

            if call_budget and call_budget.remaining <= 0:
                logger.warning("LLM call budget exhausted; skipping synthesis repair retry")
                raise LLMCallBudgetExceededError("LLM call budget exhausted during synthesis retry")

            # Bounded repair retry (max 1 retry)
            repair_prompt = (
                f"{prompt}\n\n"
                f"ATTENTION: Your previous response was malformed or failed validation. "
                f"Please output valid JSON matching the DraftResearchAnswer schema exactly."
            )
            try:
                if call_budget:
                    call_budget.consume()
                return await self.llm_provider.generate_structured(
                    prompt=repair_prompt,
                    schema=DraftResearchAnswer,
                    system_prompt=SYNTHESIS_SYSTEM_PROMPT,
                )
            except LLMCallBudgetExceededError:
                raise
            except Exception as retry_exc:
                logger.error("Grounded synthesis repair retry failed: %s", retry_exc)
                raise ResearchPipelineError(
                    f"Grounded synthesis failed after retry: {retry_exc}"
                ) from retry_exc
