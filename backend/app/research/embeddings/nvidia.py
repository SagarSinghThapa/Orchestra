import asyncio
import logging
import random
import time
from typing import Optional
import httpx

from app.research.embeddings.base import EmbeddingProvider
from app.research.exceptions import (
    AuthenticationError,
    ConfigurationError,
    LLMTimeoutError,
    ProviderUnavailableError,
    RateLimitError,
    ResearchPipelineError,
)

logger = logging.getLogger(__name__)

MAX_NVIDIA_EMBEDDING_BATCH_SIZE = 64
DEFAULT_NVIDIA_EMBEDDING_MODEL = "nvidia/nemotron-3.5-embed-1b"
DEFAULT_NVIDIA_EMBEDDING_DIMENSION = 2048
DEFAULT_NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"


class NVIDIAEmbeddingProvider(EmbeddingProvider):
    """
    NVIDIA NIM semantic embedding provider communicating via HTTP client.

    Guarantees:
    - Text semantic embeddings for document indexing (input_type="passage").
    - Text semantic embeddings for retrieval queries (input_type="query").
    - Bounded request timeouts with jittered backoff on transient errors.
    - Strict vector dimension assertion (default 2048 for Nemotron 3.5 Embed 1B).
    - Secret scrubbing: API credentials are never logged or exposed in exceptions.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: str = DEFAULT_NVIDIA_EMBEDDING_MODEL,
        dimension: int = DEFAULT_NVIDIA_EMBEDDING_DIMENSION,
        client: Optional[httpx.AsyncClient] = None,
        batch_size: int = MAX_NVIDIA_EMBEDDING_BATCH_SIZE,
        timeout: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        raw_url = (base_url or DEFAULT_NVIDIA_BASE_URL).rstrip("/")
        if not (raw_url.startswith("http://") or raw_url.startswith("https://")):
            raise ConfigurationError(
                f"NVIDIA embedding base URL must start with 'http://' or 'https://', got '{raw_url}'"
            )
        self.base_url = raw_url
        self.api_key = api_key
        self.model = model
        self._dimension = dimension
        self._client = client
        self.batch_size = max(1, batch_size)
        self.timeout = max(1.0, timeout)
        self.max_retries = max(0, max_retries)

    @property
    def dimension(self) -> int:
        return self._dimension

    async def _post_batch(
        self,
        batch_texts: list[str],
        input_type: str,
    ) -> list[list[float]]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "input": batch_texts,
            "input_type": input_type,
            "truncate": "END",
        }
        endpoint = f"{self.base_url}/embeddings"

        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                if self._client is not None:
                    response = await self._client.post(
                        endpoint,
                        json=payload,
                        headers=headers,
                        timeout=self.timeout,
                    )
                else:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.post(
                            endpoint,
                            json=payload,
                            headers=headers,
                        )

                # Safe status code classification
                if response.status_code == 200:
                    try:
                        data = response.json()
                    except Exception as parse_exc:
                        raise ResearchPipelineError(
                            f"Failed to parse NVIDIA embedding response JSON: {parse_exc}"
                        ) from parse_exc

                    raw_items = data.get("data", [])
                    if not raw_items:
                        raise ResearchPipelineError("NVIDIA embedding provider returned empty data list")

                    # Preserve ordering by 'index'
                    sorted_items = sorted(raw_items, key=lambda x: x.get("index", 0))
                    vectors: list[list[float]] = []

                    for item in sorted_items:
                        vec = item.get("embedding", [])
                        if not vec:
                            raise ResearchPipelineError("NVIDIA embedding provider returned an empty vector")
                        if len(vec) != self._dimension:
                            raise ConfigurationError(
                                f"Embedding dimension mismatch: expected {self._dimension}, got {len(vec)}"
                            )
                        vectors.append(vec)

                    return vectors

                elif response.status_code in (401, 403):
                    raise AuthenticationError(
                        f"NVIDIA embedding API authentication failed (HTTP {response.status_code})"
                    )
                elif response.status_code == 429:
                    last_error = RateLimitError("NVIDIA embedding API rate limit exceeded (HTTP 429)")
                elif response.status_code >= 500:
                    last_error = ProviderUnavailableError(
                        f"NVIDIA embedding service unavailable (HTTP {response.status_code})"
                    )
                else:
                    raise ResearchPipelineError(
                        f"NVIDIA embedding request failed with HTTP status {response.status_code}: {response.text[:200]}"
                    )

            except (httpx.TimeoutException, asyncio.TimeoutError) as exc:
                last_error = LLMTimeoutError(f"NVIDIA embedding request timed out after {self.timeout}s")
            except (AuthenticationError, ConfigurationError, ResearchPipelineError):
                raise
            except Exception as exc:
                last_error = ResearchPipelineError(f"NVIDIA embedding HTTP transport error: {type(exc).__name__}")

            # Jittered backoff if attempts remaining
            if attempt < self.max_retries:
                backoff = min(0.5 * (2 ** attempt) + random.uniform(0.1, 0.3), 2.5)
                await asyncio.sleep(backoff)

        if last_error:
            raise last_error
        raise ResearchPipelineError("NVIDIA embedding request failed with unknown error")

    async def _post_embeddings(
        self,
        texts: list[str],
        input_type: str,
    ) -> list[list[float]]:
        if not texts:
            return []

        all_vectors: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            chunk = texts[i : i + self.batch_size]
            batch_vectors = await self._post_batch(chunk, input_type=input_type)
            all_vectors.extend(batch_vectors)

        return all_vectors

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embeds document/passage chunks using input_type='passage'."""
        return await self._post_embeddings(texts, input_type="passage")

    async def embed_query(self, text: str) -> list[float]:
        """Embeds search query string using input_type='query'."""
        results = await self._post_embeddings([text], input_type="query")
        if not results:
            raise ResearchPipelineError("Failed to generate query embedding vector")
        return results[0]
