from typing import List


def compute_recall_at_k(retrieved_ids: List[str], relevant_ids: List[str], k: int = 5) -> float:
    """
    Measures the fraction of relevant chunks captured in the top-k results.
    Zero-denominator guard: If no relevant chunks exist, returns 1.0 if retriever returned nothing, else 0.0.
    """
    if not relevant_ids:
        return 1.0 if not retrieved_ids else 0.0
    top_k = set(retrieved_ids[:k])
    rel_set = set(relevant_ids)
    return len(top_k & rel_set) / len(rel_set)


def compute_precision_at_k(retrieved_ids: List[str], relevant_ids: List[str], k: int = 5) -> float:
    """
    Measures the fraction of top-k results that are genuinely relevant.
    Standard ranking definition: Denominator is fixed at k. Unretrieved items count as non-relevant.
    """
    if k <= 0:
        return 0.0
    top_k = retrieved_ids[:k]
    rel_set = set(relevant_ids)
    relevant_in_top_k = sum(1 for doc_id in top_k if doc_id in rel_set)
    return relevant_in_top_k / k


def compute_reciprocal_rank(retrieved_ids: List[str], relevant_ids: List[str]) -> float:
    """
    Computes reciprocal rank for an individual case: 1 / rank of first relevant item.
    Returns 0.0 if no relevant chunk is retrieved.
    """
    rel_set = set(relevant_ids)
    for rank, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in rel_set:
            return 1.0 / rank
    return 0.0


def compute_mean_reciprocal_rank(reciprocal_ranks: List[float]) -> float:
    """
    Computes Mean Reciprocal Rank (MRR) across a collection of evaluation cases.
    """
    if not reciprocal_ranks:
        return 0.0
    return sum(reciprocal_ranks) / len(reciprocal_ranks)
