import pytest
import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.research.exceptions import ConfigurationError, ResearchPipelineError
from app.research.llm.base import ChatMessage, LLMResponse
from app.research.llm.mock import DeterministicTestLLMProvider
from app.research.llm.openai import OpenAICompatibleLLMProvider
from app.research.llm.provider import get_llm_provider
from app.research.schemas import (
    DraftClaim,
    DraftResearchAnswer,
    ResearchClaim,
    ResearchMetadata,
    ResearchPlan,
    ResearchRequest,
    ResearchResponse,
    ResearchStatus,
    VerifiedCitation,
)


@pytest.mark.asyncio
async def test_mock_llm_provider_text_generation():
    provider = DeterministicTestLLMProvider()
    res = await provider.generate_text("Explain quantum computing")
    assert "Deterministic response" in res
    assert provider.call_count == 1
    assert provider.last_prompt == "Explain quantum computing"


@pytest.mark.asyncio
async def test_mock_llm_provider_structured_plan():
    provider = DeterministicTestLLMProvider()
    plan = await provider.generate_structured(
        prompt="<USER_QUESTION>What is transformer attention?</USER_QUESTION>",
        schema=ResearchPlan,
    )
    assert isinstance(plan, ResearchPlan)
    assert len(plan.subqueries) >= 1
    assert "What is transformer attention?" in plan.subqueries[0]
    assert provider.call_count == 1


@pytest.mark.asyncio
async def test_mock_llm_provider_structured_synthesis():
    provider = DeterministicTestLLMProvider()
    prompt = (
        '<USER_QUESTION>How fast is Qdrant?</USER_QUESTION>\n'
        '<UNTRUSTED_RETRIEVED_EVIDENCE>\n'
        '<evidence id="evidence_0">Qdrant can process 10,000 queries per second.</evidence>\n'
        '</UNTRUSTED_RETRIEVED_EVIDENCE>'
    )
    answer = await provider.generate_structured(
        prompt=prompt,
        schema=DraftResearchAnswer,
    )
    assert isinstance(answer, DraftResearchAnswer)
    assert answer.has_sufficient_evidence is True
    assert len(answer.claims) >= 1
    assert "evidence_0" in answer.claims[0].supporting_evidence_ids


@pytest.mark.asyncio
async def test_mock_llm_provider_error_modes():
    # Timeout mode
    provider_timeout = DeterministicTestLLMProvider(mode="timeout")
    with pytest.raises(ResearchPipelineError, match="timed out"):
        await provider_timeout.generate_text("Prompt")

    # Malformed JSON mode
    provider_malformed = DeterministicTestLLMProvider(mode="malformed_json")
    with pytest.raises(ResearchPipelineError, match="Invalid JSON formatting"):
        await provider_malformed.generate_structured("Prompt", schema=ResearchPlan)

    # Insufficient evidence mode
    provider_insufficient = DeterministicTestLLMProvider(mode="insufficient_evidence")
    draft = await provider_insufficient.generate_structured("Prompt", schema=DraftResearchAnswer)
    assert draft.has_sufficient_evidence is False
    assert len(draft.claims) == 0

    # Hallucinated citations mode
    provider_hallucinated = DeterministicTestLLMProvider(mode="hallucinated_citations")
    draft_h = await provider_hallucinated.generate_structured("Prompt", schema=DraftResearchAnswer)
    assert "evidence_9999" in draft_h.claims[0].supporting_evidence_ids

    # Unsupported claim mode
    provider_unsupported = DeterministicTestLLMProvider(mode="unsupported_claim")
    draft_u = await provider_unsupported.generate_structured("Prompt", schema=DraftResearchAnswer)
    assert len(draft_u.claims[0].supporting_evidence_ids) == 0


def test_provider_factory_test_mode(monkeypatch):
    monkeypatch.setattr(settings, "environment", "test")
    monkeypatch.setattr(settings, "llm_provider", "test")
    provider = get_llm_provider()
    assert isinstance(provider, DeterministicTestLLMProvider)


