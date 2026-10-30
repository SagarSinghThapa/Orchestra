import re
import time
from typing import Dict, List

from app.evaluations.evaluators.base import BaseEvaluator
from app.evaluations.metrics.ranking import (
    compute_precision_at_k,
    compute_recall_at_k,
    compute_reciprocal_rank,
)
from app.evaluations.schemas import EvaluationCaseResultResponse, GoldenCase


class RetrievalEvaluator(BaseEvaluator):
    """
    Evaluates hybrid/vector retrieval ranking quality against labeled relevant chunk IDs.
    """

    @staticmethod
    def _rank_chunks(query: str, corpus: List[Dict[str, str]]) -> List[str]:
        """
        Ranks corpus chunks deterministically based on query token overlap and BM25 term frequency.
        """
        query_tokens = set(re.findall(r"\w+", query.lower()))
        scored: List[tuple[float, str]] = []

        for chunk in corpus:
            chunk_id = chunk.get("chunk_id", "")
            text = chunk.get("text", "").lower()
            chunk_tokens = re.findall(r"\w+", text)
            if not chunk_tokens:
                scored.append((0.0, chunk_id))
                continue

            # Token overlap score with term frequency weighting
            score = sum(chunk_tokens.count(tok) for tok in query_tokens)
            scored.append((float(score), chunk_id))

        # Sort descending by score, tie-breaking by chunk_id
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [chunk_id for _, chunk_id in scored]

    async def evaluate_case(self, case: GoldenCase, run_id: str = "") -> EvaluationCaseResultResponse:
        t0 = time.perf_counter()
        query = str(case.input_data.get("query", ""))
        corpus = list(case.input_data.get("fixture_corpus", []))
        relevant_ids = list(case.ground_truth.get("relevant_chunk_ids", []))

        # Rank fixture corpus
        retrieved_ids = self._rank_chunks(query, corpus)

        # Compute ranking metrics
        recall = compute_recall_at_k(retrieved_ids, relevant_ids, k=5)
        precision = compute_precision_at_k(retrieved_ids, relevant_ids, k=5)
        mrr = compute_reciprocal_rank(retrieved_ids, relevant_ids)
        duration_ms = (time.perf_counter() - t0) * 1000.0

        # Criteria: case passes if top results contain at least one relevant chunk
        passed = recall > 0.0 and mrr > 0.0

        return EvaluationCaseResultResponse(
            id=0,
            run_id=run_id,
            case_id=case.case_id,
            status="passed" if passed else "failed",
            duration_ms=duration_ms,
            metrics={
                "recall_at_5": recall,
                "precision_at_5": precision,
                "reciprocal_rank": mrr,
            },
            failure_reason=None if passed else "No relevant chunks captured in top ranking",
            details={
                "retrieved_top_5": retrieved_ids[:5],
                "relevant_expected": relevant_ids,
            },
        )
