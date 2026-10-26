from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class SearchMode(str, Enum):
    HYBRID = "hybrid"
    DENSE = "dense"
    SPARSE = "sparse"


class SearchQuery(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000, description="User search query string")
    limit: int = Field(default=5, ge=1, le=50, description="Maximum number of citation evidence chunks to return")
    mode: SearchMode = Field(default=SearchMode.HYBRID, description="Retrieval mode: hybrid, dense, or sparse")
    dense_weight: float = Field(default=1.0, ge=0.0, description="Weight multiplier for dense vector retrieval")
    sparse_weight: float = Field(default=1.0, ge=0.0, description="Weight multiplier for sparse BM25 retrieval")
    rerank: bool = Field(default=False, description="Whether to apply secondary reranking")
    document_ids: Optional[list[int]] = Field(default=None, description="Optional filter to restrict search to specific documents")

    model_config = ConfigDict(extra="forbid")


class SearchResultChunk(BaseModel):
    """
    Internal retrieval candidate representation across dense, sparse, and fusion channels.
    """
    chunk_id: str
    document_id: int
    project_id: int
    text: str
    chunk_index: int
    page_number: int
    start_char: int
    end_char: int
    score: float
    source_engine: str  # "dense", "sparse", or "hybrid"

    # Transparent retrieval metadata (never fabricated)
    dense_score: Optional[float] = None
    dense_rank: Optional[int] = None
    sparse_score: Optional[float] = None
    sparse_rank: Optional[int] = None
    fusion_score: Optional[float] = None
    rerank_score: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class CitationEvidence(BaseModel):
    """
    Citation-ready evidence structure returned to clients and the Research Agent.
    Guarantees exact provenance: filename, 1-indexed page number, and source character offsets.
    """
    evidence_id: str
    document_id: int
    document_filename: str
    page_number: int
    chunk_id: str
    chunk_index: int
    start_char: int
    end_char: int
    text: str
    score: float

    # Optional channel metadata
    dense_score: Optional[float] = None
    sparse_score: Optional[float] = None
    dense_rank: Optional[int] = None
    sparse_rank: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class RetrievalResponse(BaseModel):
    """
    Public response contract for the retrieval API.
    """
    query: str
    total_results: int
    mode: str
    results: list[CitationEvidence]

    model_config = ConfigDict(from_attributes=True)
