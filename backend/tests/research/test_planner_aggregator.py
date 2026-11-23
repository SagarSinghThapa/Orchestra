import pytest
from unittest.mock import AsyncMock

from app.research.agents.aggregator import (
    AggregatedEvidence,
    EvidenceAggregator,
    EvidenceSelector,
)
from app.research.agents.planner import ResearchPlanner
from app.research.exceptions import ResearchPipelineError, VectorStoreError
from app.research.llm.mock import DeterministicTestLLMProvider
from app.research.retrieval.schemas import CitationEvidence, RetrievalResponse


@pytest.mark.asyncio
async def test_planner_decomposition_bounds():
    provider = DeterministicTestLLMProvider()
    planner = ResearchPlanner(llm_provider=provider)

    plan = await planner.plan("What are the architectural trade-offs in distributed RAG?", max_subqueries=3)
    assert len(plan.subqueries) <= 3
    assert plan.subqueries[0] == "What are the architectural trade-offs in distributed RAG?"


@pytest.mark.asyncio
async def test_planner_subquery_deduplication():
    # Mock LLM that returns duplicates
    mock_llm = AsyncMock()
    from app.research.schemas import ResearchPlan
    mock_llm.generate_structured.return_value = ResearchPlan(
        goal="Test duplicates",
        subqueries=[
            "quantum algorithms",
            "QUANTUM ALGORITHMS",
            "quantum algorithms ",
            "hybrid quantum classical",
        ],
    )
    planner = ResearchPlanner(llm_provider=mock_llm)
    plan = await planner.plan("Quantum computing overview", max_subqueries=4)

    # Primary question + unique decomposed queries <= 4
    assert plan.subqueries[0] == "Quantum computing overview"
    assert len(plan.subqueries) <= 4
    # Check no duplicate case-insensitive subqueries exist
    lowers = [q.lower() for q in plan.subqueries]
    assert len(lowers) == len(set(lowers))


@pytest.mark.asyncio
async def test_planner_fallback_on_failure():
    mock_llm = AsyncMock()
    mock_llm.generate_structured.side_effect = Exception("LLM connection failed")
    planner = ResearchPlanner(llm_provider=mock_llm)

    plan = await planner.plan("What is Orchestra?", max_subqueries=3)
    assert plan.subqueries == ["What is Orchestra?"]
    assert "fallback" in (plan.strategy_notes or "").lower()


@pytest.mark.asyncio
async def test_planner_unicode_normalization():
    mock_llm = AsyncMock()
    from app.research.schemas import ResearchPlan
    # e + combining acute
    decomposed_e = "re\u0301sume\u0301"
    mock_llm.generate_structured.return_value = ResearchPlan(
        goal="Normalization",
        subqueries=[decomposed_e],
    )
    planner = ResearchPlanner(llm_provider=mock_llm)
    plan = await planner.plan("Document processing", max_subqueries=2)

    import unicodedata
    for sq in plan.subqueries:
        assert unicodedata.is_normalized("NFC", sq)


@pytest.mark.asyncio
async def test_aggregator_multi_query_execution():
    mock_retrieval_service = AsyncMock()

    chunk_a = CitationEvidence(
        evidence_id="cite_1_a",
        document_id=1,
        document_filename="paper_a.pdf",
        page_number=1,
        chunk_id="chunk_a",
        chunk_index=0,
        start_char=0,
        end_char=100,
        text="Dense vectors capture semantic nuance.",
        score=0.85,
    )
    chunk_b = CitationEvidence(
        evidence_id="cite_2_b",
        document_id=2,
        document_filename="paper_b.pdf",
        page_number=3,
        chunk_id="chunk_b",
        chunk_index=1,
        start_char=200,
        end_char=350,
        text="BM25 excels at exact keyword matching.",
        score=0.75,
    )

    # Query 1 returns chunk_a; Query 2 returns chunk_a and chunk_b
    mock_retrieval_service.search.side_effect = [
        RetrievalResponse(query="q1", total_results=1, mode="hybrid", results=[chunk_a]),
        RetrievalResponse(query="q2", total_results=2, mode="hybrid", results=[chunk_a, chunk_b]),
    ]

    aggregator = EvidenceAggregator(retrieval_service=mock_retrieval_service)
    aggregated = await aggregator.aggregate(project_id=1, subqueries=["q1", "q2"])

    assert len(aggregated) == 2
    # chunk_a should be retrieved by both q1 and q2
    chunk_a_agg = next(c for c in aggregated if c.chunk_id == "chunk_a")
    assert "q1" in chunk_a_agg.retrieved_by_queries
    assert "q2" in chunk_a_agg.retrieved_by_queries
    assert chunk_a_agg.aggregated_score > chunk_a.score


