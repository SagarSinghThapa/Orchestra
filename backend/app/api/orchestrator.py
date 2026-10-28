import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.documents import get_user_project
from app.auth.dependencies import get_current_user
from app.database.connection import get_db
from app.developer.errors import DeveloperBaseException, ValidationError
from app.developer.logging import scrub_secrets
from app.developer.schemas import DeveloperMode
from app.models.session import Session as SessionModel
from app.models.user import User, UserRole
from app.orchestrator.schemas import (
    IntentType,
    OrchestratorRequest,
    OrchestratorResponse,
)
from app.orchestrator.service import OrchestratorService
from app.research.exceptions import ResearchPipelineError

logger = logging.getLogger("orchestrator-api")

router = APIRouter(
    prefix="/projects/{project_id}/orchestrate",
    tags=["Orchestrator"],
)


def get_orchestrator_service(db: Session = Depends(get_db)) -> OrchestratorService:
    """Dependency provider for OrchestratorService."""
    return OrchestratorService(db=db)


def _validate_rbac_and_session(
    project_id: int,
    request: OrchestratorRequest,
    current_user: User,
    db: Session,
    path_session_id: Optional[int] = None,
) -> int:
    """
    Validates:
      1. RBAC constraints (viewer role forbidden from apply mode developer tasks).
      2. Session existence and project boundary binding.
    """
    effective_session_id = path_session_id if path_session_id is not None else request.session_id

    # 1. RBAC check: Viewers cannot apply code changes
    if request.developer_params:
        mode_val = request.developer_params.get("mode")
        if mode_val in (DeveloperMode.APPLY, DeveloperMode.APPLY.value, "apply"):
            user_role = str(current_user.role).lower()
            if user_role == UserRole.VIEWER.value or user_role == "viewer":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Viewer role is not authorized to apply code modifications.",
                )

    # 2. Session cross-check if session_id is present
    if effective_session_id is not None:
        db_sess = (
            db.query(SessionModel)
            .filter(SessionModel.id == effective_session_id, SessionModel.project_id == project_id)
            .first()
        )
        if not db_sess:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {effective_session_id} not found in project {project_id}.",
            )

    return effective_session_id


@router.post(
    "",
    response_model=OrchestratorResponse,
    status_code=status.HTTP_200_OK,
)
async def orchestrate_new_or_existing(
    project_id: int,
    request: OrchestratorRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    orchestrator_service: OrchestratorService = Depends(get_orchestrator_service),
) -> OrchestratorResponse:
    """
    Initiates or continues an orchestration session.
    Enforces project ownership before any expensive operations (0-cost IDOR protection),
    viewer RBAC constraints on write mutations, and sanitizes all error responses.
    """
    # 1. Enforce project ownership (0 external calls if unauthorized)
    project = get_user_project(project_id, current_user, db)

    # 2. RBAC and session validation
    effective_session_id = _validate_rbac_and_session(
        project_id=project.id,
        request=request,
        current_user=current_user,
        db=db,
    )

    if effective_session_id != request.session_id:
        request = request.model_copy(update={"session_id": effective_session_id})

    # 3. Execute orchestration
    try:
        response = await orchestrator_service.orchestrate(
            project_id=project.id,
            request=request,
            current_user_id=current_user.id,
        )
        return response
    except HTTPException:
        raise
    except TimeoutError as exc:
        logger.error("Orchestration timed out: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Orchestration request timed out.",
        ) from exc
    except ValidationError as exc:
        clean_detail = scrub_secrets(exc.message)
        logger.warning("Orchestration validation error: %s", clean_detail)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=clean_detail,
        ) from exc
    except (ResearchPipelineError, DeveloperBaseException) as exc:
        clean_detail = scrub_secrets(str(exc))
        logger.error("Orchestration upstream error: %s", clean_detail)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Orchestrator encountered an upstream subsystem error.",
        ) from exc
    except Exception as exc:
        clean_detail = scrub_secrets(str(exc))
        logger.error("Unhandled orchestration error: %s", clean_detail)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error during orchestration execution.",
        ) from exc


@router.post(
    "/sessions/{session_id}",
    response_model=OrchestratorResponse,
    status_code=status.HTTP_200_OK,
)
async def orchestrate_session(
    project_id: int,
    session_id: int,
    request: OrchestratorRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    orchestrator_service: OrchestratorService = Depends(get_orchestrator_service),
) -> OrchestratorResponse:
    """
    Continues a specific session within a project.
    """
    # 1. Enforce project ownership
    project = get_user_project(project_id, current_user, db)

    # 2. RBAC and session validation
    _validate_rbac_and_session(
        project_id=project.id,
        request=request,
        current_user=current_user,
        db=db,
        path_session_id=session_id,
    )

    request_with_session = request.model_copy(update={"session_id": session_id})

    # 3. Execute orchestration
    try:
        response = await orchestrator_service.orchestrate(
            project_id=project.id,
            request=request_with_session,
            current_user_id=current_user.id,
        )
        return response
    except HTTPException:
        raise
    except TimeoutError as exc:
        logger.error("Orchestration timed out: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Orchestration request timed out.",
        ) from exc
    except ValidationError as exc:
        clean_detail = scrub_secrets(exc.message)
        logger.warning("Orchestration validation error: %s", clean_detail)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=clean_detail,
        ) from exc
    except (ResearchPipelineError, DeveloperBaseException) as exc:
        clean_detail = scrub_secrets(str(exc))
        logger.error("Orchestration upstream error: %s", clean_detail)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Orchestrator encountered an upstream subsystem error.",
        ) from exc
    except Exception as exc:
        clean_detail = scrub_secrets(str(exc))
        logger.error("Unhandled orchestration error: %s", clean_detail)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error during orchestration execution.",
        ) from exc
