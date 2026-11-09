from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.jwt import create_access_token, create_refresh_token, decode_token
from app.auth.password import hash_password, verify_password
from app.core.config import settings
from app.database.connection import get_db
from app.models.user import User, UserRole
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    UserResponse,
)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
) -> User:
    """
    Register a new user account with default 'member' role.
    
    Public endpoint. Enforces unique email, hashes password with direct native bcrypt,
    and returns safe user representation without exposing password hashes.
    """
    existing_user = (
        db.query(User)
        .filter(User.email == request.email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=request.email,
        password_hash=hash_password(request.password),
        role=UserRole.MEMBER.value,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Authenticate user credentials and issue dual cryptographic tokens (access and refresh).
    
    Supports form-data (OAuth2) and JSON bodies. Returns tokens in JSON response for API clients
    and sets explicit HttpOnly cookies for browser sessions.
    """
    username: Optional[str] = None
    password: Optional[str] = None

    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            data = await request.json()
            username = data.get("email") or data.get("username")
            password = data.get("password")
        except Exception:
            pass
    else:
        try:
            form = await request.form()
            username = form.get("username") or form.get("email")
            password = form.get("password")
        except Exception:
            pass

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    user = (
        db.query(User)
        .filter(User.email == username)
        .first()
    )

    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token = create_access_token(user.id, role=user.role)
    refresh_token = create_refresh_token(user.id)

    # Set explicit HttpOnly cookies
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
        max_age=settings.access_token_expire_minutes * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
        max_age=settings.refresh_token_expire_days * 86400,
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/refresh")
async def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Issue a new access token given a valid, unexpired refresh token.
    
    Accepts refresh token via HttpOnly cookie or JSON payload. Rejects access tokens
    with 401 Unauthorized.
    """
    raw_refresh_token: Optional[str] = request.cookies.get("refresh_token")

    if not raw_refresh_token:
        # Check JSON payload
        try:
            data = await request.json()
            raw_refresh_token = data.get("refresh_token")
        except Exception:
            pass

    if not raw_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required",
        )

    try:
        payload = decode_token(raw_refresh_token, expected_type="refresh")
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )
        user_id_int = int(user_id)
    except (JWTError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user = db.query(User).filter(User.id == user_id_int).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    new_access_token = create_access_token(user.id, role=user.role)

    response.set_cookie(
        key="access_token",
        value=new_access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
        max_age=settings.access_token_expire_minutes * 60,
    )

    return {
        "access_token": new_access_token,
        "token_type": "bearer",
    }


@router.post("/logout")
def logout(response: Response):
    """
    Browser session logout: clears authentication cookies.
    
    Note: Stateless JWT tokens remain cryptographically valid until expiration;
    server-side token revocation / blocklists are deferred to Redis session integration.
    """
    response.delete_cookie(
        key="access_token",
        path="/",
    )
    response.delete_cookie(
        key="refresh_token",
        path="/",
    )
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Retrieve authenticated user profile.
    """
    return current_user