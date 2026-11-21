import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.documents import get_user_project
from app.auth.dependencies import get_current_user
from app.database.connection import get_db
from app.models.user import User, UserRole
from app.developer.schemas import DeveloperRequest, DeveloperResponse, DeveloperMode
from app.developer.services.developer_service import DeveloperService
from app.developer.errors import ValidationError, TimeoutError, DeveloperBaseException
from app.developer.logging import scrub_secrets
from app.research.exceptions import ResearchPipelineError

logger = logging.getLogger("developer-api")

router = APIRouter(
    prefix="/projects/{project_id}/developer",
    tags=["Developer"],
)


def get_developer_service(db: Session = Depends(get_db)) -> DeveloperService:
    """Dependency provider for DeveloperService."""
    return DeveloperService(db=db)


@router.post(
    "",
    response_model=DeveloperResponse,
    status_code=status.HTTP_200_OK,
)
async def execute_developer_task(
    project_id: int,
    request: DeveloperRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    developer_service: DeveloperService = Depends(get_developer_service),
) -> DeveloperResponse:
    """
    Executes project-scoped developer intelligence tasks.
    Enforces project ownership before any expensive operations (0-cost IDOR protection),
    viewer RBAC constraints on write mutations, and sanitizes all error responses.
    """
    # 1. Enforce strict project ownership (IDOR defense) - 0 external calls if unauthorized
    project = get_user_project(project_id, current_user, db)

    # 2. RBAC check: Viewers cannot apply modifications
    if request.mode == DeveloperMode.APPLY:
        user_role = str(current_user.role).lower()
        if user_role == UserRole.VIEWER.value or user_role == "viewer":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Viewer role is not authorized to apply code modifications.",
            )

    # 3. Execute bounded developer task
    try:
        response = await developer_service.execute_task(
            project_id=project.id,
            request=request,
        )
        return response
    except HTTPException:
        raise
    except TimeoutError as exc:
        logger.error(f"Developer task timed out: {exc}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Developer task timed out.",
        ) from exc
    except ValidationError as exc:
        clean_detail = scrub_secrets(exc.message)
        logger.warning(f"Developer validation error: {clean_detail}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=clean_detail,
        ) from exc
    except (ResearchPipelineError, DeveloperBaseException) as exc:
        clean_detail = scrub_secrets(str(exc))
        logger.error(f"Developer upstream error: {clean_detail}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Developer service encountered an upstream provider error.",
        ) from exc
    except Exception as exc:
        clean_detail = scrub_secrets(str(exc))
        logger.error(f"Unhandled developer task error: {clean_detail}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error during developer task execution.",
        ) from exc
