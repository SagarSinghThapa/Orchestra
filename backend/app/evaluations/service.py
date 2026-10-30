import asyncio
from datetime import datetime
import hashlib
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.evaluations.evaluators.base import BaseEvaluator
from app.evaluations.evaluators.developer import DeveloperASTEvaluator
from app.evaluations.evaluators.orchestrator import OrchestratorEvaluator
from app.evaluations.evaluators.research import ResearchEvaluator
from app.evaluations.evaluators.retrieval import RetrievalEvaluator
from app.evaluations.loader import DatasetLoader
from app.evaluations.metrics.latency import compute_latency_summary
from app.evaluations.registry import EvaluationRegistry
from app.evaluations.schemas import (
    EvaluationCaseResultResponse,
    EvaluationRunCreate,
    EvaluationRunResponse,
    GoldenCase,
    GoldenDataset,
)
from app.models.document import Document, DocumentStatus
from app.models.evaluation import EvaluationCaseResult, EvaluationRun
from app.models.project import Project
from app.models.user import User, UserRole


class EvaluationService:
    """
    Central orchestration service for benchmark evaluation runs,
    enforcing tenancy, sequential execution, deadlines, and persistence.
    """

    def __init__(
        self,
        db: Session,
        case_timeout_s: float = 10.0,
        global_timeout_s: float = 60.0,
    ) -> None:
        self.db = db
        self.case_timeout_s = case_timeout_s
        self.global_timeout_s = global_timeout_s

    @staticmethod
    def resolve_git_sha(repo_root_override: Optional[Path] = None) -> str:
        """
        Resolves application Git commit SHA without spawning runtime subprocesses.
        Precedence:
        1. settings.app_git_sha
        2. os.getenv("APP_GIT_SHA")
        3. Safe read-only inspection of .git/HEAD (symbolic ref, packed-refs, or detached HEAD)
        4. "development" fallback
        """
        if settings.app_git_sha:
            return settings.app_git_sha

        env_sha = os.getenv("APP_GIT_SHA")
        if env_sha and env_sha.strip():
            return env_sha.strip()

        # Locate repository root containing .git directory
        try:
            repo_root: Optional[Path] = None
            if repo_root_override is not None:
                repo_root = repo_root_override
            else:
                curr = Path(__file__).resolve().parent
                for _ in range(6):
                    if (curr / ".git").exists():
                        repo_root = curr
                        break
                    if curr == curr.parent:
                        break
                    curr = curr.parent

            if repo_root:
                git_dir = repo_root / ".git"
                # Handle gitdir file (e.g. git worktrees or submodules)
                if git_dir.is_file():
                    gitdir_content = git_dir.read_text(encoding="utf-8").strip()
                    if gitdir_content.startswith("gitdir:"):
                        git_dir = (repo_root / gitdir_content[7:].strip()).resolve()

                head_path = git_dir / "HEAD"
                if head_path.is_file():
                    head_content = head_path.read_text(encoding="utf-8").strip()
                    if head_content.startswith("ref:"):
                        ref_rel = head_content[4:].strip()
                        ref_path = git_dir / ref_rel
                        if ref_path.is_file():
                            ref_sha = ref_path.read_text(encoding="utf-8").strip()
                            if ref_sha:
                                return ref_sha[:12]
                        # Check packed-refs fallback
                        packed_refs = git_dir / "packed-refs"
                        if packed_refs.is_file():
                            for line in packed_refs.read_text(encoding="utf-8").splitlines():
                                line = line.strip()
                                if line and not line.startswith("#") and not line.startswith("^"):
                                    parts = line.split()
                                    if len(parts) >= 2 and parts[1] == ref_rel:
                                        return parts[0][:12]
                    elif len(head_content) >= 7 and all(c in "0123456789abcdefABCDEF" for c in head_content[:12]):
                        return head_content[:12]
        except Exception:
            pass

        return "development"

    async def execute_run(
        self,
        payload: EvaluationRunCreate,
        user: User,
    ) -> EvaluationRunResponse:
        """
        Executes a benchmark suite under strict tenant isolation and deadlines.
        """
        suite = EvaluationRegistry.get_suite(payload.suite_id)
        if not suite:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown evaluation suite: {payload.suite_id}",
            )

        # 1. Tenancy & Ownership-Before-Cost Verification
        if payload.project_id is not None:
            if suite.supported_scope not in ("project", "both"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Suite '{payload.suite_id}' does not support project scope",
                )
            project = (
                self.db.query(Project)
                .filter(Project.id == payload.project_id, Project.owner_id == user.id)
                .first()
            )
            if not project:
                # Strictly return 404 before any dataset or evaluation computation
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Project {payload.project_id} not found",
                )
        else:
            if suite.supported_scope not in ("system", "both"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Suite '{payload.suite_id}' requires a project_id",
                )
            if user.role != UserRole.ADMIN.value:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="System benchmark execution requires admin privileges",
                )

        # 2. Case Count Boundary Enforcement
        if payload.max_cases > 25:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Requested cases exceed the maximum allowed ceiling of 25",
            )

        # 3. Dataset Loading
        cases_to_run: List[tuple[GoldenCase, BaseEvaluator]] = []
        dataset_id: str
        dataset_version: str
        dataset_sha256: str

        if payload.suite_id == "full_system":
            # Composite suite: 5 cases from each of the 4 golden datasets = 20 cases total
            dataset_id = "orchestra_golden_benchmark"
            dataset_version = "1.0.0"
            combined_bytes = bytearray()

            suites_and_evaluators = [
                ("retrieval_golden_v1.json", RetrievalEvaluator()),
                ("research_grounding_v1.json", ResearchEvaluator()),
                ("developer_ast_v1.json", DeveloperASTEvaluator()),
                ("orchestrator_routing_v1.json", OrchestratorEvaluator()),
            ]
            for ds_file, evaluator in suites_and_evaluators:
                ds, ds_hash = DatasetLoader.load_dataset(ds_file)
                combined_bytes.extend(ds_hash.encode("utf-8"))
                for c in ds.cases[:5]:
                    cases_to_run.append((c, evaluator))

            dataset_sha256 = hashlib.sha256(combined_bytes).hexdigest()
        elif payload.suite_id == "project_invariants":
            dataset_id = "project_live_corpus"
            dataset_version = "1.0.0"
            dataset_sha256 = hashlib.sha256(f"proj_{payload.project_id}".encode("utf-8")).hexdigest()
            # Construct 5 invariant check cases against project corpus
            docs = (
                self.db.query(Document)
                .filter(Document.project_id == payload.project_id, Document.status == DocumentStatus.INDEXED.value)
                .limit(5)
                .all()
            )
            evaluator = ResearchEvaluator()
            for i, doc in enumerate(docs, start=1):
                case = GoldenCase(
                    case_id=f"proj_inv_{i}",
                    category="research",
                    description=f"Provenance check for document {doc.original_filename}",
                    input_data={
                        "evidence_pool": [
                            {"chunk_id": f"doc_{doc.id}_chk_0", "document_filename": doc.original_filename, "text": "Valid indexed content."}
                        ],
                        "draft_answer": {
                            "has_sufficient_evidence": True,
                            "claims": [
                                {"claim_text": f"Grounded statement from {doc.original_filename}", "supporting_evidence_ids": [f"doc_{doc.id}_chk_0"]}
                            ],
                        },
                    },
                    ground_truth={
                        "expect_sufficient_evidence": True,
                        "expected_citations": [f"doc_{doc.id}_chk_0"],
                        "min_grounded_claims": 1,
                        "max_stripped_claims": 0,
                    },
                )
                cases_to_run.append((case, evaluator))
            # If no docs, add empty refusal case
            if not cases_to_run:
                cases_to_run.append(
                    (
                        GoldenCase(
                            case_id="proj_inv_empty",
                            category="research",
                            description="Refusal verification on empty project corpus",
                            input_data={"evidence_pool": [], "draft_answer": {"has_sufficient_evidence": False, "claims": []}},
                            ground_truth={"expect_sufficient_evidence": False, "expected_citations": [], "min_grounded_claims": 0, "max_stripped_claims": 0, "expect_canonical_refusal": True},
                        ),
                        evaluator,
                    )
                )
        else:
            filename = EvaluationRegistry.DATASET_FILENAME_MAP[payload.suite_id]
            ds, dataset_sha256 = DatasetLoader.load_dataset(filename)
            dataset_id = ds.dataset_id
            dataset_version = ds.dataset_version
            evaluator = EvaluationRegistry.get_evaluator(payload.suite_id)
            for c in ds.cases[: payload.max_cases]:
                cases_to_run.append((c, evaluator))

        # Enforce max_cases slice
        cases_to_run = cases_to_run[: payload.max_cases]

        # 4. Initialize Run Record
        run_id = str(uuid.uuid4())
        git_sha = self.resolve_git_sha()
        model_name = "deterministic-test-provider" if payload.execution_mode.value == "regression" else "production-provider"

        run = EvaluationRun(
            id=run_id,
            project_id=payload.project_id,
            created_by_user_id=user.id,
            suite_id=payload.suite_id,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            dataset_sha256=dataset_sha256,
            execution_mode=payload.execution_mode.value,
            model_name=model_name,
            metric_schema_version="1.0.0",
            target_type=suite.target_type,
            status="running",
            is_baseline=False,
            total_cases=len(cases_to_run),
            passed_cases=0,
            failed_cases=0,
            duration_ms=0.0,
            summary_metrics={},
            created_at=datetime.utcnow(),
        )
        self.db.add(run)
        self.db.commit()

        # 5. Sequential Execution with Deadlines
        case_results: List[EvaluationCaseResult] = []
        latencies: List[float] = []
        metric_sums: Dict[str, float] = {}
        metric_counts: Dict[str, int] = {}

        global_t0 = time.perf_counter()
        run_status = "completed"
        run_error_message: Optional[str] = None

        for idx, (case, evaluator) in enumerate(cases_to_run):
            # Check global run deadline (60s)
            elapsed_global = time.perf_counter() - global_t0
            if elapsed_global >= self.global_timeout_s:
                # Mark this and remaining cases as skipped
                run_status = "failed"
                run_error_message = f"Global evaluation deadline exceeded ({self.global_timeout_s}s)"
                for skipped_case, _ in cases_to_run[idx:]:
                    cr = EvaluationCaseResult(
                        run_id=run_id,
                        case_id=skipped_case.case_id,
                        status="skipped",
                        duration_ms=0.0,
                        metrics={},
                        failure_reason="Global run deadline exceeded",
                        details=None,
                    )
                    case_results.append(cr)
                break

            # Execute case with per-case timeout (10s)
            try:
                result_resp = await asyncio.wait_for(
                    evaluator.evaluate_case(case, run_id=run_id),
                    timeout=self.case_timeout_s,
                )
                case_status = result_resp.status
                duration = result_resp.duration_ms
                metrics = result_resp.metrics
                fail_reason = result_resp.failure_reason
                details = result_resp.details
            except asyncio.TimeoutError:
                case_status = "error"
                duration = self.case_timeout_s * 1000.0
                metrics = {}
                fail_reason = f"CaseTimeoutError: Execution exceeded {self.case_timeout_s}s"
                details = None
            except Exception as e:
                case_status = "error"
                duration = 0.0
                metrics = {}
                fail_reason = f"ExecutionError: {type(e).__name__} - {str(e)[:100]}"
                details = None

            cr = EvaluationCaseResult(
                run_id=run_id,
                case_id=case.case_id,
                status=case_status,
                duration_ms=duration,
                metrics=metrics,
                failure_reason=fail_reason,
                details=details,
            )
            case_results.append(cr)

            # Accumulate executed metrics for mean calculation
            if case_status in ("passed", "failed"):
                latencies.append(duration)
                for m_name, m_val in metrics.items():
                    metric_sums[m_name] = metric_sums.get(m_name, 0.0) + float(m_val)
                    metric_counts[m_name] = metric_counts.get(m_name, 0) + 1

        total_duration_ms = (time.perf_counter() - global_t0) * 1000.0

        # 6. Aggregate Summary Metrics
        summary_metrics: Dict[str, float] = {}
        for m_name, m_sum in metric_sums.items():
            count = metric_counts.get(m_name, 1)
            summary_metrics[m_name] = m_sum / count if count > 0 else 0.0

        if latencies:
            summary_metrics.update(compute_latency_summary(latencies))

        passed_count = sum(1 for cr in case_results if cr.status == "passed")
        failed_count = sum(1 for cr in case_results if cr.status in ("failed", "error", "skipped"))

        if any(cr.status in ("error", "skipped") for cr in case_results):
            run_status = "failed"

        # 7. Finalize & Persist Run
        run.status = run_status
        run.passed_cases = passed_count
        run.failed_cases = failed_count
        run.duration_ms = total_duration_ms
        run.summary_metrics = summary_metrics
        run.error_message = run_error_message
        run.completed_at = datetime.utcnow()

        self.db.add_all(case_results)
        self.db.commit()
        self.db.refresh(run)

        # Convert to response
        response = EvaluationRunResponse.model_validate(run)
        response.case_results = [
            EvaluationCaseResultResponse.model_validate(cr) for cr in run.case_results
        ]
        return response

    def list_runs_scoped(
        self,
        user: User,
        project_id: Optional[int] = None,
        suite_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[EvaluationRunResponse]:
        """
        Lists runs strictly scoped to user tenancy and role boundaries.
        """
        query = self.db.query(EvaluationRun)

        if user.role != UserRole.ADMIN.value:
            # Non-admin sees owned project runs and global system runs
            owned_project_ids = [
                p.id
                for p in self.db.query(Project.id).filter(Project.owner_id == user.id).all()
            ]
            if project_id is not None:
                if project_id not in owned_project_ids:
                    return []
                query = query.filter(EvaluationRun.project_id == project_id)
            else:
                query = query.filter(
                    (EvaluationRun.project_id.in_(owned_project_ids))
                    | (EvaluationRun.project_id.is_(None))
                )
        else:
            if project_id is not None:
                query = query.filter(EvaluationRun.project_id == project_id)

        if suite_id:
            query = query.filter(EvaluationRun.suite_id == suite_id)

        runs = (
            query.order_by(EvaluationRun.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [EvaluationRunResponse.model_validate(r) for r in runs]

    def get_run_scoped(
        self,
        run_id: str,
        user: User,
    ) -> Optional[EvaluationRunResponse]:
        """
        Gets a single run with case results, enforcing IDOR ownership checks.
        """
        run = self.db.query(EvaluationRun).filter(EvaluationRun.id == run_id).first()
        if not run:
            return None

        # IDOR check: if project-scoped and user is not admin, verify ownership
        if run.project_id is not None and user.role != UserRole.ADMIN.value:
            project = (
                self.db.query(Project)
                .filter(Project.id == run.project_id, Project.owner_id == user.id)
                .first()
            )
            if not project:
                return None

        response = EvaluationRunResponse.model_validate(run)
        response.case_results = [
            EvaluationCaseResultResponse.model_validate(cr) for cr in run.case_results
        ]
        return response

    def set_baseline_scoped(
        self,
        run_id: str,
        user: User,
    ) -> EvaluationRunResponse:
        """
        Atomically designates a run as the active baseline for its compatibility signature.
        """
        run = self.db.query(EvaluationRun).filter(EvaluationRun.id == run_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Evaluation run not found")

        # Authorization: system baseline requires ADMIN; project baseline requires owner
        if run.project_id is None:
            if user.role != UserRole.ADMIN.value:
                raise HTTPException(status_code=403, detail="System baseline designation requires admin privileges")
        else:
            project = (
                self.db.query(Project)
                .filter(Project.id == run.project_id, Project.owner_id == user.id)
                .first()
            )
            if not project and user.role != UserRole.ADMIN.value:
                raise HTTPException(status_code=404, detail="Project not found")

        # Clear existing active baseline for matching signature
        (
            self.db.query(EvaluationRun)
            .filter(
                EvaluationRun.suite_id == run.suite_id,
                EvaluationRun.dataset_id == run.dataset_id,
                EvaluationRun.dataset_version == run.dataset_version,
                EvaluationRun.execution_mode == run.execution_mode,
                EvaluationRun.project_id == run.project_id,
                EvaluationRun.is_baseline.is_(True),
            )
            .update({"is_baseline": False})
        )

        run.is_baseline = True
        self.db.commit()
        self.db.refresh(run)

        response = EvaluationRunResponse.model_validate(run)
        response.case_results = [
            EvaluationCaseResultResponse.model_validate(cr) for cr in run.case_results
        ]
        return response

    def delete_run_scoped(
        self,
        run_id: str,
        user: User,
    ) -> None:
        """
        Deletes an evaluation run and its cascading case results.
        """
        run = self.db.query(EvaluationRun).filter(EvaluationRun.id == run_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Evaluation run not found")

        if run.project_id is None:
            if user.role != UserRole.ADMIN.value:
                raise HTTPException(status_code=403, detail="System run deletion requires admin privileges")
        else:
            project = (
                self.db.query(Project)
                .filter(Project.id == run.project_id, Project.owner_id == user.id)
                .first()
            )
            if not project and user.role != UserRole.ADMIN.value:
                raise HTTPException(status_code=404, detail="Project not found")

        self.db.delete(run)
        self.db.commit()
