from typing import Optional

from app.core.config import settings
from app.research.retrieval.base import HybridFusionEngine
from app.research.retrieval.schemas import SearchResultChunk


class ReciprocalRankFusion(HybridFusionEngine):
    """
    Standard Reciprocal Rank Fusion (RRF) combining dense and sparse candidate rankings.
    Formula: score(d) = sum_{m in M} (weight_m / (k + rank_m(d)))
    Ranks are strictly 1-based.
    """

    def __init__(self, rrf_k: Optional[int] = None) -> None:
        self.rrf_k = rrf_k if rrf_k is not None else settings.retrieval_rrf_k

    def fuse(
        self,
        dense_results: list[SearchResultChunk],
        sparse_results: list[SearchResultChunk],
        limit: int = 5,
        dense_weight: float = 1.0,
        sparse_weight: float = 1.0,
    ) -> list[SearchResultChunk]:
        if not dense_results and not sparse_results:
            return []

        # Maps chunk_id -> fused SearchResultChunk copy
        fused_chunks: dict[str, SearchResultChunk] = {}
        # Maps chunk_id -> cumulative RRF score
        rrf_scores: dict[str, float] = {}

        # 1. Accumulate dense candidates
        for rank, chunk in enumerate(dense_results, 1):
            cid = chunk.chunk_id
            rrf_contrib = dense_weight * (1.0 / (self.rrf_k + rank))
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + rrf_contrib

            # Store chunk representation with dense metadata
            fused_chunks[cid] = chunk.model_copy(
                update={
                    "dense_score": chunk.dense_score if chunk.dense_score is not None else chunk.score,
                    "dense_rank": rank,
                    "source_engine": "hybrid",
                }
            )

        # 2. Accumulate sparse candidates
        for rank, chunk in enumerate(sparse_results, 1):
            cid = chunk.chunk_id
            rrf_contrib = sparse_weight * (1.0 / (self.rrf_k + rank))
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + rrf_contrib

            if cid in fused_chunks:
                # Candidate present in both channels
                fused_chunks[cid].sparse_score = (
                    chunk.sparse_score if chunk.sparse_score is not None else chunk.score
                )
                fused_chunks[cid].sparse_rank = rank
            else:
                # Disjoint candidate only present in sparse results
                fused_chunks[cid] = chunk.model_copy(
                    update={
                        "sparse_score": chunk.sparse_score if chunk.sparse_score is not None else chunk.score,
                        "sparse_rank": rank,
                        "source_engine": "hybrid",
                    }
                )

        # 3. Finalize scores on fused chunks
        candidates: list[SearchResultChunk] = []
        for cid, chunk in fused_chunks.items():
            final_score = rrf_scores[cid]
            chunk.score = final_score
            chunk.fusion_score = final_score
            candidates.append(chunk)

        # 4. Sort descending by RRF score with deterministic tie-breaking
        # Primary: fusion_score (desc)
        # Secondary: dense_score if available (desc)
        # Tertiary: chunk_id (asc)
        candidates.sort(
            key=lambda c: (
                -c.score,
                -(c.dense_score if c.dense_score is not None else -1.0),
                c.chunk_id,
            )
        )

        return candidates[:limit]


class WeightedScoreFusion(HybridFusionEngine):
    """
    Min-max normalized score fusion combining dense cosine and sparse BM25 scores linearly.
    """

    def fuse(
        self,
        dense_results: list[SearchResultChunk],
        sparse_results: list[SearchResultChunk],
        limit: int = 5,
        dense_weight: float = 1.0,
        sparse_weight: float = 1.0,
    ) -> list[SearchResultChunk]:
        if not dense_results and not sparse_results:
            return []

        def _min_max_normalize(scores: list[float]) -> dict[int, float]:
            if not scores:
                return {}
            min_s, max_s = min(scores), max(scores)
            if math.isclose(min_s, max_s):
                return {i: 1.0 for i in range(len(scores))}
            return {i: (s - min_s) / (max_s - min_s) for i, s in enumerate(scores)}

        import math

        dense_norm = _min_max_normalize([c.score for c in dense_results])
        sparse_norm = _min_max_normalize([c.score for c in sparse_results])

        fused_chunks: dict[str, SearchResultChunk] = {}
        combined_scores: dict[str, float] = {}

        for idx, chunk in enumerate(dense_results):
            cid = chunk.chunk_id
            s = dense_weight * dense_norm.get(idx, 0.0)
            combined_scores[cid] = combined_scores.get(cid, 0.0) + s
            fused_chunks[cid] = chunk.model_copy(
                update={"dense_score": chunk.score, "source_engine": "hybrid"}
            )

        for idx, chunk in enumerate(sparse_results):
            cid = chunk.chunk_id
            s = sparse_weight * sparse_norm.get(idx, 0.0)
            combined_scores[cid] = combined_scores.get(cid, 0.0) + s
            if cid in fused_chunks:
                fused_chunks[cid].sparse_score = chunk.score
            else:
                fused_chunks[cid] = chunk.model_copy(
                    update={"sparse_score": chunk.score, "source_engine": "hybrid"}
                )

        candidates: list[SearchResultChunk] = []
        for cid, chunk in fused_chunks.items():
            final_s = combined_scores[cid]
            chunk.score = final_s
            chunk.fusion_score = final_s
            candidates.append(chunk)

        candidates.sort(key=lambda c: (-c.score, c.chunk_id))
        return candidates[:limit]
