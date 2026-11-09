from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SummaryStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class SessionSummarySchema(BaseModel):
    """Public validated representation of a persisted session summary."""
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    session_id: int
    project_id: int
    summary_text: str
    message_watermark_id: int
    message_count_summarized: int
    status: SummaryStatus
    version: int
    created_at: datetime
    updated_at: datetime


class ContextAssemblerConfig(BaseModel):
    """Configuration limits for context assembly and summarization."""
    model_config = ConfigDict(extra="forbid")

    window_size: int = Field(default=20, ge=2, le=100, description="Max messages in sliding window")
    summarization_threshold: int = Field(default=30, ge=5, le=200, description="Unsummarized messages triggering summarization")
    max_project_summaries: int = Field(default=5, ge=0, le=20, description="Max sibling session summaries to include")
    max_context_chars: int = Field(default=4000, ge=500, le=16000, description="Strict unbreachable character limit on assembled context")
    max_messages_per_summarization: int = Field(default=40, ge=5, le=100, description="Max messages processed in one summarization call")
    max_summarization_input_chars: int = Field(default=12000, ge=1000, le=50000, description="Max input characters sent to summarizer LLM")


class MemoryContext(BaseModel):
    """Assembled three-tier memory context ready for orchestrator injection."""
    model_config = ConfigDict(extra="forbid")

    project_context: str = Field(default="", description="Aggregated summaries from sibling sessions")
    session_summary: str = Field(default="", description="Incremental summary of older messages in current session")
    recent_messages: List[Dict[str, Any]] = Field(default_factory=list, description="Sliding window of recent message dicts")
    total_chars: int = Field(default=0, ge=0, description="Total character count of assembled context (guaranteed <= max_context_chars)")


class MemoryStats(BaseModel):
    """Clean telemetry and inspection schema without exposing internal prompt layout."""
    model_config = ConfigDict(extra="forbid")

    session_id: int
    summary_exists: bool
    summary_version: int
    message_watermark_id: int
    messages_summarized_count: int
    sliding_window_message_count: int
    assembled_context_chars: int


class SummarizationRequest(BaseModel):
    """Internal request to the summarizer service."""
    model_config = ConfigDict(extra="forbid")

    session_id: int
    project_id: int
    existing_summary: Optional[str] = None
    messages_to_summarize: List[Dict[str, Any]] = Field(default_factory=list)


class SummarizationResponse(BaseModel):
    """Structured response from the summarizer LLM call."""
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(..., min_length=1, max_length=4000, description="Compressed conversation summary")
    key_topics: List[str] = Field(default_factory=list, max_length=10, description="Key topics discussed")
    decisions_made: List[str] = Field(default_factory=list, max_length=10, description="Decisions or conclusions reached")

