from typing import Optional

from app.research.embeddings.base import EmbeddingProvider
from app.research.retrieval.base import DenseRetriever
from app.research.retrieval.schemas import SearchResultChunk
from app.research.vectorstore.qdrant import QdrantVectorStore


class QdrantDenseRetriever(DenseRetriever):
    """
    Project-scoped dense vector retrieval utilizing QdrantVectorStore and EmbeddingProvider.
    """

    def __init__(
        self,
        vector_store: QdrantVectorStore,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider

    async def search(
        self,
        project_id: int,
        query: str,
        limit: int = 5,
        document_ids: Optional[list[int]] = None,
    ) -> list[SearchResultChunk]:
        if not query or not query.strip():
            return []

        # Generate query embedding vector
        query_vector = await self.embedding_provider.embed_query(query.strip())

        # Perform project-isolated search in Qdrant
        points = await self.vector_store.search(
            project_id=project_id,
            query_vector=query_vector,
            limit=limit,
            document_ids=document_ids,
        )

        results: list[SearchResultChunk] = []
        for rank, pt in enumerate(points, 1):
            p = pt.payload or {}
            score = float(pt.score)
            results.append(
                SearchResultChunk(
                    chunk_id=p.get("chunk_id", str(pt.id)),
                    document_id=p["document_id"],
                    project_id=p["project_id"],
                    text=p["text"],
                    chunk_index=p.get("chunk_index", 0),
                    page_number=p.get("page_number", 1),
                    start_char=p.get("start_char", 0),
                    end_char=p.get("end_char", len(p["text"])),
                    score=score,
                    source_engine="dense",
                    dense_score=score,
                    dense_rank=rank,
                )
            )

        return results
