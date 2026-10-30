import time
from typing import Dict, List, Set

from app.evaluations.evaluators.base import BaseEvaluator
from app.evaluations.metrics.grounding import (
    compute_benchmark_hallucination_rate,
    compute_citation_precision,
    compute_claim_grounding_rate,
    compute_rag_faithfulness,
)
from app.evaluations.schemas import EvaluationCaseResultResponse, GoldenCase


class ResearchEvaluator(BaseEvaluator):
    """
    Evaluates research answer grounding, citation validity, and refusal correctness
    against candidate evidence fixtures.
    """

    async def evaluate_case(self, case: GoldenCase, run_id: str = "") -> EvaluationCaseResultResponse:
        t0 = time.perf_counter()

        evidence_pool = list(case.input_data.get("evidence_pool", []))
        draft = dict(case.input_data.get("draft_answer", {}))
        claims = list(draft.get("claims", []))
        has_sufficient = bool(draft.get("has_sufficient_evidence", True))

        valid_chunk_ids: Set[str] = {c.get("chunk_id", "") for c in evidence_pool if c.get("chunk_id")}
        expected_citations = list(case.ground_truth.get("expected_citations", []))

        # Evaluate claim survival and citations
        verified_claims: List[Dict] = []
        stripped_claims: List[Dict] = []
        all_cited_ids: List[str] = []

        for claim in claims:
            evidence_ids = claim.get("supporting_evidence_ids", [])
            all_cited_ids.extend(evidence_ids)
            # A claim is verified only if all supporting evidence IDs exist in evidence pool
            if evidence_ids and all(eid in valid_chunk_ids for eid in evidence_ids):
                verified_claims.append(claim)
            else:
                stripped_claims.append(claim)

        # Ground truth expectations
        expect_sufficient = bool(case.ground_truth.get("expect_sufficient_evidence", True))
        expect_refusal = bool(case.ground_truth.get("expect_canonical_refusal", False))
        min_grounded = int(case.ground_truth.get("min_grounded_claims", 0))
        max_stripped = int(case.ground_truth.get("max_stripped_claims", 100))

        # Metric calculations
        total_claims_count = len(claims)
        verified_count = len(verified_claims)
        stripped_count = len(stripped_claims)

        cit_precision = compute_citation_precision(all_cited_ids, expected_citations)
        grounding_rate = compute_claim_grounding_rate(total_claims_count, verified_count)
        hallucination_rate = compute_benchmark_hallucination_rate(total_claims_count, stripped_count)
        faithfulness = compute_rag_faithfulness(verified_count, verified_count)

        refusal_accurate = 1.0 if (not has_sufficient or verified_count == 0) == expect_refusal else 0.0

        duration_ms = (time.perf_counter() - t0) * 1000.0

        # Pass condition: meets grounding/stripped limits and refusal accuracy
        passed = (
            verified_count >= min_grounded
            and stripped_count <= max_stripped
            and refusal_accurate == 1.0
        )

        failure_reason = None
        if not passed:
            if verified_count < min_grounded:
                failure_reason = f"Grounded claims ({verified_count}) below expected minimum ({min_grounded})"
            elif stripped_count > max_stripped:
                failure_reason = f"Stripped claims ({stripped_count}) exceeded maximum allowed ({max_stripped})"
            elif refusal_accurate != 1.0:
                failure_reason = "Refusal behavior did not match ground truth expectation"

        return EvaluationCaseResultResponse(
            id=0,
            run_id=run_id,
            case_id=case.case_id,
            status="passed" if passed else "failed",
            duration_ms=duration_ms,
            metrics={
                "citation_precision": cit_precision,
                "claim_grounding_rate": grounding_rate,
                "benchmark_hallucination_rate": hallucination_rate,
                "rag_faithfulness": faithfulness,
                "refusal_accuracy": refusal_accurate,
            },
            failure_reason=failure_reason,
            details={
                "total_claims": total_claims_count,
                "verified_claims": verified_count,
                "stripped_claims": stripped_count,
                "refusal_accurate": bool(refusal_accurate == 1.0),
            },
        )
