import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.documents import get_user_project
from app.auth.dependencies import get_current_user
from app.database.connection import get_db
from app.models.user import User
from app.research.exceptions import ResearchPipelineError, VectorStoreError
from app.research.schemas import ResearchRequest, ResearchResponse
from app.research.services.research_service import ResearchService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/projects/{project_id}/research",
    tags=["Research"],
)


def get_research_service(db: Session = Depends(get_db)) -> ResearchService:
    """Dependency provider for ResearchService."""
    return ResearchService(db=db)


@router.post(
    "",
    response_model=ResearchResponse,
    status_code=status.HTTP_200_OK,
)
async def conduct_research(
    project_id: int,
    request: ResearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    research_service: ResearchService = Depends(get_research_service),
) -> ResearchResponse:
    """
    Executes project-scoped grounded research workflow.
    Validates project tenancy to prevent IDOR vulnerabilities (returns 404 on unowned project
    BEFORE executing any LLM, planner, or retrieval calls).
    """
    # 1. Enforce strict project ownership (IDOR defense) - 0 external calls if unauthorized
    project = get_user_project(project_id, current_user, db)

    # 2. Validate non-empty / non-whitespace question
    if not request.question or not request.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Research question cannot be empty or whitespace only",
        )

    # 3. Execute bounded research workflow
    try:
        response = await research_service.research(
            project_id=project.id,
            request=request,
        )
        return response
    except TimeoutError as exc:
        logger.error("Research request timed out for project %s", project.id)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Research request timed out.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except (VectorStoreError, ResearchPipelineError) as exc:
        logger.error("Research pipeline error for project %s: %s", project.id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Research service encountered an error while processing the request.",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error during research for project %s: %s", project.id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error during research processing.",
        ) from exc
