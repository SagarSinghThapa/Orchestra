"""
Tests for Independent BM25 Fallback, Degraded Retrieval, and No-Hallucination Error Handling.
"""

from unittest.mock import AsyncMock, MagicMock
import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.research.exceptions import ProviderUnavailableError
from app.research.retrieval.schemas import (
    CitationEvidence,
    SearchMode,
    SearchQuery,
    SearchResultChunk,
)
from app.research.services.retrieval_service import RetrievalService


@pytest.mark.asyncio
async def test_retrieval_service_bm25_fallback_on_dense_503(db_session: Session):
    """
    Verify that when dense vector retrieval raises ProviderUnavailableError (e.g. NVIDIA 503),
    RetrievalService falls back gracefully to independent BM25 sparse search and returns
    results marked with degraded_mode=True.
    """
    mock_dense = AsyncMock()
    mock_dense.search.side_effect = ProviderUnavailableError("NVIDIA NIM 503 Service Unavailable")

    mock_sparse = AsyncMock()
    fallback_chunk = SearchResultChunk(
        chunk_id="chunk_bm25_1",
        document_id=1,
        project_id=10,
        text="Fallback lexical evidence text regarding transformer attention.",
        chunk_index=0,
        page_number=1,
        start_char=0,
        end_char=50,
        score=2.85,
        source_engine="sparse",
    )
    mock_sparse.search.return_value = [fallback_chunk]

    mock_citation_builder = MagicMock()
    mock_citation_builder.build_citations.return_value = [
        CitationEvidence(
            evidence_id="ev_1",
            document_id=1,
            document_filename="attention.pdf",
            page_number=1,
            chunk_id="chunk_bm25_1",
            chunk_index=0,
            start_char=0,
            end_char=50,
            text=fallback_chunk.text,
            score=2.85,
        )
    ]

    service = RetrievalService(
        db=db_session,
        dense_retriever=mock_dense,
        sparse_retriever=mock_sparse,
        citation_builder=mock_citation_builder,
    )

    query = SearchQuery(query="attention mechanism", mode=SearchMode.HYBRID)
    resp = await service.search(project_id=10, query_input=query)

    assert resp.status == "ok"
    assert resp.degraded_mode is True
    assert resp.total_results == 1
    assert len(resp.results) == 1
    assert resp.results[0].chunk_id == "chunk_bm25_1"
    assert "Dense retrieval unavailable" in (resp.error_message or "")


@pytest.mark.asyncio
async def test_retrieval_service_no_hallucination_when_sparse_empty(db_session: Session):
    """
    Strict No-Hallucination Guard:
    When dense retrieval fails with 503 and independent sparse retrieval yields zero candidates,
    the service MUST explicitly return status='degraded_unavailable' with results=[] and
    zero fabricated citations.
    """
    mock_dense = AsyncMock()
    mock_dense.search.side_effect = ProviderUnavailableError("NVIDIA NIM 503 Service Unavailable")

    mock_sparse = AsyncMock()
    mock_sparse.search.return_value = []  # No sparse keywords match

    service = RetrievalService(
        db=db_session,
        dense_retriever=mock_dense,
        sparse_retriever=mock_sparse,
    )

    query = SearchQuery(query="obscure historical query", mode=SearchMode.HYBRID)
    resp = await service.search(project_id=10, query_input=query)

    assert resp.status == "degraded_unavailable"
    assert resp.degraded_mode is True
    assert resp.total_results == 0
    assert resp.results == []  # ZERO fabricated citations
    assert "Dense embedding service unavailable" in (resp.error_message or "")


def test_production_guard_rejects_nvidia_without_api_key():
    """Verify validate_runtime_requirements fails fast if NVIDIA provider has no API key."""
    s = Settings(
        environment="production",
        database_url="postgresql+psycopg://user:pass@localhost:5432/orchestra",
        jwt_secret="a_valid_production_secret_at_least_32_characters_long!",
        cookie_secure=True,
        rate_limit_enabled=True,
        rate_limit_backend="redis",
        qdrant_url="http://localhost:6333",
        llm_provider="openai_compatible",
        llm_api_key="valid-llm-key",
        embedding_provider="nvidia",
        embedding_api_key="",
    )
    # Both embedding_api_key and llm_api_key empty
    s.llm_api_key = ""
    with pytest.raises(RuntimeError) as exc_info:
        s.validate_runtime_requirements()
    assert "EMBEDDING_API_KEY (or LLM_API_KEY) must be configured for nvidia" in str(exc_info.value)
