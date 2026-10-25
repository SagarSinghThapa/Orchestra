from datetime import datetime, timedelta, timezone
from typing import Optional, Union

from jose import JWTError, jwt

from app.core.config import settings


ALGORITHM = "HS256"


def create_access_token(
    user_id_or_data: Union[int, str, dict],
    role: Optional[str] = None,
    expires_minutes: Optional[int] = None,
) -> str:
    """
    Generate a signed JWT access token containing subject, optional role, and explicit type='access'.
    """
    if not settings.jwt_secret:
        settings.validate_runtime_requirements()

    if isinstance(user_id_or_data, dict):
        payload = user_id_or_data.copy()
        if role and "role" not in payload:
            payload["role"] = role
        payload.setdefault("type", "access")
    else:
        payload = {
            "sub": str(user_id_or_data),
            "type": "access",
        }
        if role:
            payload["role"] = role

    mins = expires_minutes if expires_minutes is not None else settings.access_token_expire_minutes
    expire = datetime.now(timezone.utc) + timedelta(minutes=mins)
    payload["exp"] = expire

    return jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=ALGORITHM,
    )


def create_refresh_token(
    user_id_or_data: Union[int, str, dict],
    expires_days: Optional[int] = None,
) -> str:
    """
    Generate a signed JWT refresh token containing subject identity and explicit type='refresh'.
    """
    if not settings.jwt_secret:
        settings.validate_runtime_requirements()

    if isinstance(user_id_or_data, dict):
        sub = str(user_id_or_data.get("sub", ""))
    else:
        sub = str(user_id_or_data)

    payload = {
        "sub": sub,
        "type": "refresh",
    }

    days = expires_days if expires_days is not None else settings.refresh_token_expire_days
    expire = datetime.now(timezone.utc) + timedelta(days=days)
    payload["exp"] = expire

    return jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=ALGORITHM,
    )


def decode_token(token: str, expected_type: str = "access") -> dict:
    """
    Decode and validate a signed JWT token, enforcing cryptographic integrity and matching expected token type.
    """
    if not settings.jwt_secret:
        settings.validate_runtime_requirements()

    payload = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[ALGORITHM],
    )

    token_type = payload.get("type")
    if token_type != expected_type:
        raise JWTError(f"Invalid token type: expected '{expected_type}', got '{token_type}'")

    return payload


def decode_access_token(token: str) -> dict:
    """Decode an access token, maintaining backward compatibility."""
    return decode_token(token, expected_type="access")