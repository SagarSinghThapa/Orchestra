import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from jose import JWTError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.jwt import create_access_token, create_refresh_token, decode_token
from app.auth.password import hash_password, verify_password
from app.core.config import settings
from app.core.csrf import generate_session_csrf_token
from app.core.token_blocklist import is_token_revoked, revoke_token, TokenRevocationError
from app.database.connection import get_db
from app.models.user import User, UserRole
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    UserResponse,
)

logger = logging.getLogger("orchestra.auth")

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
    clean_email = request.email.strip().lower()
    existing_user = (
        db.query(User)
        .filter(func.lower(User.email) == clean_email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=clean_email,
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

    username_raw = username.strip()
    username_lower = username_raw.lower()

    # Tier 1: Exact match first (preserves legacy account affinity)
    user = (
        db.query(User)
        .filter(User.email == username_raw)
        .first()
    )

    # Tier 2: Safe case-insensitive fallback ONLY if no exact match found
    if not user:
        candidates = (
            db.query(User)
            .filter(func.lower(User.email) == username_lower)
            .all()
        )
        if len(candidates) == 1:
            user = candidates[0]
        elif len(candidates) > 1:
            # COLLISION DETECTED: FAIL CLOSED!
            # Never automatically select any account (including the oldest).
            # Never merge or mutate existing accounts automatically.
            # Log internal structured security alert with candidate IDs for manual operator resolution:
            logger.warning(
                "SECURITY ALERT: Case-insensitive email collision detected during login for '%s' "
                "(candidate IDs: %s). Failing closed to prevent account hijacking or data bleed.",
                username_lower,
                [c.id for c in candidates],
            )
            # Require manual collision resolution. Zero information disclosure in public error.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token = create_access_token(user.id, role=user.role)
    refresh_token = create_refresh_token(user.id)
    csrf_token = generate_session_csrf_token(user.id)

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
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
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

    token_id = payload.get("jti") or raw_refresh_token
    try:
        if await is_token_revoked(token_id):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked",
            )
    except TokenRevocationError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable",
        )

    new_access_token = create_access_token(user.id, role=user.role)
    csrf_token = generate_session_csrf_token(user.id)

    response.set_cookie(
        key="access_token",
        value=new_access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
        max_age=settings.access_token_expire_minutes * 60,
    )
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
        max_age=settings.refresh_token_expire_days * 86400,
    )

    return {
        "access_token": new_access_token,
        "token_type": "bearer",
    }


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
):
    """
    Browser session logout: clears authentication cookies and revokes tokens server-side.
    """
    auth_header = request.headers.get("authorization", "")
    token_to_revoke = None
    if auth_header.strip().lower().startswith("bearer "):
        parts = auth_header.split()
        if len(parts) == 2:
            token_to_revoke = parts[1]

    access_cookie = request.cookies.get("access_token")
    refresh_cookie = request.cookies.get("refresh_token")

    tokens_to_revoke = [t for t in (token_to_revoke, access_cookie, refresh_cookie) if t]
    for t in tokens_to_revoke:
        try:
            await revoke_token(t)
        except TokenRevocationError:
            if settings.environment.lower() == "production":
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication service unavailable",
                )

    response.delete_cookie(
        key="access_token",
        path="/",
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        httponly=True,
    )
    response.delete_cookie(
        key="refresh_token",
        path="/",
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        httponly=True,
    )
    response.delete_cookie(
        key="csrf_token",
        path="/",
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        httponly=False,
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