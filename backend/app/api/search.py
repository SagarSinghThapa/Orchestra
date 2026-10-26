from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.documents import get_user_project
from app.auth.dependencies import get_current_user
from app.database.connection import get_db
from app.models.user import User
from app.research.exceptions import ResearchPipelineError, VectorStoreError
from app.research.retrieval.schemas import RetrievalResponse, SearchQuery
from app.research.services.retrieval_service import RetrievalService

router = APIRouter(
    prefix="/projects/{project_id}/search",
    tags=["Search"],
)


def get_retrieval_service(db: Session = Depends(get_db)) -> RetrievalService:
    """Dependency provider for RetrievalService."""
    return RetrievalService(db=db)


@router.post(
    "",
    response_model=RetrievalResponse,
    status_code=status.HTTP_200_OK,
)
async def search_project(
    project_id: int,
    search_query: SearchQuery,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
) -> RetrievalResponse:
    """
    Executes project-scoped hybrid search and returns citation-ready evidence.
    Validates project tenancy to prevent IDOR vulnerabilities (returns 404 on unowned project).
    """
    # 1. Enforce strict project ownership (IDOR defense)
    project = get_user_project(project_id, current_user, db)

    # 2. Validate non-empty / non-whitespace query
    if not search_query.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query cannot be empty or whitespace only",
        )

    # 3. Execute bounded retrieval
    try:
        response = await retrieval_service.search(
            project_id=project.id,
            query_input=search_query,
        )
        return response
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except (VectorStoreError, ResearchPipelineError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Retrieval engine error: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error during retrieval processing.",
        ) from exc
