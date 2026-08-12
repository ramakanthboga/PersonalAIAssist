"""Auth routes – registration, login, Google OAuth, token refresh, current user."""

from __future__ import annotations

from urllib.parse import quote, urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from jose import JWTError
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.auth.oauth import (
    configure_oauth,
    google_callback_uri,
    google_oauth_configured,
    oauth,
)
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.database.models import User
from app.database.session import get_db
from app.security.rate_limiter import check_auth_rate_limit
from app.services.user_service import UserService

logger = get_logger(__name__)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


router = APIRouter(prefix="/auth")


def _oauth_error_redirect(message: str) -> RedirectResponse:
    settings = get_settings()
    base = settings.FRONTEND_OAUTH_SUCCESS_URL.split("#", 1)[0]
    url = f"{base}?error={quote(message)}"
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


def _oauth_success_redirect(access_token: str, refresh_token: str) -> RedirectResponse:
    """Send JWTs to the frontend via URL hash (not sent to the server on next request)."""
    settings = get_settings()
    base = settings.FRONTEND_OAUTH_SUCCESS_URL.split("#", 1)[0]
    fragment = urlencode(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }
    )
    return RedirectResponse(url=f"{base}#{fragment}", status_code=status.HTTP_302_FOUND)


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(check_auth_rate_limit)],
)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    try:
        svc = UserService(db)
        user = await svc.register(
            email=body.email,
            password=body.password,
            full_name=body.full_name,
        )
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(check_auth_rate_limit)])
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    try:
        svc = UserService(db)
        user = await svc.authenticate(email=body.email, password=body.password)
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.get("/google/login", dependencies=[Depends(check_auth_rate_limit)])
async def google_login(request: Request):
    """Start Google OAuth — redirects the browser to Google consent."""
    if not google_oauth_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google sign-in is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
        )
    configure_oauth()
    redirect_uri = google_callback_uri()
    # Always show Google account picker so users can switch Gmail accounts
    # instead of silently reusing the browser's existing Google session.
    return await oauth.google.authorize_redirect(
        request,
        redirect_uri,
        prompt="select_account",
    )


@router.get("/google/callback", dependencies=[Depends(check_auth_rate_limit)])
async def google_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """Google redirects here; issue app JWTs and send the user to the frontend."""
    if not google_oauth_configured():
        return _oauth_error_redirect("Google sign-in is not configured")

    configure_oauth()
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception:
        logger.exception("google_oauth_token_exchange_failed")
        return _oauth_error_redirect("Google sign-in failed. Please try again.")

    userinfo = token.get("userinfo")
    if not userinfo:
        try:
            userinfo = await oauth.google.userinfo(token=token)
        except Exception:
            logger.exception("google_oauth_userinfo_failed")
            return _oauth_error_redirect("Could not read your Google profile")

    email = userinfo.get("email")
    email_verified = bool(userinfo.get("email_verified"))
    oauth_sub = str(userinfo.get("sub") or "")
    full_name = userinfo.get("name") or userinfo.get("given_name")

    if not email:
        return _oauth_error_redirect("Google did not provide an email address")

    try:
        svc = UserService(db)
        user = await svc.login_or_register_google(
            email=email,
            email_verified=email_verified,
            full_name=full_name,
            oauth_sub=oauth_sub,
        )
        await db.commit()
    except AppError as exc:
        return _oauth_error_redirect(exc.message)
    except Exception:
        logger.exception("google_oauth_user_persist_failed")
        return _oauth_error_redirect("Could not complete sign-in")

    return _oauth_success_redirect(
        create_access_token(user.id),
        create_refresh_token(user.id),
    )


@router.get("/providers")
async def list_auth_providers():
    """Frontend can hide Google / Register when not available."""
    settings = get_settings()
    return {
        "google": google_oauth_configured(),
        "registration_enabled": settings.ALLOW_REGISTRATION,
        "registration_allowlist_active": bool(settings.REGISTRATION_ALLOWED_EMAILS),
    }


@router.post("/refresh", response_model=TokenResponse, dependencies=[Depends(check_auth_rate_limit)])
async def refresh_token(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is not a refresh token",
        )

    try:
        user_id = int(payload["sub"])
        svc = UserService(db)
        user = await svc.get_user(user_id)
    except (KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at.isoformat(),
    }