@pytest.mark.asyncio
async def test_aggregator_cross_document_preservation():
    mock_retrieval_service = AsyncMock()

    # Identical text in Doc 1 page 1 vs Doc 2 page 5
    shared_text = "The model achieved 94% accuracy on the benchmark."
    chunk_1 = CitationEvidence(
        evidence_id="cite_1_c1",
        document_id=1,
        document_filename="team_alpha.pdf",
        page_number=1,
        chunk_id="chunk_1",
        chunk_index=0,
        start_char=0,
        end_char=len(shared_text),
        text=shared_text,
        score=0.90,
    )
    chunk_2 = CitationEvidence(
        evidence_id="cite_2_c2",
        document_id=2,
        document_filename="team_beta.pdf",
        page_number=5,
        chunk_id="chunk_2",
        chunk_index=4,
        start_char=100,
        end_char=100 + len(shared_text),
        text=shared_text,
        score=0.90,
    )

    mock_retrieval_service.search.return_value = RetrievalResponse(
        query="accuracy", total_results=2, mode="hybrid", results=[chunk_1, chunk_2]
    )

    aggregator = EvidenceAggregator(retrieval_service=mock_retrieval_service)
    aggregated = await aggregator.aggregate(project_id=1, subqueries=["accuracy"])

    # Both must survive with their distinct document_id and chunk_id
    assert len(aggregated) == 2
    doc_ids = {c.document_id for c in aggregated}
    assert doc_ids == {1, 2}


@pytest.mark.asyncio
async def test_aggregator_fail_fast_on_error():
    mock_retrieval_service = AsyncMock()
    mock_retrieval_service.search.side_effect = VectorStoreError("Qdrant collection unavailable")

    aggregator = EvidenceAggregator(retrieval_service=mock_retrieval_service)
    with pytest.raises(VectorStoreError):
        await aggregator.aggregate(project_id=1, subqueries=["q1", "q2"])


def test_evidence_selector_budget_ceiling():
    selector = EvidenceSelector(max_chunks=2, max_total_chars=1000)

    cands = [
        AggregatedEvidence(
            evidence_id="1", document_id=1, document_filename="f1", page_number=1,
            chunk_id="c1", chunk_index=0, start_char=0, end_char=50,
            text="Text chunk 1", score=0.9, aggregated_score=0.9,
        ),
        AggregatedEvidence(
            evidence_id="2", document_id=2, document_filename="f2", page_number=1,
            chunk_id="c2", chunk_index=0, start_char=0, end_char=50,
            text="Text chunk 2", score=0.8, aggregated_score=0.8,
        ),
        AggregatedEvidence(
            evidence_id="3", document_id=3, document_filename="f3", page_number=1,
            chunk_id="c3", chunk_index=0, start_char=0, end_char=50,
            text="Text chunk 3", score=0.7, aggregated_score=0.7,
        ),
    ]

    selected = selector.select(cands)
    assert len(selected) == 2
    assert selected[0].evidence_id == "1"
    assert selected[1].evidence_id == "2"


def test_evidence_selector_diversity():
    # 5 chunks from Doc 1, 1 chunk from Doc 2
    selector = EvidenceSelector(max_chunks=5, max_chunks_per_doc=2, max_total_chars=10000)

    cands = [
        AggregatedEvidence(
            evidence_id=f"1_{i}", document_id=1, document_filename="f1", page_number=1,
            chunk_id=f"c1_{i}", chunk_index=i, start_char=0, end_char=50,
            text=f"Text 1 {i}", score=0.9 - 0.01 * i, aggregated_score=0.9 - 0.01 * i,
        )
        for i in range(5)
    ]
    cand_doc2 = AggregatedEvidence(
        evidence_id="2_0", document_id=2, document_filename="f2", page_number=1,
        chunk_id="c2_0", chunk_index=0, start_char=0, end_char=50,
        text="Text from Doc 2", score=0.85, aggregated_score=0.85,
    )
    cands.append(cand_doc2)

    selected = selector.select(cands)
    # Doc 2 should be included because Doc 1 is capped to 2 in pass 1, leaving room for Doc 2
    doc_ids = [c.document_id for c in selected]
    assert 2 in doc_ids


@pytest.mark.asyncio
async def test_empty_retrieval_aggregation():
    mock_retrieval_service = AsyncMock()
    mock_retrieval_service.search.return_value = RetrievalResponse(
        query="empty", total_results=0, mode="hybrid", results=[]
    )

    aggregator = EvidenceAggregator(retrieval_service=mock_retrieval_service)
    aggregated = await aggregator.aggregate(project_id=1, subqueries=["q1"])
    assert aggregated == []

    selector = EvidenceSelector()
    assert selector.select([]) == []
