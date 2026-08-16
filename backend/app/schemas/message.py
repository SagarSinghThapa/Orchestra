from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class MessageRole(str, Enum):
    user = "user"
    assistant = "assistant"
    tool = "tool"
    system = "system"


class MessageCreate(BaseModel):
    role: MessageRole
    content: str


class MessageResponse(BaseModel):
    id: int
    session_id: int
    role: MessageRole
    content: str
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )