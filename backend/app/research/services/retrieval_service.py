import logging
from typing import Optional
from sqlalchemy.orm import Session

from app.research.chunking.normalizer import TextNormalizer
from app.research.embeddings.base import EmbeddingProvider
from app.research.embeddings.provider import get_embedding_provider
from app.research.exceptions import ProviderUnavailableError
from app.research.retrieval.base import (
    DenseRetriever,
    HybridFusionEngine,
    Reranker,
    SparseRetriever,
)
from app.research.retrieval.citation import CitationAnchorBuilder
from app.research.retrieval.dedup import ChunkDeduplicator
from app.research.retrieval.dense import QdrantDenseRetriever
from app.research.retrieval.fusion import ReciprocalRankFusion
from app.research.retrieval.rerank import get_reranker
from app.research.retrieval.schemas import (
    RetrievalResponse,
    SearchMode,
    SearchQuery,
    SearchResultChunk,
)
from app.research.retrieval.sparse import BM25SparseRetriever
from app.research.vectorstore.qdrant import QdrantVectorStore

logger = logging.getLogger(__name__)


class RetrievalService:
    """
    Coordinates project-scoped hybrid retrieval across query normalization, dense retrieval,
    sparse BM25 retrieval, Reciprocal Rank Fusion, deduplication, optional reranking,
    and citation provenance enrichment.

    Safeguards:
    - Bounded retry and graceful degradation to independent BM25 on dense provider failure (e.g. 503).
    - Strict no-hallucination guard: if dense fails and sparse yields no candidates, returns
      a structured degraded-service error response with zero citations.
    """

    def __init__(
        self,
        db: Session,
        vector_store: Optional[QdrantVectorStore] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
        dense_retriever: Optional[DenseRetriever] = None,
        sparse_retriever: Optional[SparseRetriever] = None,
        fusion_engine: Optional[HybridFusionEngine] = None,
        reranker: Optional[Reranker] = None,
        deduplicator: Optional[ChunkDeduplicator] = None,
        citation_builder: Optional[CitationAnchorBuilder] = None,
        normalizer: Optional[TextNormalizer] = None,
    ) -> None:
        self.db = db
        self.vector_store = vector_store or QdrantVectorStore()
        self.embedding_provider = embedding_provider or get_embedding_provider()
        self.dense_retriever = dense_retriever or QdrantDenseRetriever(
            vector_store=self.vector_store,
            embedding_provider=self.embedding_provider,
        )
        self.sparse_retriever = sparse_retriever or BM25SparseRetriever(
            vector_store=self.vector_store,
        )
        self.fusion_engine = fusion_engine or ReciprocalRankFusion()
        self.reranker = reranker or get_reranker(enabled=False)
        self.deduplicator = deduplicator or ChunkDeduplicator()
        self.citation_builder = citation_builder or CitationAnchorBuilder(self.db)
        self.normalizer = normalizer or TextNormalizer()

    async def search(
        self,
        project_id: int,
        query_input: SearchQuery,
    ) -> RetrievalResponse:
        """
        Executes bounded, authenticated project search and returns structured citation evidence.
        """
        # 1. Canonical Unicode NFC query normalization
        norm_query = self.normalizer.normalize(query_input.query).strip()
        if not norm_query:
            raise ValueError("Search query cannot be empty or whitespace only")

        # 2. Overfetch candidate pool for fusion and deduplication
        candidate_k = max(query_input.limit * 3, 20)

        # 3. Retrieve candidates according to selected mode
        degraded_mode = False
        candidates: list[SearchResultChunk] = []

        if query_input.mode == SearchMode.DENSE:
            try:
                candidates = await self.dense_retriever.search(
                    project_id=project_id,
                    query=norm_query,
                    limit=candidate_k,
                    document_ids=query_input.document_ids,
                )
            except ProviderUnavailableError as exc:
                logger.warning(
                    "Dense embedding service unavailable (503). Attempting independent sparse BM25 retrieval: %s",
                    exc,
                )
                degraded_mode = True
                try:
                    candidates = await self.sparse_retriever.search(
                        project_id=project_id,
                        query=norm_query,
                        limit=candidate_k,
                        document_ids=query_input.document_ids,
                    )
                except Exception as sparse_exc:
                    logger.warning("Sparse retrieval fallback also failed: %s", sparse_exc)
                    candidates = []

        elif query_input.mode == SearchMode.SPARSE:
            candidates = await self.sparse_retriever.search(
                project_id=project_id,
                query=norm_query,
                limit=candidate_k,
                document_ids=query_input.document_ids,
            )

        elif query_input.mode == SearchMode.HYBRID:
            dense_res: list[SearchResultChunk] = []
            try:
                dense_res = await self.dense_retriever.search(
                    project_id=project_id,
                    query=norm_query,
                    limit=candidate_k,
                    document_ids=query_input.document_ids,
                )
            except ProviderUnavailableError as exc:
                logger.warning(
                    "Dense embedding service unavailable (503). Attempting independent sparse BM25 retrieval: %s",
                    exc,
                )
                dense_res = []
                degraded_mode = True

            sparse_res: list[SearchResultChunk] = []
            try:
                sparse_res = await self.sparse_retriever.search(
                    project_id=project_id,
                    query=norm_query,
                    limit=candidate_k,
                    document_ids=query_input.document_ids,
                )
            except Exception as sparse_exc:
                logger.warning("Sparse retrieval failed: %s", sparse_exc)
                sparse_res = []

            if degraded_mode:
                # Dense failed; rely purely on independent sparse BM25 candidates
                candidates = sparse_res
            else:
                candidates = self.fusion_engine.fuse(
                    dense_results=dense_res,
                    sparse_results=sparse_res,
                    limit=candidate_k,
                    dense_weight=query_input.dense_weight,
                    sparse_weight=query_input.sparse_weight,
                )

        # No-hallucination safeguard: if dense failed and sparse yielded zero candidates,
        # fail safe with structured degraded response and ZERO fabricated citations
        if degraded_mode and not candidates:
            return RetrievalResponse(
                status="degraded_unavailable",
                query=query_input.query,
                total_results=0,
                mode=query_input.mode.value,
                results=[],
                degraded_mode=True,
                error_message="Dense embedding service unavailable (503) and independent sparse retrieval produced no verified evidence.",
            )

        # 4. Apply conservative deduplication
        candidates = self.deduplicator.deduplicate_chunks(candidates)

        # 5. Apply optional reranking
        if query_input.rerank and candidates:
            try:
                active_reranker = self.reranker or get_reranker(enabled=True)
                candidates = await active_reranker.rerank(
                    query=norm_query,
                    candidates=candidates,
                    limit=query_input.limit,
                )
            except Exception as r_exc:
                logger.warning("Reranking failed; falling back to unranked candidates: %s", r_exc)
                candidates = candidates[: query_input.limit]
        else:
            candidates = candidates[: query_input.limit]

        # 6. Build citation-ready provenance evidence
        citations = self.citation_builder.build_citations(candidates, project_id=project_id)

        return RetrievalResponse(
            query=query_input.query,
            total_results=len(citations),
            mode=query_input.mode.value,
            results=citations,
            status="ok",
            degraded_mode=degraded_mode,
            error_message=(
                "Dense retrieval unavailable; results retrieved via independent BM25 sparse index."
                if degraded_mode
                else None
            ),
        )
