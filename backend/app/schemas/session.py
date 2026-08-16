from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class SessionType(str, Enum):
    research = "research"
    coding = "coding"


class SessionCreate(BaseModel):
    project_id: int
    type: SessionType
    title: str
    query: str


class SessionResponse(BaseModel):
    id: int
    project_id: int
    type: SessionType
    title: str
    query: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )