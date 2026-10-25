from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol defining the interface for document and query embedding generation."""

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate vector representations for a list of document chunk texts."""
        ...

    async def embed_query(self, text: str) -> list[float]:
        """Generate vector representation for a search query string."""
        ...

    @property
    def dimension(self) -> int:
        """Dimensionality of the emitted embedding vectors."""
        ...
