from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class ResearchStatus(str, Enum):
    COMPLETED = "completed"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    FAILED = "failed"


class ResearchRequest(BaseModel):
    """
    Public request schema for initiating a project-scoped research task.
    Enforces strict input bounds and prohibits unauthorized internal parameters.
    """
    question: str = Field(
        ...,
        max_length=1000,
        description="User research inquiry",
    )
    max_subqueries: int = Field(
        default=3,
        ge=1,
        le=4,
        description="Max total decomposed search queries, including original question",
    )
    max_evidence: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Max candidate evidence chunks for synthesis",
    )
    response_depth: str = Field(
        default="standard",
        pattern="^(brief|standard|detailed)$",
        description="Target depth of the generated research response",
    )

    model_config = ConfigDict(extra="forbid")


class SubQuery(BaseModel):
    """Decomposed subquery representation."""
    id: str
    query: str
    rationale: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class ResearchPlan(BaseModel):
    """Structured plan produced by ResearchPlanner."""
    goal: str
    subqueries: list[str] = Field(..., min_length=1, max_length=4)
    strategy_notes: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class DraftClaim(BaseModel):
    """Claim-level statement with self-attributed evidence IDs produced by LLM."""
    claim_text: str = Field(..., min_length=1, max_length=500)
    supporting_evidence_ids: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class DraftResearchAnswer(BaseModel):
    """Draft structured output emitted by synthesis LLM before deterministic verification."""
    claims: list[DraftClaim] = Field(default_factory=list, min_length=0, max_length=15)
    summary_notes: Optional[str] = None
    has_sufficient_evidence: bool = True

    model_config = ConfigDict(extra="forbid")


class VerifiedCitation(BaseModel):
    """
    Verified citation metadata with immutable provenance directly from Qdrant/PostgreSQL.
    Guarantees document existence, project ownership, exact page number, and source offsets.
    """
    citation_id: str  # e.g. "[C1]", "[C2]"
    evidence_id: str  # e.g. "evidence_0"
    document_id: int
    document_filename: str
    page_number: int
    chunk_id: str
    start_char: int
    end_char: int
    text: str
    score: float

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class ResearchClaim(BaseModel):
    """Verified factual claim with resolved citation labels."""
    claim_text: str
    citation_ids: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class ResearchMetadata(BaseModel):
    """Sanitized research execution telemetry."""
    model: str
    subqueries_executed: list[str]
    total_evidence_retrieved: int
    verified_citations_count: int
    execution_time_ms: float
    llm_call_count: int

    model_config = ConfigDict(extra="forbid")


class ResearchResponse(BaseModel):
    """
    Structured public research response contract.
    Guarantees deterministic answer assembly from verified claims without hallucinated extra prose.
    """
    question: str
    status: ResearchStatus
    answer: str
    claims: list[ResearchClaim]
    citations: list[VerifiedCitation]
    evidence_count: int
    metadata: ResearchMetadata

    model_config = ConfigDict(extra="forbid")
