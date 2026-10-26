from typing import Optional
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import AsyncQdrantClient, models

from app.core.config import settings
from app.research.chunking.base import DocumentChunk
from app.research.exceptions import ConfigurationError, VectorStoreError


class QdrantVectorStore:
    """
    Qdrant vector database storage manager.
    
    Guarantees:
    - Lazy client initialization: application imports are 100% side-effect free (no network calls on import).
    - Dynamic dimension enforcement: creates collections with dynamic provider dimension and rejects dimension mismatches.
    - Tenant defense-in-depth: vector IDs are deterministic UUID v5 with explicit tenant context:
      uuid5(NAMESPACE_URL, f"proj_{project_id}_doc_{document_id}_chk_{chunk_index}").
    - Strict tenant scoping: all searches and deletions enforce project_id filters.
    """

    def __init__(
        self,
        client: Optional[AsyncQdrantClient] = None,
        location: Optional[str] = None,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        collection_name: Optional[str] = None,
    ) -> None:
        self._client = client
        self._location = location
        self.url = url or settings.qdrant_url
        self.api_key = api_key or settings.qdrant_api_key
        self.collection_name = collection_name or settings.qdrant_collection_name

    async def _get_client(self) -> AsyncQdrantClient:
        if self._client is None:
            if self._location == ":memory:":
                self._client = AsyncQdrantClient(location=":memory:")
            else:
                self._client = AsyncQdrantClient(url=self.url, api_key=self.api_key)
        return self._client

    async def close(self) -> None:
        """Close connection to Qdrant if open."""
        if self._client is not None:
            await self._client.close()
            self._client = None

    async def ensure_collection(self, dimension: int) -> None:
        """
        Dynamically ensure that the Qdrant collection exists and has matching vector dimensions.
        Raises ConfigurationError on dimension mismatch without destroying or corrupting data.
        """
        client = await self._get_client()

        try:
            exists = await client.collection_exists(self.collection_name)
        except Exception as exc:
            raise VectorStoreError(f"Failed to check Qdrant collection '{self.collection_name}': {exc}") from exc

        if not exists:
            try:
                await client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=dimension,
                        distance=models.Distance.COSINE,
                    ),
                )
            except Exception as exc:
                raise VectorStoreError(
                    f"Failed to create Qdrant collection '{self.collection_name}': {exc}"
                ) from exc
        else:
            try:
                info = await client.get_collection(self.collection_name)
            except Exception as exc:
                raise VectorStoreError(
                    f"Failed to retrieve Qdrant collection '{self.collection_name}' info: {exc}"
                ) from exc

            vectors_config = info.config.params.vectors
            if hasattr(vectors_config, "size"):
                existing_size = vectors_config.size
            elif isinstance(vectors_config, dict) and "" in vectors_config:
                existing_size = vectors_config[""].size
            elif isinstance(vectors_config, dict) and vectors_config:
                existing_size = next(iter(vectors_config.values())).size
            else:
                existing_size = None

            if existing_size != dimension:
                raise ConfigurationError(
                    f"Qdrant collection '{self.collection_name}' has vector dimension {existing_size}, "
                    f"but embedding provider is configured for dimension {dimension}. "
                    "Changing embedding model or dimension requires explicit collection re-indexing or migration."
                )

    async def upsert_chunks(
        self,
        chunks: list[DocumentChunk],
        vectors: list[list[float]],
    ) -> None:
        """
        Upserts document chunks and their embedding vectors with tenant-scoped UUID v5 IDs.
        """
        if not chunks:
            return

        if len(chunks) != len(vectors):
            raise ConfigurationError(
                f"Chunks count ({len(chunks)}) does not match vectors count ({len(vectors)})"
            )

        client = await self._get_client()
        points: list[models.PointStruct] = []

        for chunk, vector in zip(chunks, vectors):
            point_id = str(
                uuid5(
                    NAMESPACE_URL,
                    f"proj_{chunk.project_id}_doc_{chunk.document_id}_chk_{chunk.chunk_index}",
                )
            )
            payload = {
                "project_id": chunk.project_id,
                "document_id": chunk.document_id,
                "chunk_id": chunk.chunk_id,
                "chunk_index": chunk.chunk_index,
                "page_number": chunk.page_number,
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
                "text": chunk.text,
            }
            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            )

        try:
            await client.upsert(
                collection_name=self.collection_name,
                points=points,
            )
        except Exception as exc:
            raise VectorStoreError(
                f"Failed to upsert {len(points)} points into Qdrant collection '{self.collection_name}': {exc}"
            ) from exc

    async def delete_document_vectors(self, project_id: int, document_id: int) -> None:
        """
        Purges all vectors belonging to a specific document under a project.
        Idempotent: missing vectors do not raise an error.
        On network/database failures, raises VectorStoreError.
        """
        client = await self._get_client()
        filter_criteria = models.Filter(
            must=[
                models.FieldCondition(
                    key="project_id",
                    match=models.MatchValue(value=project_id),
                ),
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchValue(value=document_id),
                ),
            ]
        )

        try:
            if not await client.collection_exists(self.collection_name):
                return
            await client.delete(
                collection_name=self.collection_name,
                points_selector=filter_criteria,
            )
        except Exception as exc:
            raise VectorStoreError(
                f"Failed to delete document vectors for project {project_id}, document {document_id}: {exc}"
            ) from exc

    async def search(
        self,
        project_id: int,
        query_vector: list[float],
        limit: int = 5,
        document_ids: Optional[list[int]] = None,
    ) -> list[models.ScoredPoint]:
        """
        Searches vectors enforcing strict project-level isolation and optional document filtering.
        """
        client = await self._get_client()
        if not await client.collection_exists(self.collection_name):
            return []

        must_conditions: list[models.Condition] = [
            models.FieldCondition(
                key="project_id",
                match=models.MatchValue(value=project_id),
            ),
        ]
        if document_ids:
            must_conditions.append(
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchAny(any=document_ids),
                )
            )

        filter_criteria = models.Filter(must=must_conditions)

        try:
            if hasattr(client, "query_points"):
                response = await client.query_points(
                    collection_name=self.collection_name,
                    query=query_vector,
                    query_filter=filter_criteria,
                    limit=limit,
                )
                return response.points
            else:
                return await client.search(
                    collection_name=self.collection_name,
                    query_vector=query_vector,
                    query_filter=filter_criteria,
                    limit=limit,
                )
        except Exception as exc:
            raise VectorStoreError(
                f"Failed to search Qdrant collection '{self.collection_name}': {exc}"
            ) from exc

    async def scroll_project_chunks(
        self,
        project_id: int,
        document_ids: Optional[list[int]] = None,
        batch_size: int = 100,
    ) -> list[DocumentChunk]:
        """
        Retrieves all indexed chunks for a given project via cursor pagination until exhaustion.
        Enforces project tenant isolation and safety bounds to prevent memory starvation.
        """
        client = await self._get_client()
        if not await client.collection_exists(self.collection_name):
            return []
        must_conditions: list[models.Condition] = [
            models.FieldCondition(
                key="project_id",
                match=models.MatchValue(value=project_id),
            ),
        ]
        if document_ids:
            must_conditions.append(
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchAny(any=document_ids),
                )
            )

        filter_criteria = models.Filter(must=must_conditions)
        chunks: list[DocumentChunk] = []
        offset = None

        try:
            while True:
                records, next_offset = await client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=filter_criteria,
                    limit=batch_size,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )

                for rec in records:
                    p = rec.payload or {}
                    chunks.append(
                        DocumentChunk(
                            chunk_id=p.get("chunk_id", str(rec.id)),
                            document_id=p["document_id"],
                            project_id=p["project_id"],
                            text=p["text"],
                            chunk_index=p.get("chunk_index", 0),
                            page_number=p.get("page_number", 1),
                            start_char=p.get("start_char", 0),
                            end_char=p.get("end_char", len(p["text"])),
                            token_count=p.get("token_count", max(1, len(p["text"]) // 4)),
                        )
                    )

                    if len(chunks) > settings.retrieval_max_project_chunks:
                        raise VectorStoreError(
                            f"Project {project_id} exceeds maximum chunk limit of {settings.retrieval_max_project_chunks} chunks."
                        )

                if next_offset is None or not records:
                    break
                offset = next_offset

            return chunks
        except VectorStoreError:
            raise
        except Exception as exc:
            raise VectorStoreError(
                f"Failed to scroll chunks for project {project_id} from Qdrant: {exc}"
            ) from exc

