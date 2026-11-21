from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import TypedDict

from app.research.schemas import ResearchResponse
from app.developer.schemas import DeveloperResponse


class IntentType(str, Enum):
    RESEARCH = "research"
    DEVELOPER = "developer"
    DIRECT_QA = "direct_qa"


class IntentClassificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: IntentType = Field(..., description="The classified primary intent")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score")
    rationale: str = Field(default="", description="Brief explanation of intent routing")


class OrchestratorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(..., min_length=1, max_length=4000, description="User instruction or query prompt")
    session_id: Optional[int] = Field(default=None, description="Optional existing session ID to continue")
    forced_intent: Optional[IntentType] = Field(default=None, description="Optional override for routing intent")
    developer_params: Optional[Dict[str, Any]] = Field(default=None, description="Optional developer intelligence parameters (mode, target_files, etc.)")
    research_params: Optional[Dict[str, Any]] = Field(default=None, description="Optional research parameters (response_depth, etc.)")


class OrchestratorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: int = Field(..., description="The database session ID associated with this turn")
    intent: IntentType = Field(..., description="The intent branch executed")
    answer: str = Field(..., description="Synthesized textual response")
    research_result: Optional[ResearchResponse] = Field(default=None, description="Detailed research outcome if routed to research")
    developer_result: Optional[DeveloperResponse] = Field(default=None, description="Detailed developer outcome if routed to developer")
    execution_trace: List[str] = Field(default_factory=list, description="Bounded audit trail of orchestration steps")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Execution performance metrics and call budgets")


class OrchestratorState(TypedDict, total=False):
    project_id: int
    session_id: int
    prompt: str
    forced_intent: Optional[str]
    intent: Optional[str]
    developer_params: Optional[Dict[str, Any]]
    research_params: Optional[Dict[str, Any]]
    memory_context: Optional[str]
    answer: str
    research_result: Optional[Dict[str, Any]]
    developer_result: Optional[Dict[str, Any]]
    execution_trace: List[str]
    llm_calls_made: int
    error: Optional[str]
