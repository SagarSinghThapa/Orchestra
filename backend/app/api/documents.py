import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.config import settings
from app.database.connection import get_db
from app.models.document import Document, DocumentStatus
from app.models.project import Project
from app.models.user import User
from app.research.services.ingestion_service import IngestionService
from app.research.storage.local import LocalStorageBackend
from app.schemas.document import DocumentDetailResponse, DocumentResponse

router = APIRouter(
    prefix="/projects/{project_id}/documents",
    tags=["Documents"],
)


def get_user_project(project_id: int, current_user: User, db: Session) -> Project:
    """Validates project ownership to prevent IDOR vulnerabilities."""
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.owner_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return project


def get_project_document(project_id: int, document_id: int, db: Session) -> Document:
    """Validates document tenancy under the specific project."""
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.project_id == project_id)
        .first()
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return doc


def get_ingestion_service(db: Session = Depends(get_db)) -> IngestionService:
    """Dependency provider for IngestionService."""
    return IngestionService(db=db)


@router.post(
    "",
    response_model=DocumentDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
):
    project = get_user_project(project_id, current_user, db)

    filename = file.filename or "upload.txt"
    ext = Path(filename).suffix.lower()

    if ext not in settings.allowed_upload_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension '{ext}'. Allowed extensions: {list(settings.allowed_upload_extensions)}",
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum upload size of {settings.max_upload_size_bytes} bytes",
        )

    # File Signature Validation
    if ext == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid PDF file signature; expected %PDF- header",
            )
    elif ext in (".txt", ".md"):
        if b"\0" in content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Binary content not allowed in text document",
            )
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                content.decode("latin-1")
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid text encoding; must be valid UTF-8 or Latin-1",
                )

    checksum = hashlib.sha256(content).hexdigest()

    # Duplicate pre-check within same project
    existing_doc = (
        db.query(Document)
        .filter(
            Document.project_id == project.id,
            Document.checksum == checksum,
            Document.status != DocumentStatus.FAILED.value,
        )
        .first()
    )
    if existing_doc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A document with identical content already exists in this project",
        )

    storage_key = f"projects/{project.id}/{uuid4().hex}{ext}"
    storage = ingestion_service.storage
    storage.save(content, storage_key)

    # Storage compensation protocol
    try:
        doc = Document(
            project_id=project.id,
            original_filename=filename,
            storage_key=storage_key,
            content_type=file.content_type or "application/octet-stream",
            size_bytes=len(content),
            checksum=checksum,
            status=DocumentStatus.UPLOADED.value,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
    except IntegrityError:
        db.rollback()
        storage.delete(storage_key)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A document with identical content already exists in this project",
        )
    except Exception:
        db.rollback()
        storage.delete(storage_key)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document creation failed",
        )

    # Bounded synchronous ingestion execution
    processed_doc = await ingestion_service.process_document(doc.id)
    return processed_doc


@router.get(
    "",
    response_model=list[DocumentResponse],
)
def list_documents(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_user_project(project_id, current_user, db)
    return (
        db.query(Document)
        .filter(Document.project_id == project.id)
        .order_by(Document.created_at.desc())
        .all()
    )


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
)
def get_document(
    project_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_user_project(project_id, current_user, db)
    doc = get_project_document(project_id, document_id, db)
    return doc


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document(
    project_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
):
    get_user_project(project_id, current_user, db)
    get_project_document(project_id, document_id, db)
    await ingestion_service.delete_document(project_id, document_id)
    return None


@router.post(
    "/{document_id}/reindex",
    response_model=DocumentDetailResponse,
)
async def reindex_document(
    project_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
):
    get_user_project(project_id, current_user, db)
    get_project_document(project_id, document_id, db)
    reindexed_doc = await ingestion_service.reindex_document(project_id, document_id)
    return reindexed_doc
