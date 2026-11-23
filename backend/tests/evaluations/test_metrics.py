import difflib
import pytest

from app.evaluations.metrics.ast_safety import (
    evaluate_ast_syntax,
    evaluate_diff_applicability,
    verify_preview_zero_mutation,
    verify_scope_compliance,
)
from app.evaluations.metrics.grounding import (
    compute_benchmark_hallucination_rate,
    compute_citation_precision,
    compute_claim_grounding_rate,
    compute_rag_faithfulness,
)
from app.evaluations.metrics.latency import (
    compute_latency_summary,
    compute_nearest_rank_percentile,
)
from app.evaluations.metrics.ranking import (
    compute_mean_reciprocal_rank,
    compute_precision_at_k,
    compute_recall_at_k,
    compute_reciprocal_rank,
)


def test_ranking_metrics_exact_hand_calculated():
    """Verify Recall@K, Precision@K, and Reciprocal Rank on explicit hand-calculated inputs."""
    retrieved = ["doc_c", "doc_a", "doc_x", "doc_y", "doc_z"]
    relevant = ["doc_a", "doc_b", "doc_c"]

    # In top 5, retrieved items matching relevant are: 'doc_c' (rank 1), 'doc_a' (rank 2) = 2 matches
    recall = compute_recall_at_k(retrieved, relevant, k=5)
    assert recall == pytest.approx(2.0 / 3.0)

    precision = compute_precision_at_k(retrieved, relevant, k=5)
    assert precision == pytest.approx(2.0 / 5.0)

    # First relevant chunk 'doc_c' is at rank 1
    rr = compute_reciprocal_rank(retrieved, relevant)
    assert rr == 1.0

    # Relevant chunk at rank 3
    retrieved_delayed = ["doc_x", "doc_y", "doc_a"]
    rr_delayed = compute_reciprocal_rank(retrieved_delayed, ["doc_a"])
    assert rr_delayed == pytest.approx(1.0 / 3.0)

    # MRR across cases
    mrr = compute_mean_reciprocal_rank([1.0, 0.5, 0.0])
    assert mrr == pytest.approx(1.5 / 3.0)


def test_ranking_metrics_zero_denominators():
    """Verify zero-denominator edge cases in ranking metrics."""
    # Zero relevant and zero retrieved -> 1.0 (correctly empty)
    assert compute_recall_at_k([], [], k=5) == 1.0

    # Zero relevant but retrieved something -> 0.0
    assert compute_recall_at_k(["chk_1"], [], k=5) == 0.0

    # Relevant exists but retrieved nothing -> 0.0
    assert compute_recall_at_k([], ["chk_1"], k=5) == 0.0

    # K is zero
    assert compute_precision_at_k(["chk_1"], ["chk_1"], k=0) == 0.0

    # No relevant retrieved
    assert compute_reciprocal_rank(["chk_a"], ["chk_b"]) == 0.0

    # Empty run MRR
    assert compute_mean_reciprocal_rank([]) == 0.0


def test_grounding_metrics_hand_calculated():
    """Verify citation precision, claim grounding, and hallucination rates."""
    cited = ["chk_1", "chk_2", "chk_3", "chk_fake"]
    expected = ["chk_1", "chk_2", "chk_3"]

    # 3 out of 4 citations are valid
    precision = compute_citation_precision(cited, expected)
    assert precision == 0.75

    # 5 total draft claims, 4 verified, 1 stripped
    grounding_rate = compute_claim_grounding_rate(total_generated_claims=5, verified_claims_count=4)
    assert grounding_rate == 0.8

    hallucination_rate = compute_benchmark_hallucination_rate(total_generated_claims=5, stripped_claims_count=1)
    assert hallucination_rate == 0.2

    # Zero-denominator guard: refusal case (0 claims generated)
    assert compute_claim_grounding_rate(0, 0) == 1.0
    assert compute_benchmark_hallucination_rate(0, 0) == 0.0

    # Citation precision zero-denominators
    assert compute_citation_precision([], []) == 1.0
    assert compute_citation_precision([], ["chk_1"]) == 0.0


def test_ast_syntax_validation():
    """Verify AST validity emits 1.0 on clean Python and 0.0 on SyntaxError."""
    valid_code = "def greet(name: str) -> str:\n    return f'Hello, {name}'\n"
    score, err = evaluate_ast_syntax(valid_code)
    assert score == 1.0
    assert err is None

    invalid_code = "def broken(\n    return 42\n"
    score_inv, err_inv = evaluate_ast_syntax(invalid_code)
    assert score_inv == 0.0
    assert err_inv is not None
    assert "SyntaxError" in err_inv


def test_diff_applicability_reconstruction():
    """Verify deterministic pure-Python diff applicability on matching and mismatched base."""
    base = "line1\nline2\nline3\n"
    new = "line1\nline2_modified\nline3\nline4\n"
    diff = "".join(difflib.unified_diff(base.splitlines(keepends=True), new.splitlines(keepends=True)))

    score, err = evaluate_diff_applicability(base, diff)
    assert score == 1.0
    assert err is None

    # Mismatched base context
    wrong_base = "different1\ndifferent2\ndifferent3\n"
    score_bad, err_bad = evaluate_diff_applicability(wrong_base, diff)
    assert score_bad == 0.0
    assert err_bad is not None
    assert "Hunk" in err_bad or "mismatch" in err_bad


def test_scope_compliance():
    """Verify file modification scope boundaries."""
    # Compliant
    score, err = verify_scope_compliance(["a.py", "b.py"], ["a.py", "b.py", "c.py"])
    assert score == 1.0
    assert err is None

    # Unauthorized path
    score_unauth, err_unauth = verify_scope_compliance(["a.py", "malicious.py"], ["a.py", "b.py"])
    assert score_unauth == 0.0
    assert "exceed allowed" in err_unauth

    # Exceeding 5 files
    too_many = [f"f{i}.py" for i in range(6)]
    score_many, err_many = verify_scope_compliance(too_many, too_many)
    assert score_many == 0.0
    assert "exceeds maximum limit of 5" in err_many


def test_preview_zero_mutation():
    """Verify workspace hash equality check."""
    assert verify_preview_zero_mutation("abc123hash", "abc123hash") == (1.0, None)
    score, err = verify_preview_zero_mutation("abc123hash", "xyz789hash")
    assert score == 0.0
    assert "mutation" in err


def test_nearest_rank_percentiles():
    """Verify nearest-rank percentile algorithm on synthetic durations."""
    durations = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]

    # P50 (rank = ceil(0.50 * 10) = 5 -> index 4 -> 50.0)
    p50 = compute_nearest_rank_percentile(durations, 50.0)
    assert p50 == 50.0

    # P95 (rank = ceil(0.95 * 10) = 10 -> index 9 -> 100.0)
    p95 = compute_nearest_rank_percentile(durations, 95.0)
    assert p95 == 100.0

    summary = compute_latency_summary(durations)
    assert summary["latency_p50_ms"] == 50.0
    assert summary["latency_p95_ms"] == 100.0
    assert summary["latency_mean_ms"] == 55.0
    assert summary["latency_max_ms"] == 100.0
