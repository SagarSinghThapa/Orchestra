from typing import Any, Optional
from typing_extensions import TypedDict


class ResearchState(TypedDict, total=False):
    """
    Pure serializable state dictionary for the LangGraph Research Subgraph.
    Excludes database connections, HTTP clients, and unpicklable objects.
    """
    project_id: int
    question: str
    max_subqueries: int
    max_evidence: int
    response_depth: str

    # Execution telemetry and tracking
    subqueries: list[str]
    retrieved_evidence: list[dict[str, Any]]
    selected_evidence: list[dict[str, Any]]
    draft_answer: Optional[dict[str, Any]]
    verified_claims: list[dict[str, Any]]
    verified_citations: list[dict[str, Any]]

    status: str
    answer: str
    repair_count: int
    error: Optional[str]
    metadata: dict[str, Any]
