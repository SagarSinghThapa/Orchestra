from typing import Optional

from app.research.retrieval.base import SparseRetriever
from app.research.retrieval.bm25 import BM25Okapi
from app.research.retrieval.schemas import SearchResultChunk
from app.research.vectorstore.qdrant import QdrantVectorStore


class BM25SparseRetriever(SparseRetriever):
    """
    Project-scoped sparse lexical retrieval utilizing BM25Okapi built on-demand
    from Qdrant project chunk payloads.
    """

    def __init__(self, vector_store: QdrantVectorStore) -> None:
        self.vector_store = vector_store

    async def search(
        self,
        project_id: int,
        query: str,
        limit: int = 5,
        document_ids: Optional[list[int]] = None,
    ) -> list[SearchResultChunk]:
        if not query or not query.strip():
            return []

        # 1. Fetch all chunks for this project from Qdrant payloads
        chunks = await self.vector_store.scroll_project_chunks(
            project_id=project_id,
            document_ids=document_ids,
        )

        if not chunks:
            return []

        # 2. Build project BM25 index on the fly
        bm25 = BM25Okapi(chunks)

        # 3. Search and score matching candidates
        matches = bm25.search(query.strip(), limit=limit)

        results: list[SearchResultChunk] = []
        for rank, (chunk, score, _doc_idx) in enumerate(matches, 1):
            results.append(
                SearchResultChunk(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    project_id=chunk.project_id,
                    text=chunk.text,
                    chunk_index=chunk.chunk_index,
                    page_number=chunk.page_number,
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                    score=float(score),
                    source_engine="sparse",
                    sparse_score=float(score),
                    sparse_rank=rank,
                )
            )

        return results
