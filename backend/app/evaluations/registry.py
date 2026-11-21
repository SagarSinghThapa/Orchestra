from typing import Dict, List, Optional

from app.evaluations.evaluators.base import BaseEvaluator
from app.evaluations.evaluators.developer import DeveloperASTEvaluator
from app.evaluations.evaluators.orchestrator import OrchestratorEvaluator
from app.evaluations.evaluators.research import ResearchEvaluator
from app.evaluations.evaluators.retrieval import RetrievalEvaluator
from app.evaluations.schemas import BenchmarkSuiteInfo, EvaluationMetricDirection


class EvaluationRegistry:
    """
    Static, backend-controlled registry defining benchmark suites, supported scopes,
    metric optimization directions, and evaluator bindings.
    """

    METRIC_DIRECTIONS: Dict[str, EvaluationMetricDirection] = {
        "recall_at_5": EvaluationMetricDirection.HIGHER_IS_BETTER,
        "precision_at_5": EvaluationMetricDirection.HIGHER_IS_BETTER,
        "reciprocal_rank": EvaluationMetricDirection.HIGHER_IS_BETTER,
        "citation_precision": EvaluationMetricDirection.HIGHER_IS_BETTER,
        "claim_grounding_rate": EvaluationMetricDirection.HIGHER_IS_BETTER,
        "benchmark_hallucination_rate": EvaluationMetricDirection.LOWER_IS_BETTER,
        "rag_faithfulness": EvaluationMetricDirection.HIGHER_IS_BETTER,
        "ast_syntax_validity": EvaluationMetricDirection.HIGHER_IS_BETTER,
        "patch_applicability": EvaluationMetricDirection.HIGHER_IS_BETTER,
        "diff_scope_compliance": EvaluationMetricDirection.HIGHER_IS_BETTER,
        "preview_zero_mutation": EvaluationMetricDirection.HIGHER_IS_BETTER,
        "routing_accuracy": EvaluationMetricDirection.HIGHER_IS_BETTER,
        "llm_budget_compliance": EvaluationMetricDirection.HIGHER_IS_BETTER,
        "context_cap_compliance": EvaluationMetricDirection.HIGHER_IS_BETTER,
        "turn_latency_ms": EvaluationMetricDirection.LOWER_IS_BETTER,
    }

    METRIC_UNITS: Dict[str, str] = {
        "recall_at_5": "%",
        "precision_at_5": "%",
        "reciprocal_rank": "ratio",
        "citation_precision": "%",
        "claim_grounding_rate": "%",
        "benchmark_hallucination_rate": "%",
        "rag_faithfulness": "%",
        "ast_syntax_validity": "%",
        "patch_applicability": "%",
        "diff_scope_compliance": "%",
        "preview_zero_mutation": "%",
        "routing_accuracy": "%",
        "llm_budget_compliance": "%",
        "context_cap_compliance": "%",
        "turn_latency_ms": "ms",
    }

    SUITES: Dict[str, BenchmarkSuiteInfo] = {
        "rag_faithfulness": BenchmarkSuiteInfo(
            suite_id="rag_faithfulness",
            name="RAG Faithfulness & Citations",
            description="Evaluates citation grounding, claim verification, and refusal accuracy",
            target_type="research",
            supported_scope="system",
            default_dataset_id="orchestra_research_grounding",
            default_dataset_version="1.0.0",
            case_count=5,
            metrics=["citation_precision", "claim_grounding_rate", "benchmark_hallucination_rate", "rag_faithfulness"],
        ),
        "retrieval_ranking": BenchmarkSuiteInfo(
            suite_id="retrieval_ranking",
            name="Retrieval Ranking & MRR",
            description="Evaluates vector and hybrid search ranking quality against labeled relevant chunks",
            target_type="research",
            supported_scope="system",
            default_dataset_id="orchestra_retrieval_golden",
            default_dataset_version="1.0.0",
            case_count=5,
            metrics=["recall_at_5", "precision_at_5", "reciprocal_rank"],
        ),
        "coding_ast": BenchmarkSuiteInfo(
            suite_id="coding_ast",
            name="Coding AST & Safety",
            description="Evaluates Python AST parsing, diff line reconstruction, scope limits, and hash safety",
            target_type="developer",
            supported_scope="system",
            default_dataset_id="orchestra_developer_ast",
            default_dataset_version="1.0.0",
            case_count=5,
            metrics=["ast_syntax_validity", "patch_applicability", "diff_scope_compliance", "preview_zero_mutation"],
        ),
        "orchestrator_routing": BenchmarkSuiteInfo(
            suite_id="orchestrator_routing",
            name="Orchestrator Routing & Latency",
            description="Evaluates intent classification accuracy, budget compliance, and turn latency",
            target_type="orchestrator",
            supported_scope="system",
            default_dataset_id="orchestra_routing_golden",
            default_dataset_version="1.0.0",
            case_count=10,
            metrics=["routing_accuracy", "llm_budget_compliance", "context_cap_compliance", "turn_latency_ms"],
        ),
        "full_system": BenchmarkSuiteInfo(
            suite_id="full_system",
            name="Full System Benchmark Suite",
            description="Executes comprehensive end-to-end evaluation across all four intelligence pillars",
            target_type="system",
            supported_scope="system",
            default_dataset_id="orchestra_golden_benchmark",
            default_dataset_version="1.0.0",
            case_count=20,  # Capped at exactly 20 cases (5+5+5+5)
            metrics=["recall_at_5", "citation_precision", "ast_syntax_validity", "routing_accuracy", "turn_latency_ms"],
        ),
        "project_invariants": BenchmarkSuiteInfo(
            suite_id="project_invariants",
            name="Project Invariants & Provenance",
            description="Evaluates document citation provenance, context caps, and response latency on project corpus",
            target_type="project",
            supported_scope="project",
            default_dataset_id="project_live_corpus",
            default_dataset_version="1.0.0",
            case_count=5,
            metrics=["citation_precision", "context_cap_compliance", "turn_latency_ms"],
        ),
    }

    DATASET_FILENAME_MAP: Dict[str, str] = {
        "rag_faithfulness": "research_grounding_v1.json",
        "retrieval_ranking": "retrieval_golden_v1.json",
        "coding_ast": "developer_ast_v1.json",
        "orchestrator_routing": "orchestrator_routing_v1.json",
    }

    @classmethod
    def get_suite(cls, suite_id: str) -> Optional[BenchmarkSuiteInfo]:
        return cls.SUITES.get(suite_id)

    @classmethod
    def list_suites(cls) -> List[BenchmarkSuiteInfo]:
        return list(cls.SUITES.values())

    @classmethod
    def get_evaluator(cls, suite_id: str) -> BaseEvaluator:
        if suite_id in ("rag_faithfulness", "project_invariants"):
            return ResearchEvaluator()
        elif suite_id == "retrieval_ranking":
            return RetrievalEvaluator()
        elif suite_id == "coding_ast":
            return DeveloperASTEvaluator()
        elif suite_id == "orchestrator_routing":
            return OrchestratorEvaluator()
        elif suite_id == "full_system":
            # Composite evaluator handles multi-suite execution
            return OrchestratorEvaluator()
        else:
            raise ValueError(f"Unknown evaluation suite: {suite_id}")
