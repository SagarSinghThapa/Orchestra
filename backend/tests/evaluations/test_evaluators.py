import pytest

from app.evaluations.evaluators import (
    DeveloperASTEvaluator,
    OrchestratorEvaluator,
    ResearchEvaluator,
    RetrievalEvaluator,
)
from app.evaluations.loader import DatasetLoader


@pytest.mark.asyncio
async def test_retrieval_evaluator_golden_cases():
    """Verify RetrievalEvaluator executes against retrieval_golden_v1 cases."""
    ds, _ = DatasetLoader.load_dataset("retrieval_golden_v1.json")
    evaluator = RetrievalEvaluator()

    for case in ds.cases:
        res = await evaluator.evaluate_case(case, run_id="test_ret_run")
        assert res.case_id == case.case_id
        assert res.status == "passed"
        assert res.duration_ms >= 0.0
        assert "recall_at_5" in res.metrics
        assert "precision_at_5" in res.metrics
        assert "reciprocal_rank" in res.metrics
        assert res.metrics["recall_at_5"] > 0.0


@pytest.mark.asyncio
async def test_research_evaluator_golden_cases():
    """Verify ResearchEvaluator executes against research_grounding_v1 cases including refusal."""
    ds, _ = DatasetLoader.load_dataset("research_grounding_v1.json")
    evaluator = ResearchEvaluator()

    for case in ds.cases:
        res = await evaluator.evaluate_case(case, run_id="test_res_run")
        assert res.case_id == case.case_id
        assert res.status == "passed"
        assert res.duration_ms >= 0.0
        assert "citation_precision" in res.metrics
        assert "claim_grounding_rate" in res.metrics
        assert "benchmark_hallucination_rate" in res.metrics

    # Check the specific refusal case
    refusal_case = next(c for c in ds.cases if c.case_id == "res_003")
    res_refusal = await evaluator.evaluate_case(refusal_case, run_id="test_res_run")
    assert res_refusal.metrics["refusal_accuracy"] == 1.0
    assert res_refusal.metrics["claim_grounding_rate"] == 1.0


@pytest.mark.asyncio
async def test_developer_evaluator_golden_cases():
    """Verify DeveloperASTEvaluator evaluates AST, diffs, hash checks in temporary directories."""
    ds, _ = DatasetLoader.load_dataset("developer_ast_v1.json")
    evaluator = DeveloperASTEvaluator()

    for case in ds.cases:
        res = await evaluator.evaluate_case(case, run_id="test_dev_run")
        assert res.case_id == case.case_id
        # Every golden case should pass its assertion against ground truth expectation
        assert res.status == "passed", f"Case {case.case_id} failed: {res.failure_reason}"
        assert res.duration_ms >= 0.0
        assert "ast_syntax_validity" in res.metrics
        assert "patch_applicability" in res.metrics
        assert "preview_zero_mutation" in res.metrics
        assert res.metrics["preview_zero_mutation"] == 1.0


@pytest.mark.asyncio
async def test_orchestrator_evaluator_golden_cases():
    """Verify OrchestratorEvaluator classifies all golden prompts accurately."""
    ds, _ = DatasetLoader.load_dataset("orchestrator_routing_v1.json")
    evaluator = OrchestratorEvaluator()

    for case in ds.cases:
        res = await evaluator.evaluate_case(case, run_id="test_orch_run")
        assert res.case_id == case.case_id
        assert res.status == "passed", f"Case {case.case_id} failed: {res.failure_reason}"
        assert res.metrics["routing_accuracy"] == 1.0
        assert res.metrics["llm_budget_compliance"] == 1.0
        assert res.metrics["context_cap_compliance"] == 1.0
        assert res.duration_ms >= 0.0
