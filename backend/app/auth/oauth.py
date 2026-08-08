"""Google OAuth client registration (Authlib)."""

from __future__ import annotations

from authlib.integrations.starlette_client import OAuth

from app.core.config import get_settings

oauth = OAuth()
_google_registered = False


def configure_oauth() -> None:
    """Register Google provider when client credentials are configured."""
    global _google_registered
    settings = get_settings()
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        return
    if _google_registered:
        return
    oauth.register(
        name="google",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
    _google_registered = True


def google_oauth_configured() -> bool:
    settings = get_settings()
    return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)


def google_callback_uri() -> str:
    settings = get_settings()
    base = settings.OAUTH_REDIRECT_BASE_URL.rstrip("/")
    prefix = settings.API_V1_PREFIX.rstrip("/")
    return f"{base}{prefix}/auth/google/callback"
