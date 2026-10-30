from typing import List


def compute_citation_precision(cited_chunk_ids: List[str], expected_chunk_ids: List[str]) -> float:
    """
    Measures the fraction of cited chunks in the answer that reference expected evidence.
    Zero-denominator guard: If zero citations emitted and zero expected -> 1.0;
    if zero emitted and expected > 0 -> 0.0.
    """
    if not cited_chunk_ids:
        return 1.0 if not expected_chunk_ids else 0.0
    exp_set = set(expected_chunk_ids)
    valid_citations = sum(1 for cid in cited_chunk_ids if cid in exp_set)
    return valid_citations / len(cited_chunk_ids)


def compute_claim_grounding_rate(total_generated_claims: int, verified_claims_count: int) -> float:
    """
    Fraction of draft claims that were deterministically verified against relational evidence.
    Zero-denominator guard: If total generated claims is zero (e.g. valid refusal) -> 1.0.
    """
    if total_generated_claims <= 0:
        return 1.0
    return min(1.0, max(0.0, verified_claims_count / total_generated_claims))


def compute_benchmark_hallucination_rate(total_generated_claims: int, stripped_claims_count: int) -> float:
    """
    Fraction of draft claims that were stripped during verification due to ungrounded citations.
    Operationally defined as: stripped_claims / total_generated_claims (or 1.0 - claim_grounding_rate).
    """
    if total_generated_claims <= 0:
        return 0.0
    return min(1.0, max(0.0, stripped_claims_count / total_generated_claims))


def compute_rag_faithfulness(final_claims_count: int, grounded_final_claims_count: int) -> float:
    """
    Measures whether all claims appearing in the final research answer are grounded.
    """
    if final_claims_count <= 0:
        return 1.0
    return min(1.0, max(0.0, grounded_final_claims_count / final_claims_count))
