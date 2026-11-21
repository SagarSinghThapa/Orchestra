import hashlib
import math
import random

from app.research.embeddings.base import EmbeddingProvider


class DeterministicTestEmbeddingProvider(EmbeddingProvider):
    """
    Offline, fast, and 100% deterministic embedding provider for testing.
    
    Guarantees:
    - Zero network calls and zero heavy ML dependencies.
    - Deterministic: identical input text produces identical vectors.
    - Distinct: different input text produces distinct vectors.
    - Normalized unit vectors (Euclidean norm ≈ 1.0).
    """

    def __init__(self, dimension: int = 1536) -> None:
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def _generate_vector(self, text: str) -> list[float]:
        # Derive a 64-bit seed from the SHA-256 digest of the input text
        text_hash = hashlib.sha256(text.encode("utf-8")).digest()
        seed = int.from_bytes(text_hash[:8], byteorder="big")
        rng = random.Random(seed)

        # Generate Gaussian pseudo-random components and normalize to unit length
        raw_components = [rng.gauss(0.0, 1.0) for _ in range(self._dimension)]
        norm = math.sqrt(sum(x * x for x in raw_components)) or 1.0
        return [round(x / norm, 6) for x in raw_components]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._generate_vector(t) for t in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._generate_vector(text)
