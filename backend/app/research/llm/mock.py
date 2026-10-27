import re
from typing import Optional, Type, TypeVar
from pydantic import BaseModel

from app.research.exceptions import ResearchPipelineError
from app.research.llm.base import LLMProvider

T = TypeVar("T", bound=BaseModel)


class DeterministicTestLLMProvider(LLMProvider):
    """
    Deterministic offline test LLM provider.
    Generates rule-based structured responses and tracks call counts for assertions.
    """

    def __init__(self, mode: str = "normal") -> None:
        self.mode = mode
        self.call_count: int = 0
        self.last_prompt: Optional[str] = None
        self.last_system_prompt: Optional[str] = None

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.0,
    ) -> str:
        self.call_count += 1
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt

        if self.mode == "timeout":
            raise ResearchPipelineError("LLM request timed out after 20.0s")

        return f"Deterministic response to: {prompt[:50]}"

    async def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.0,
    ) -> T:
        self.call_count += 1
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt

        if self.mode == "timeout":
            raise ResearchPipelineError("LLM request timed out after 20.0s")

        if self.mode == "malformed_json":
            raise ResearchPipelineError(
                f"Failed to validate model response as {schema.__name__}: Invalid JSON formatting"
            )

        schema_name = schema.__name__

        if schema_name == "ResearchPlan":
            return self._generate_plan(prompt, schema)

        if schema_name == "DraftResearchAnswer":
            return self._generate_draft_answer(prompt, schema)

        # Fallback generic model instantiation with empty dict or dummy fields
        try:
            return schema.model_validate({})
        except Exception as exc:
            raise ResearchPipelineError(
                f"DeterministicTestLLMProvider could not construct {schema_name}: {exc}"
            ) from exc

    def _generate_plan(self, prompt: str, schema: Type[T]) -> T:
        # Extract question if inside <USER_QUESTION> tags or take prompt
        match = re.search(r"<USER_QUESTION>(.*?)</USER_QUESTION>", prompt, re.DOTALL)
        question = match.group(1).strip() if match else prompt.strip()

        subqueries = [
            question,
            f"{question} key concepts",
            f"{question} evaluation and results",
        ]

        data = {
            "goal": f"Research inquiry: {question[:100]}",
            "subqueries": subqueries[:3],
            "strategy_notes": "Decomposed into conceptual and empirical subqueries.",
        }
        return schema.model_validate(data)

    def _generate_draft_answer(self, prompt: str, schema: Type[T]) -> T:
        if self.mode == "insufficient_evidence":
            return schema.model_validate({
                "claims": [],
                "summary_notes": "The indexed sources do not contain sufficient evidence.",
                "has_sufficient_evidence": False,
            })

        # Find evidence IDs mentioned in the prompt
        evidence_ids = re.findall(r'id="(evidence_\d+)"', prompt)

        if self.mode == "hallucinated_citations":
            # Cite an evidence ID that was NOT provided
            return schema.model_validate({
                "claims": [
                    {
                        "claim_text": "This fact references a nonexistent citation.",
                        "supporting_evidence_ids": ["evidence_9999"],
                    }
                ],
                "summary_notes": "Draft with hallucinated citation ID.",
                "has_sufficient_evidence": True,
            })

        if self.mode == "unsupported_claim":
            return schema.model_validate({
                "claims": [
                    {
                        "claim_text": "This factual claim has zero citations.",
                        "supporting_evidence_ids": [],
                    }
                ],
                "summary_notes": "Draft with unsupported claim.",
                "has_sufficient_evidence": True,
            })

        # Normal mode: cite the first available evidence IDs
        if not evidence_ids:
            return schema.model_validate({
                "claims": [],
                "summary_notes": "No evidence chunks supplied.",
                "has_sufficient_evidence": False,
            })

        primary_id = evidence_ids[0]
        secondary_id = evidence_ids[1] if len(evidence_ids) > 1 else primary_id

        claims = [
            {
                "claim_text": "The research findings demonstrate strong empirical performance.",
                "supporting_evidence_ids": [primary_id],
            },
            {
                "claim_text": "The platform architecture guarantees verified provenance.",
                "supporting_evidence_ids": [secondary_id],
            },
        ]

        return schema.model_validate({
            "claims": claims,
            "summary_notes": "Synthesized grounded answer based on supplied evidence.",
            "has_sufficient_evidence": True,
        })
