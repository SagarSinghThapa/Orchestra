from typing import Optional

from app.core.config import settings
from app.research.exceptions import ConfigurationError
from app.research.retrieval.base import Reranker
from app.research.retrieval.bm25 import tokenize
from app.research.retrieval.schemas import SearchResultChunk


class PassThroughReranker(Reranker):
    """
    Production default: preserves upstream hybrid candidate ranking unchanged.
    """

    async def rerank(
        self,
        query: str,
        candidates: list[SearchResultChunk],
        limit: int = 5,
    ) -> list[SearchResultChunk]:
        return candidates[:limit]


class DeterministicTestReranker(Reranker):
    """
    Deterministic, offline lexical overlap reranker used for testing and verification.
    Requires no GPU, no PyTorch, and no external network calls.
    """

    async def rerank(
        self,
        query: str,
        candidates: list[SearchResultChunk],
        limit: int = 5,
    ) -> list[SearchResultChunk]:
        if not candidates:
            return []

        q_tokens = set(tokenize(query))
        reranked: list[SearchResultChunk] = []

        for c in candidates:
            c_tokens = set(tokenize(c.text))
            intersection = len(q_tokens.intersection(c_tokens))
            union = len(q_tokens.union(c_tokens)) if (q_tokens or c_tokens) else 1
            jaccard = intersection / union if union > 0 else 0.0

            # Deterministic composite score: 0.2 * original_score + 0.8 * jaccard
            score = 0.2 * c.score + 0.8 * jaccard
            updated = c.model_copy(
                update={
                    "score": score,
                    "rerank_score": score,
                }
            )
            reranked.append(updated)

        reranked.sort(key=lambda c: (-c.score, c.chunk_id))
        return reranked[:limit]


def get_reranker(enabled: bool = False, provider_name: Optional[str] = None) -> Reranker:
    """
    Factory creating the configured Reranker.
    Guarantees production cannot silently use a test-only reranker.
    """
    if provider_name == "test":
        if settings.environment == "production":
            raise ConfigurationError("Deterministic test reranker cannot be enabled in production environment.")
        return DeterministicTestReranker()

    if enabled:
        if settings.environment == "test":
            return DeterministicTestReranker()
        return PassThroughReranker()

    return PassThroughReranker()
