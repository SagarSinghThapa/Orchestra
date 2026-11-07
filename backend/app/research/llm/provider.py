from app.core.config import settings, PROVIDER_PRESETS
from app.research.exceptions import ConfigurationError
from app.research.llm.base import LLMProvider
from app.research.llm.mock import DeterministicTestLLMProvider
from app.research.llm.openai import OpenAICompatibleLLMProvider


def get_llm_provider() -> LLMProvider:
    """
    Factory function instantiating the configured LLMProvider.

    Guarantees:
    - In production, rejects 'test' provider with descriptive ConfigurationError.
    - In production with real providers (openai, groq, nvidia, gemini, openai_compatible),
      mandates LLM_API_KEY and valid HTTP/HTTPS base URL.
    - Preserves deterministic offline test provider when LLM_PROVIDER=test.
    """
    provider_name = (settings.llm_provider or "").lower()

    if provider_name == "test":
        if settings.environment == "production":
            raise ConfigurationError(
                "LLM_PROVIDER cannot be 'test' in production environment. "
                "Configure a real provider such as 'openai_compatible' with required credentials."
            )
        return DeterministicTestLLMProvider()

    elif provider_name in PROVIDER_PRESETS:
        preset = PROVIDER_PRESETS[provider_name]
        if settings.environment == "production" and not settings.llm_api_key:
            raise ConfigurationError(
                f"LLM_API_KEY must be configured for {provider_name} provider in production"
            )

        # Preset defaults with explicit override support
        base_url = preset["base_url"]
        if settings.llm_base_url and settings.llm_base_url != "https://api.openai.com/v1":
            base_url = settings.llm_base_url

        model = preset["default_model"]
        if settings.llm_model and settings.llm_model != "gpt-4o-mini":
            model = settings.llm_model

        return OpenAICompatibleLLMProvider(
            base_url=base_url,
            api_key=settings.llm_api_key,
            model=model,
            timeout=settings.llm_timeout_seconds,
            max_tokens=settings.llm_max_output_tokens,
            max_retries=settings.llm_max_retries,
        )

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
            max_retries=settings.llm_max_retries,
        )

    else:
        raise ConfigurationError(f"Unsupported LLM provider: {settings.llm_provider}")
