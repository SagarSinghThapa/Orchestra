from typing import Any
from pydantic import BaseModel, EmailStr, field_validator

from app.models.user import UserRole


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email_input(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip().lower()
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email_input(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip().lower()
        return v


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    role: UserRole = UserRole.MEMBER

    model_config = {
        "from_attributes": True
    }