def test_provider_factory_production_guard(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "llm_provider", "test")
    with pytest.raises(ConfigurationError, match="LLM_PROVIDER cannot be 'test' in production"):
        get_llm_provider()


def test_provider_factory_missing_api_key(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "llm_provider", "openai_compatible")
    monkeypatch.setattr(settings, "llm_api_key", None)
    with pytest.raises(ConfigurationError, match="LLM_API_KEY must be configured"):
        get_llm_provider()


def test_provider_factory_invalid_base_url_scheme(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "llm_provider", "openai_compatible")
    monkeypatch.setattr(settings, "llm_api_key", "sk-secret-123")
    monkeypatch.setattr(settings, "llm_base_url", "file:///etc/passwd")
    with pytest.raises(ConfigurationError, match="must begin with 'http://' or 'https://'"):
        get_llm_provider()


@pytest.mark.asyncio
async def test_openai_provider_timeout_handling():
    def _timeout_handler(request):
        raise httpx.TimeoutException("Connection timed out", request=request)

    transport = httpx.MockTransport(_timeout_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAICompatibleLLMProvider(
            base_url="https://api.openai.com/v1",
            api_key="test-key",
            client=client,
            timeout=1.0,
        )
        with pytest.raises(ResearchPipelineError, match="timed out"):
            await provider.generate_text("Test prompt")


@pytest.mark.asyncio
async def test_openai_provider_structured_parsing():
    valid_json_response = {
        "choices": [
            {
                "message": {
                    "content": '```json\n{"goal": "Understand attention", "subqueries": ["attention mechanism"], "strategy_notes": "Focused"}\n```'
                }
            }
        ]
    }

    def _json_handler(request):
        return httpx.Response(200, json=valid_json_response)

    transport = httpx.MockTransport(_json_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAICompatibleLLMProvider(
            base_url="https://api.openai.com/v1",
            api_key="test-key",
            client=client,
        )
        plan = await provider.generate_structured("Prompt", schema=ResearchPlan)
        assert isinstance(plan, ResearchPlan)
        assert plan.goal == "Understand attention"
        assert plan.subqueries == ["attention mechanism"]


def test_research_request_validation():
    # Valid request
    req = ResearchRequest(question="How does Orchestra verify citations?")
    assert req.question == "How does Orchestra verify citations?"
    assert req.max_subqueries == 3
    assert req.max_evidence == 10

    # Question too short
    with pytest.raises(ValidationError):
        ResearchRequest(question="Hi")

    # Extra unauthorized parameters
    with pytest.raises(ValidationError):
        ResearchRequest(question="Valid question", system_prompt="Hacked")  # type: ignore

    # Subqueries out of bounds
    with pytest.raises(ValidationError):
        ResearchRequest(question="Valid question", max_subqueries=10)


def test_research_response_serialization():
    citation = VerifiedCitation(
        citation_id="[C1]",
        evidence_id="evidence_0",
        document_id=1,
        document_filename="paper.pdf",
        page_number=2,
        chunk_id="chunk_123",
        start_char=50,
        end_char=150,
        text="The empirical results show 95% accuracy.",
        score=0.95,
    )
    claim = ResearchClaim(
        claim_text="The empirical results show 95% accuracy.",
        citation_ids=["[C1]"],
    )
    metadata = ResearchMetadata(
        model="gpt-4o-mini",
        subqueries_executed=["query 1"],
        total_evidence_retrieved=1,
        verified_citations_count=1,
        execution_time_ms=125.5,
        llm_call_count=2,
    )
    response = ResearchResponse(
        question="What is the accuracy?",
        status=ResearchStatus.COMPLETED,
        answer="The empirical results show 95% accuracy [C1].",
        claims=[claim],
        citations=[citation],
        evidence_count=1,
        metadata=metadata,
    )

    json_str = response.model_dump_json()
    assert "[C1]" in json_str
    assert "paper.pdf" in json_str

    deserialized = ResearchResponse.model_validate_json(json_str)
    assert deserialized.status == ResearchStatus.COMPLETED
    assert len(deserialized.claims) == 1
    assert deserialized.citations[0].document_filename == "paper.pdf"
