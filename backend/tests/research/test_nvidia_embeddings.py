import pytest
import httpx
from unittest.mock import AsyncMock, patch

from app.core.config import settings
from app.research.embeddings.nvidia import (
    NVIDIAEmbeddingProvider,
    DEFAULT_NVIDIA_EMBEDDING_DIMENSION,
    DEFAULT_NVIDIA_EMBEDDING_MODEL,
)
from app.research.embeddings.provider import get_embedding_provider
from app.research.exceptions import (
    AuthenticationError,
    ConfigurationError,
    ProviderUnavailableError,
    RateLimitError,
    ResearchPipelineError,
)
from app.research.vectorstore.qdrant import resolve_qdrant_collection_name


@pytest.fixture
def mock_nvidia_vector_2048():
    return [0.01 * (i % 10) for i in range(DEFAULT_NVIDIA_EMBEDDING_DIMENSION)]


@pytest.mark.asyncio
async def test_nvidia_embed_query_success(mock_nvidia_vector_2048):
    mock_response = httpx.Response(
        status_code=200,
        json={"data": [{"index": 0, "embedding": mock_nvidia_vector_2048}]},
        request=httpx.Request("POST", "https://integrate.api.nvidia.com/v1/embeddings"),
    )

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = mock_response

    provider = NVIDIAEmbeddingProvider(
        api_key="nvapi-test-fake-key",
        client=mock_client,
    )

    query_vec = await provider.embed_query("What is Project Aurora?")
    assert len(query_vec) == 2048
    assert provider.dimension == 2048

    mock_client.post.assert_called_once()
    call_args, call_kwargs = mock_client.post.call_args
    payload = call_kwargs["json"]
    assert payload["model"] == DEFAULT_NVIDIA_EMBEDDING_MODEL
    assert payload["input"] == ["What is Project Aurora?"]
    assert payload["input_type"] == "query"
    assert payload["truncate"] == "END"


@pytest.mark.asyncio
async def test_nvidia_embed_documents_passage_success(mock_nvidia_vector_2048):
    mock_response = httpx.Response(
        status_code=200,
        json={
            "data": [
                {"index": 0, "embedding": mock_nvidia_vector_2048},
                {"index": 1, "embedding": mock_nvidia_vector_2048},
            ]
        },
        request=httpx.Request("POST", "https://integrate.api.nvidia.com/v1/embeddings"),
    )

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = mock_response

    provider = NVIDIAEmbeddingProvider(
        api_key="nvapi-test-fake-key",
        client=mock_client,
    )

    docs = ["Doc chunk 1 text", "Doc chunk 2 text"]
    doc_vecs = await provider.embed_documents(docs)
    assert len(doc_vecs) == 2
    assert len(doc_vecs[0]) == 2048
    assert len(doc_vecs[1]) == 2048

    mock_client.post.assert_called_once()
    _, call_kwargs = mock_client.post.call_args
    payload = call_kwargs["json"]
    assert payload["input_type"] == "passage"
    assert payload["input"] == docs


@pytest.mark.asyncio
async def test_nvidia_dimension_mismatch_fails():
    wrong_vector = [0.1] * 1536  # Expected 2048
    mock_response = httpx.Response(
        status_code=200,
        json={"data": [{"index": 0, "embedding": wrong_vector}]},
        request=httpx.Request("POST", "https://integrate.api.nvidia.com/v1/embeddings"),
    )

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = mock_response

    provider = NVIDIAEmbeddingProvider(
        api_key="nvapi-test-fake-key",
        dimension=2048,
        client=mock_client,
    )

    with pytest.raises(ConfigurationError) as exc_info:
        await provider.embed_query("test query")
    assert "Embedding dimension mismatch" in str(exc_info.value)


@pytest.mark.asyncio
async def test_nvidia_auth_error_sanitization():
    mock_response = httpx.Response(
        status_code=401,
        json={"detail": "Invalid authentication credentials"},
        request=httpx.Request("POST", "https://integrate.api.nvidia.com/v1/embeddings"),
    )

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = mock_response

    provider = NVIDIAEmbeddingProvider(
        api_key="nvapi-super-secret-key-12345",
        client=mock_client,
        max_retries=0,
    )

    with pytest.raises(AuthenticationError) as exc_info:
        await provider.embed_query("test query")
    err_str = str(exc_info.value)
    assert "HTTP 401" in err_str
    assert "nvapi-super-secret-key-12345" not in err_str


@pytest.mark.asyncio
async def test_nvidia_rate_limit_error():
    mock_response = httpx.Response(
        status_code=429,
        json={"detail": "Quota exceeded"},
        request=httpx.Request("POST", "https://integrate.api.nvidia.com/v1/embeddings"),
    )

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = mock_response

    provider = NVIDIAEmbeddingProvider(
        api_key="nvapi-test-fake-key",
        client=mock_client,
        max_retries=0,
    )

    with pytest.raises(RateLimitError):
        await provider.embed_query("test query")


@pytest.mark.asyncio
async def test_nvidia_provider_unavailable_error():
    mock_response = httpx.Response(
        status_code=503,
        json={"detail": "Service unavailable"},
        request=httpx.Request("POST", "https://integrate.api.nvidia.com/v1/embeddings"),
    )

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = mock_response

    provider = NVIDIAEmbeddingProvider(
        api_key="nvapi-test-fake-key",
        client=mock_client,
        max_retries=0,
    )

    with pytest.raises(ProviderUnavailableError):
        await provider.embed_query("test query")


def test_qdrant_collection_isolation():
    with patch.object(settings, "embedding_provider", "test"):
        with patch.object(settings, "qdrant_collection_name", "orchestra_knowledge"):
            col = resolve_qdrant_collection_name()
            assert col == "orchestra_knowledge"

    with patch.object(settings, "embedding_provider", "openai_compatible"):
        with patch.object(settings, "qdrant_collection_name", "orchestra_knowledge"):
            col = resolve_qdrant_collection_name()
            assert col == "orchestra_knowledge"

    with patch.object(settings, "embedding_provider", "nvidia"):
        with patch.object(settings, "embedding_model", "nvidia/nemotron-3.5-embed-1b"):
            with patch.object(settings, "embedding_dimension", 2048):
                with patch.object(settings, "qdrant_collection_name", "orchestra_knowledge"):
                    col = resolve_qdrant_collection_name()
                    assert col == "orchestra_knowledge_nvidia_nemotron_35_embed_1b_2048"

    # Explicit override takes precedence
    col_custom = resolve_qdrant_collection_name("explicit_custom_collection")
    assert col_custom == "explicit_custom_collection"


def test_factory_nvidia_provider():
    with patch.object(settings, "embedding_provider", "nvidia"):
        with patch.object(settings, "llm_api_key", "nvapi-test-key"):
            with patch.object(settings, "embedding_api_key", None):
                with patch.object(settings, "embedding_model", "nvidia/nemotron-3.5-embed-1b"):
                    with patch.object(settings, "embedding_dimension", 2048):
                        provider = get_embedding_provider()
                        assert isinstance(provider, NVIDIAEmbeddingProvider)
                        assert provider.dimension == 2048
                        assert provider.model == "nvidia/nemotron-3.5-embed-1b"
                        assert provider.api_key == "nvapi-test-key"
