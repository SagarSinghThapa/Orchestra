import math
import httpx
import pytest

from app.core.config import Settings, settings
from app.research.embeddings.mock import DeterministicTestEmbeddingProvider
from app.research.embeddings.openai import OpenAICompatibleEmbeddingProvider
from app.research.embeddings.provider import get_embedding_provider
from app.research.exceptions import ConfigurationError, ResearchPipelineError


class TestDeterministicTestEmbeddingProvider:
    @pytest.mark.asyncio
    async def test_dimension_contract(self):
        p1536 = DeterministicTestEmbeddingProvider(dimension=1536)
        assert p1536.dimension == 1536
        v1536 = await p1536.embed_query("quantum computing")
        assert len(v1536) == 1536

        p768 = DeterministicTestEmbeddingProvider(dimension=768)
        assert p768.dimension == 768
        v768 = await p768.embed_query("quantum computing")
        assert len(v768) == 768

    @pytest.mark.asyncio
    async def test_determinism(self):
        provider = DeterministicTestEmbeddingProvider(dimension=1536)
        text = "Orchestra research multi-agent architecture"
        v1 = await provider.embed_query(text)
        v2 = await provider.embed_query(text)
        assert v1 == v2

        docs_vecs = await provider.embed_documents([text, text])
        assert len(docs_vecs) == 2
        assert docs_vecs[0] == v1
        assert docs_vecs[1] == v1

    @pytest.mark.asyncio
    async def test_uniqueness(self):
        provider = DeterministicTestEmbeddingProvider(dimension=1536)
        v1 = await provider.embed_query("Topic Alpha")
        v2 = await provider.embed_query("Topic Beta")
        assert v1 != v2

    @pytest.mark.asyncio
    async def test_unit_normalization(self):
        provider = DeterministicTestEmbeddingProvider(dimension=1536)
        v = await provider.embed_query("Normalize this vector")
        norm = math.sqrt(sum(x * x for x in v))
        assert math.isclose(norm, 1.0, rel_tol=1e-3)


class TestOpenAICompatibleEmbeddingProvider:
    @pytest.mark.asyncio
    async def test_mock_transport_success(self):
        expected_vec = [0.1] * 1536

        def handler(request: httpx.Request):
            assert request.url.path.endswith("/embeddings")
            assert request.headers["authorization"] == "Bearer test-api-key"
            assert request.headers["content-type"] == "application/json"
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"embedding": expected_vec, "index": 0}
                    ]
                },
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            provider = OpenAICompatibleEmbeddingProvider(
                base_url="https://mock.api.openai.com/v1",
                api_key="test-api-key",
                dimension=1536,
                client=client,
            )
            res = await provider.embed_query("hello world")
            assert len(res) == 1536
            assert res == expected_vec

    @pytest.mark.asyncio
    async def test_dimension_mismatch_raises_configuration_error(self):
        def handler(request: httpx.Request):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"embedding": [0.1] * 768, "index": 0}
                    ]
                },
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            provider = OpenAICompatibleEmbeddingProvider(
                base_url="https://mock.api.openai.com/v1",
                api_key="test-api-key",
                dimension=1536,
                client=client,
            )
            with pytest.raises(ConfigurationError, match="Embedding dimension mismatch: expected 1536, got 768"):
                await provider.embed_query("test query")

    @pytest.mark.asyncio
    async def test_http_error_raises_pipeline_error(self):
        def handler(request: httpx.Request):
            return httpx.Response(500, text="Internal Server Error")

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            provider = OpenAICompatibleEmbeddingProvider(
                base_url="https://mock.api.openai.com/v1",
                api_key="test-api-key",
                client=client,
            )
            with pytest.raises(ResearchPipelineError, match="Embedding request failed with HTTP status 500"):
                await provider.embed_query("test")


class TestProductionEnvironmentSafetyGuards:
    def test_production_rejects_test_provider_in_factory(self, monkeypatch):
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "embedding_provider", "test")

        with pytest.raises(ConfigurationError, match="EMBEDDING_PROVIDER cannot be 'test' in production"):
            get_embedding_provider()

    def test_production_mandates_api_key_for_openai_provider(self, monkeypatch):
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "embedding_provider", "openai_compatible")
        monkeypatch.setattr(settings, "embedding_api_key", None)

        with pytest.raises(ConfigurationError, match="EMBEDDING_API_KEY must be configured"):
            get_embedding_provider()

    def test_validate_runtime_requirements_catches_test_provider_in_production(self):
        test_settings = Settings(
            database_url="postgresql+psycopg://user:pass@localhost:5432/db",
            jwt_secret="super-secret-key",
            environment="production",
            embedding_provider="test",
        )
        with pytest.raises(RuntimeError, match="EMBEDDING_PROVIDER cannot be 'test' in production"):
            test_settings.validate_runtime_requirements()
