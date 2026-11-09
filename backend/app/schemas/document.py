from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    id: int
    project_id: int
    original_filename: str
    content_type: str
    size_bytes: int
    status: str
    chunk_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


class DocumentDetailResponse(DocumentResponse):
    error_message: str | None = None
