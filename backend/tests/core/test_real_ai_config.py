import asyncio
import time
import httpx
import pytest

from app.core.config import Settings, PROVIDER_PRESETS
from app.research.exceptions import (
    AuthenticationError,
    ConfigurationError,
    LLMTimeoutError,
    ProviderUnavailableError,
    RateLimitError,
    ResearchPipelineError,
)
from app.research.embeddings.openai import OpenAICompatibleEmbeddingProvider
from app.research.llm.openai import OpenAICompatibleLLMProvider
from app.research.llm.provider import get_llm_provider
from app.research.embeddings.provider import get_embedding_provider


def test_provider_presets_configuration():
    assert "openai" in PROVIDER_PRESETS
    assert "groq" in PROVIDER_PRESETS
    assert "nvidia" in PROVIDER_PRESETS
    assert "gemini" in PROVIDER_PRESETS

    assert PROVIDER_PRESETS["groq"]["base_url"] == "https://api.groq.com/openai/v1"
    assert "llama-3.3" in PROVIDER_PRESETS["groq"]["default_model"]
    assert "gemini" in PROVIDER_PRESETS["gemini"]["default_model"]


def test_provider_factory_resolves_presets(monkeypatch):
    from app.core.config import settings

    # Test Groq preset resolution
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "llm_provider", "groq")
    monkeypatch.setattr(settings, "llm_api_key", "gsk-test-key")
    monkeypatch.setattr(settings, "llm_base_url", "https://api.openai.com/v1")  # default
    monkeypatch.setattr(settings, "llm_model", "gpt-4o-mini")  # default

    provider = get_llm_provider()
    assert isinstance(provider, OpenAICompatibleLLMProvider)
    assert provider.base_url == "https://api.groq.com/openai/v1"
    assert provider.model == "llama-3.3-70b-versatile"
    assert provider.api_key == "gsk-test-key"

    # Test NVIDIA preset resolution
    monkeypatch.setattr(settings, "llm_provider", "nvidia")
    provider_nvidia = get_llm_provider()
    assert provider_nvidia.base_url == "https://integrate.api.nvidia.com/v1"
    assert "llama-3.1" in provider_nvidia.model

    # Test Gemini preset resolution
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    provider_gemini = get_llm_provider()
    assert "generativelanguage.googleapis.com" in provider_gemini.base_url
    assert "gemini-1.5-flash" in provider_gemini.model


def test_decoupled_llm_and_embedding_providers(monkeypatch):
    from app.core.config import settings

    # Operator selects Groq for LLM, but test/openai for embeddings
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "llm_provider", "groq")
    monkeypatch.setattr(settings, "llm_api_key", "gsk-test")
    monkeypatch.setattr(settings, "embedding_provider", "test")
    monkeypatch.setattr(settings, "embedding_dimension", 1536)

    llm = get_llm_provider()
    emb = get_embedding_provider()

    assert isinstance(llm, OpenAICompatibleLLMProvider)
    assert emb.dimension == 1536


@pytest.mark.asyncio
async def test_error_mapping_401_fails_fast_zero_retries():
    call_count = 0

    def _handler(request):
        nonlocal call_count
        call_count += 1
        return httpx.Response(401, json={"error": {"message": "Invalid API Key"}})

    transport = httpx.MockTransport(_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAICompatibleLLMProvider(
            base_url="https://api.groq.com/openai/v1",
            api_key="invalid-key",
            client=client,
            max_retries=2,
        )
        with pytest.raises(AuthenticationError, match="authentication failed with HTTP status 401"):
            await provider.generate_text("Test prompt")

    # Strictly 1 call made; zero retries on authentication error
    assert call_count == 1


@pytest.mark.asyncio
async def test_error_mapping_429_retries_and_raises_rate_limit():
    call_count = 0

    def _handler(request):
        nonlocal call_count
        call_count += 1
        return httpx.Response(429, json={"error": {"message": "Rate limit reached"}})

    transport = httpx.MockTransport(_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAICompatibleLLMProvider(
            base_url="https://api.openai.com/v1",
            api_key="test-key",
            client=client,
            max_retries=2,
        )
        with pytest.raises(RateLimitError, match="rate limit or quota exceeded with HTTP status 429"):
            await provider.generate_text("Test prompt")

    # Initial call + 2 retries = 3 calls total
    assert call_count == 3


@pytest.mark.asyncio
async def test_error_mapping_503_retries_and_raises_unavailable():
    call_count = 0

    def _handler(request):
        nonlocal call_count
        call_count += 1
        return httpx.Response(503, text="Service Unavailable")

    transport = httpx.MockTransport(_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAICompatibleLLMProvider(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key="test-key",
            client=client,
            max_retries=1,
        )
        with pytest.raises(ProviderUnavailableError, match="temporarily unavailable with HTTP status 503"):
            await provider.generate_text("Test prompt")

    # Initial call + 1 retry = 2 calls total
    assert call_count == 2


@pytest.mark.asyncio
async def test_deadline_budget_aborts_retry_when_under_floor():
    call_count = 0

    def _handler(request):
        nonlocal call_count
        call_count += 1
        return httpx.Response(502, text="Bad Gateway")

    transport = httpx.MockTransport(_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAICompatibleLLMProvider(
            base_url="https://api.openai.com/v1",
            api_key="test-key",
            client=client,
            max_retries=3,
        )
        # Set a past or razor-thin deadline (< 2.0s remaining)
        thin_deadline = time.monotonic() + 0.1
        with pytest.raises(ProviderUnavailableError):
            await provider._post_chat(
                messages=[{"role": "user", "content": "hi"}],
                deadline=thin_deadline,
            )

    # First call failed with 502, but second attempt aborted because remaining < 2.0s
    assert call_count == 1


@pytest.mark.asyncio
async def test_embedding_dimension_strict_guard_rejects_mismatch():
    # If a provider returns 768 or 1024 dims instead of 1536, it must raise ConfigurationError
    def _handler(request):
        # Return 768-dim mock vector (e.g. Gemini embedding)
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 0, "embedding": [0.1] * 768}
                ]
            },
        )

    transport = httpx.MockTransport(_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAICompatibleEmbeddingProvider(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            api_key="gemini-key",
            dimension=1536,  # Qdrant collection contract
            client=client,
        )
        with pytest.raises(ConfigurationError, match="Embedding dimension mismatch: expected 1536, got 768"):
            await provider.embed_documents(["Test chunk"])

