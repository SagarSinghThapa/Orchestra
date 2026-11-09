from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ExecutionMode(str, Enum):
    REGRESSION = "regression"
    REAL_PROVIDER = "real_provider"


class EvaluationMetricDirection(str, Enum):
    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"


class EvaluationMetricValue(BaseModel):
    name: str = Field(..., description="Unique metric identifier, e.g. 'recall_at_5'")
    value: float = Field(..., description="Normalized metric score or measured value")
    unit: str = Field(default="", description="Unit of measurement: '%', 'ms', 'ratio'")
    direction: EvaluationMetricDirection = Field(
        default=EvaluationMetricDirection.HIGHER_IS_BETTER,
        description="Optimization direction for regression comparisons",
    )
    threshold: Optional[float] = Field(default=None, description="Optional pass/fail threshold")
    passed: Optional[bool] = Field(default=None, description="Whether metric met threshold")


class GoldenCase(BaseModel):
    case_id: str = Field(..., description="Stable alphanumeric case identifier, e.g. 'rag_001'")
    category: str = Field(..., description="Evaluation pillar: 'retrieval', 'research', 'developer', 'orchestrator'")
    description: str = Field(default="", description="Human-readable scenario description")
    input_data: Dict[str, Any] = Field(..., description="Case payload (query, code snippet, prompt)")
    ground_truth: Dict[str, Any] = Field(..., description="Expected outputs, relevant IDs, routes, syntax")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GoldenDataset(BaseModel):
    dataset_id: str = Field(..., description="Unique dataset identifier")
    dataset_version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$", description="SemVer dataset version, e.g. '1.0.0'")
    description: str = Field(default="")
    cases: List[GoldenCase] = Field(..., min_length=1)


class EvaluationRunCreate(BaseModel):
    suite_id: str = Field(..., description="Evaluation suite identifier from static registry")
    project_id: Optional[int] = Field(default=None, description="Optional project ID for project-scoped evaluations")
    execution_mode: ExecutionMode = Field(default=ExecutionMode.REGRESSION, description="Execution mode: 'regression' ($0.00) or 'real_provider'")
    max_cases: int = Field(default=20, ge=1, le=25, description="Max cases to evaluate (capped at 25)")


class EvaluationCaseResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: str
    case_id: str
    status: str  # "passed" | "failed" | "error" | "skipped"
    duration_ms: float
    metrics: Dict[str, float]
    failure_reason: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class EvaluationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: Optional[int] = None
    created_by_user_id: Optional[int] = None
    suite_id: str
    dataset_id: str
    dataset_version: str
    dataset_sha256: str
    execution_mode: str
    model_name: str
    metric_schema_version: str
    target_type: str
    status: str  # "pending" | "running" | "completed" | "failed"
    is_baseline: bool
    total_cases: int
    passed_cases: int
    failed_cases: int
    duration_ms: float
    summary_metrics: Dict[str, float]
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    case_results: Optional[List[EvaluationCaseResultResponse]] = None


class BenchmarkSuiteInfo(BaseModel):
    suite_id: str
    name: str
    description: str
    target_type: str
    supported_scope: str  # "system", "project", or "both"
    default_dataset_id: str
    default_dataset_version: str
    case_count: int
    metrics: List[str]
