from typing import Optional, Protocol, runtime_checkable

from app.research.retrieval.schemas import SearchResultChunk


@runtime_checkable
class DenseRetriever(Protocol):
    """
    Protocol for project-scoped dense vector retrieval.
    """
    async def search(
        self,
        project_id: int,
        query: str,
        limit: int = 5,
        document_ids: Optional[list[int]] = None,
    ) -> list[SearchResultChunk]:
        ...


@runtime_checkable
class SparseRetriever(Protocol):
    """
    Protocol for project-scoped sparse lexical retrieval.
    """
    async def search(
        self,
        project_id: int,
        query: str,
        limit: int = 5,
        document_ids: Optional[list[int]] = None,
    ) -> list[SearchResultChunk]:
        ...


@runtime_checkable
class HybridFusionEngine(Protocol):
    """
    Protocol for fusing ranked candidate lists from multiple retrieval channels.
    """
    def fuse(
        self,
        dense_results: list[SearchResultChunk],
        sparse_results: list[SearchResultChunk],
        limit: int = 5,
        dense_weight: float = 1.0,
        sparse_weight: float = 1.0,
    ) -> list[SearchResultChunk]:
        ...


@runtime_checkable
class Reranker(Protocol):
    """
    Protocol for secondary candidate reranking.
    """
    async def rerank(
        self,
        query: str,
        candidates: list[SearchResultChunk],
        limit: int = 5,
    ) -> list[SearchResultChunk]:
        ...
