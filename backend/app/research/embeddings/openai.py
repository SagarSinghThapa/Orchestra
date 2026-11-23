from typing import Optional
import httpx

from app.research.embeddings.base import EmbeddingProvider
from app.research.exceptions import ConfigurationError, ResearchPipelineError

MAX_EMBEDDING_BATCH_SIZE = 64


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    """
    OpenAI-compatible embedding provider communicating via HTTP client.

    Default reference configuration:
    - Model: text-embedding-3-small
    - Native dimension: 1536 (Strictly asserted against Qdrant collection)
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: str = "text-embedding-3-small",
        dimension: int = 1536,
        client: Optional[httpx.AsyncClient] = None,
        batch_size: int = MAX_EMBEDDING_BATCH_SIZE,
    ) -> None:
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.api_key = api_key
        self.model = model
        self._dimension = dimension
        self._client = client
        self.batch_size = max(1, batch_size)

    @property
    def dimension(self) -> int:
        return self._dimension

    async def _post_batch(self, batch_texts: list[str]) -> list[list[float]]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "input": batch_texts,
        }
        endpoint = f"{self.base_url}/embeddings"

        if self._client is not None:
            response = await self._client.post(endpoint, json=payload, headers=headers)
        else:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(endpoint, json=payload, headers=headers)

        if response.status_code != 200:
            raise ResearchPipelineError(
                f"Embedding request failed with HTTP status {response.status_code}: {response.text}"
            )

        try:
            data = response.json()
        except Exception as exc:
            raise ResearchPipelineError(f"Failed to parse embedding response JSON: {exc}") from exc

        raw_items = data.get("data", [])
        if not raw_items:
            raise ResearchPipelineError("Embedding provider returned empty data list")

        # Sort embeddings by 'index' to ensure ordering matches inputs
        sorted_items = sorted(raw_items, key=lambda x: x.get("index", 0))
        vectors: list[list[float]] = []

        for item in sorted_items:
            vec = item.get("embedding", [])
            if len(vec) != self._dimension:
                raise ConfigurationError(
                    f"Embedding dimension mismatch: expected {self._dimension}, got {len(vec)}"
                )
            vectors.append(vec)

        return vectors

    async def _post_embeddings(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        all_vectors: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            chunk = texts[i : i + self.batch_size]
            batch_vectors = await self._post_batch(chunk)
            all_vectors.extend(batch_vectors)

        return all_vectors

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._post_embeddings(texts)

    async def embed_query(self, text: str) -> list[float]:
        results = await self._post_embeddings([text])
        return results[0]
