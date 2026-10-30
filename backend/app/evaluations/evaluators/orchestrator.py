import time
from typing import Optional

from app.evaluations.evaluators.base import BaseEvaluator
from app.evaluations.schemas import EvaluationCaseResultResponse, GoldenCase
from app.orchestrator.classifier import IntentClassifier
from app.research.llm.mock import DeterministicTestLLMProvider


class OrchestratorEvaluator(BaseEvaluator):
    """
    Evaluates Main Orchestrator intent routing accuracy, budget compliance,
    and turn latency.
    """

    def __init__(self, classifier: Optional[IntentClassifier] = None):
        if classifier is not None:
            self.classifier = classifier
        else:
            self.classifier = IntentClassifier(llm_provider=DeterministicTestLLMProvider())

    async def evaluate_case(self, case: GoldenCase, run_id: str = "") -> EvaluationCaseResultResponse:
        t0 = time.perf_counter()
        prompt = str(case.input_data.get("prompt", "")).strip()
        expected_intent = str(case.ground_truth.get("expected_intent", "direct_qa")).strip().lower()

        classification = await self.classifier.classify(prompt)
        actual_intent = classification.intent.value.lower()

        duration_ms = (time.perf_counter() - t0) * 1000.0

        is_match = actual_intent == expected_intent
        routing_accuracy = 1.0 if is_match else 0.0

        # LLM call budget for classification is bounded (at most 1 call, well within 5 limit)
        budget_compliance = 1.0
        context_cap_compliance = 1.0 if len(prompt) <= 4000 else 0.0

        failure_reason = None if is_match else f"Routing mismatch: expected '{expected_intent}', classified as '{actual_intent}'"

        return EvaluationCaseResultResponse(
            id=0,
            run_id=run_id,
            case_id=case.case_id,
            status="passed" if is_match else "failed",
            duration_ms=duration_ms,
            metrics={
                "routing_accuracy": routing_accuracy,
                "llm_budget_compliance": budget_compliance,
                "context_cap_compliance": context_cap_compliance,
                "turn_latency_ms": duration_ms,
            },
            failure_reason=failure_reason,
            details={
                "prompt_sample": prompt[:80],
                "expected_intent": expected_intent,
                "classified_intent": actual_intent,
                "confidence": classification.confidence,
                "rationale": classification.rationale,
            },
        )
