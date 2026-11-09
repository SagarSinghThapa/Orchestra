from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_role
from app.database.connection import get_db
from app.evaluations.registry import EvaluationRegistry
from app.evaluations.schemas import (
    BenchmarkSuiteInfo,
    EvaluationRunCreate,
    EvaluationRunResponse,
)
from app.evaluations.service import EvaluationService
from app.models.user import User, UserRole

router = APIRouter(
    prefix="/evaluations",
    tags=["Evaluations"],
)


@router.get("/benchmarks", response_model=List[BenchmarkSuiteInfo])
def get_benchmarks(
    current_user: User = Depends(get_current_user),
) -> List[BenchmarkSuiteInfo]:
    """
    Returns metadata for all statically registered evaluation benchmark suites.
    """
    return EvaluationRegistry.list_suites()


@router.get("/runs", response_model=List[EvaluationRunResponse])
def list_runs(
    project_id: Optional[int] = Query(default=None, description="Filter by project ID"),
    suite_id: Optional[str] = Query(default=None, description="Filter by suite ID"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[EvaluationRunResponse]:
    """
    Lists historical evaluation runs scoped to the user's authorized projects and system benchmarks.
    """
    service = EvaluationService(db)
    return service.list_runs_scoped(
        user=current_user,
        project_id=project_id,
        suite_id=suite_id,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/runs",
    response_model=EvaluationRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_run(
    payload: EvaluationRunCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN.value, UserRole.MEMBER.value)),
) -> EvaluationRunResponse:
    """
    Launches a synchronous benchmark run.
    Enforces ownership-before-cost on project-scoped runs and admin-only execution on system runs.
    Viewer role is blocked with HTTP 403 Forbidden.
    """
    service = EvaluationService(db)
    return await service.execute_run(payload, user=current_user)


@router.get("/runs/{run_id}", response_model=EvaluationRunResponse)
def get_run(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EvaluationRunResponse:
    """
    Fetches detailed evaluation run summary, aggregate metrics, and case results.
    Enforces strict IDOR protection: foreign project runs return 404.
    """
    service = EvaluationService(db)
    run = service.get_run_scoped(run_id=run_id, user=current_user)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation run '{run_id}' not found",
        )
    return run


@router.post(
    "/runs/{run_id}/baseline",
    response_model=EvaluationRunResponse,
    status_code=status.HTTP_200_OK,
)
def set_baseline(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN.value, UserRole.MEMBER.value)),
) -> EvaluationRunResponse:
    """
    Atomically designates a run as the active baseline for its compatibility signature.
    System baseline requires Admin; project baseline requires project owner.
    """
    service = EvaluationService(db)
    return service.set_baseline_scoped(run_id=run_id, user=current_user)


@router.delete(
    "/runs/{run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_run(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN.value, UserRole.MEMBER.value)),
) -> None:
    """
    Deletes an evaluation run and its cascading case results.
    """
    service = EvaluationService(db)
    service.delete_run_scoped(run_id=run_id, user=current_user)
