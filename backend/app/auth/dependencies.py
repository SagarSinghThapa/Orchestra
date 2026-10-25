from typing import Callable, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.auth.jwt import decode_token
from app.database.connection import get_db
from app.models.user import User


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login",
    auto_error=False,
)


def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Authenticate the current user with deterministic credential extraction.
    
    Precedence rules:
    1. If the 'Authorization' header is present, it is evaluated strictly.
       If missing/invalid/expired/wrong-type, immediately raise 401 Unauthorized.
       DO NOT fall back to cookies when an Authorization header is supplied.
    2. Fallback to 'access_token' cookie occurs ONLY when the Authorization header is completely absent.
    """
    auth_header = request.headers.get("Authorization")
    raw_token: Optional[str] = None

    if auth_header:
        # Strict Header Evaluation: header was provided
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        raw_token = parts[1]
    else:
        # Fallback to HttpOnly cookie ONLY when Authorization header is absent
        cookie_token = request.cookies.get("access_token")
        if cookie_token:
            raw_token = cookie_token
        elif token:
            raw_token = token

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(raw_token, expected_type="access")
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id_int).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_role(*allowed_roles: str) -> Callable[[User], User]:
    """
    Dependency factory to enforce Role-Based Access Control (RBAC).
    
    Returns 401 Unauthorized for unauthenticated requests.
    Returns 403 Forbidden with 'Insufficient permissions' for authenticated users lacking an allowed role.
    
    Note: RBAC enforces category-level permissions and does NOT replace or weaken
    Phase 02 resource ownership isolation (e.g. project.owner_id == user.id).
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return role_checker