from app.core.config import settings
from app.research.exceptions import ConfigurationError
from app.research.llm.base import LLMProvider
from app.research.llm.mock import DeterministicTestLLMProvider
from app.research.llm.openai import OpenAICompatibleLLMProvider


def get_llm_provider() -> LLMProvider:
    """
    Factory function instantiating the configured LLMProvider.

    Guarantees:
    - In production, rejects 'test' provider with descriptive ConfigurationError.
    - In production with 'openai_compatible', mandates LLM_API_KEY and valid HTTP/HTTPS base URL.
    """
    provider_name = (settings.llm_provider or "").lower()

    if provider_name == "test":
        if settings.environment == "production":
            raise ConfigurationError(
                "LLM_PROVIDER cannot be 'test' in production environment. "
                "Configure a real provider such as 'openai_compatible' with required credentials."
            )
        return DeterministicTestLLMProvider()

    elif provider_name == "openai_compatible":
        if settings.environment == "production":
            if not settings.llm_api_key:
                raise ConfigurationError(
                    "LLM_API_KEY must be configured for openai_compatible provider in production"
                )
            if not settings.llm_base_url or not (
                settings.llm_base_url.startswith("http://")
                or settings.llm_base_url.startswith("https://")
            ):
                raise ConfigurationError(
                    "LLM_BASE_URL must begin with 'http://' or 'https://' in production"
                )

        return OpenAICompatibleLLMProvider(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout=settings.llm_timeout_seconds,
            max_tokens=settings.llm_max_output_tokens,
        )

    else:
        raise ConfigurationError(f"Unsupported LLM provider: {settings.llm_provider}")
