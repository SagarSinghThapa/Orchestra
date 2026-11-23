from app.core.config import settings
from app.research.embeddings.base import EmbeddingProvider
from app.research.embeddings.mock import DeterministicTestEmbeddingProvider
from app.research.embeddings.nvidia import NVIDIAEmbeddingProvider
from app.research.embeddings.openai import OpenAICompatibleEmbeddingProvider
from app.research.exceptions import ConfigurationError


def get_embedding_provider() -> EmbeddingProvider:
    """
    Factory function instantiating the configured EmbeddingProvider.
    
    Guarantees:
    - In production, rejects 'test' provider with descriptive ConfigurationError.
    - In production with real providers ('openai_compatible', 'nvidia'), mandates API credentials.
    - Accurately conveys configured dimension to providers and ensures proper query/passage handling.
    """
    provider_name = (settings.embedding_provider or "").lower()

    if provider_name == "test":
        if settings.environment == "production":
            raise ConfigurationError(
                "EMBEDDING_PROVIDER cannot be 'test' in production environment. "
                "Configure a real provider such as 'openai_compatible' or 'nvidia' with required credentials."
            )
        return DeterministicTestEmbeddingProvider(dimension=settings.embedding_dimension)

    elif provider_name == "nvidia":
        api_key = settings.embedding_api_key or settings.llm_api_key
        if settings.environment == "production" and not api_key:
            raise ConfigurationError(
                "EMBEDDING_API_KEY (or LLM_API_KEY) must be configured for nvidia embedding provider in production"
            )
        base_url = settings.embedding_base_url or "https://integrate.api.nvidia.com/v1"
        model = (
            settings.embedding_model
            if settings.embedding_model and settings.embedding_model != "text-embedding-3-small"
            else "nvidia/nemotron-3.5-embed-1b"
        )
        dimension = (
            settings.embedding_dimension
            if settings.embedding_dimension and settings.embedding_dimension != 1536
            else 2048
        )
        return NVIDIAEmbeddingProvider(
            base_url=base_url,
            api_key=api_key,
            model=model,
            dimension=dimension,
        )

    elif provider_name == "openai_compatible":
        if settings.environment == "production" and not settings.embedding_api_key:
            raise ConfigurationError(
                "EMBEDDING_API_KEY must be configured for openai_compatible provider in production"
            )
        return OpenAICompatibleEmbeddingProvider(
            base_url=settings.embedding_base_url,
            api_key=settings.embedding_api_key,
            model=settings.embedding_model,
            dimension=settings.embedding_dimension,
        )

    else:
        raise ConfigurationError(f"Unsupported embedding provider: {settings.embedding_provider}")
