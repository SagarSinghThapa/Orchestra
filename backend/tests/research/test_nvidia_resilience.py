"""
Tests for NVIDIA NIM Embedding 503 Resilience, Jittered Backoff, and Retry-After Handling.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest

from app.research.embeddings.nvidia import NVIDIAEmbeddingProvider
from app.research.exceptions import ProviderUnavailableError, RateLimitError


@pytest.mark.asyncio
async def test_nvidia_embedding_default_retries_and_5_attempts():
    """Verify default max_retries is 4, producing 5 attempts total on 503."""
    provider = NVIDIAEmbeddingProvider(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key="test-nv-key",
        timeout=5.0,
    )
    assert provider.max_retries == 4

    # Mock client to fail with 503
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_resp.text = "Service Unavailable"
    mock_resp.headers = {}

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = mock_resp
    provider._client = mock_client

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        with pytest.raises(ProviderUnavailableError) as exc_info:
            await provider.embed_query("test query")

        assert "503" in str(exc_info.value)
        # 5 attempts total means 5 calls to client.post
        assert mock_client.post.call_count == 5
        # 4 backoff sleeps between the 5 attempts
        assert mock_sleep.call_count == 4


@pytest.mark.asyncio
async def test_nvidia_embedding_respects_retry_after_header():
    """Verify numeric Retry-After header is honored up to 15.0s."""
    provider = NVIDIAEmbeddingProvider(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key="test-nv-key",
        max_retries=2,
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_resp.text = "Service Unavailable"
    mock_resp.headers = {"Retry-After": "4.5"}

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = mock_resp
    provider._client = mock_client

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        with pytest.raises(ProviderUnavailableError):
            await provider.embed_query("test query")

        assert mock_client.post.call_count == 3
        # Ensure the sleep duration matched Retry-After (4.5s)
        assert mock_sleep.call_count == 2
        for call_args in mock_sleep.call_args_list:
            assert call_args[0][0] == 4.5


@pytest.mark.asyncio
async def test_nvidia_embedding_recovers_after_transient_503():
    """Verify successful recovery on third attempt after two 503 errors."""
    provider = NVIDIAEmbeddingProvider(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key="test-nv-key",
        dimension=4,
        max_retries=4,
    )

    mock_resp_503 = MagicMock()
    mock_resp_503.status_code = 503
    mock_resp_503.text = "Service Unavailable"
    mock_resp_503.headers = {}

    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.json.return_value = {
        "data": [{"index": 0, "embedding": [0.1, 0.2, 0.3, 0.4]}]
    }

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.side_effect = [mock_resp_503, mock_resp_503, mock_resp_200]
    provider._client = mock_client

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        vec = await provider.embed_query("successful query")
        assert vec == [0.1, 0.2, 0.3, 0.4]
        assert mock_client.post.call_count == 3
        assert mock_sleep.call_count == 2
