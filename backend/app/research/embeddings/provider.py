from app.core.config import settings
from app.research.embeddings.base import EmbeddingProvider
from app.research.embeddings.mock import DeterministicTestEmbeddingProvider
from app.research.embeddings.openai import OpenAICompatibleEmbeddingProvider
from app.research.exceptions import ConfigurationError


def get_embedding_provider() -> EmbeddingProvider:
    """
    Factory function instantiating the configured EmbeddingProvider.
    
    Guarantees:
    - In production, rejects 'test' provider with descriptive ConfigurationError.
    - In production with 'openai_compatible', mandates EMBEDDING_API_KEY.
    - Accurately conveys configured dimension to providers.
    """
    provider_name = (settings.embedding_provider or "").lower()

    if provider_name == "test":
        if settings.environment == "production":
            raise ConfigurationError(
                "EMBEDDING_PROVIDER cannot be 'test' in production environment. "
                "Configure a real provider such as 'openai_compatible' with required credentials."
            )
        return DeterministicTestEmbeddingProvider(dimension=settings.embedding_dimension)

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
