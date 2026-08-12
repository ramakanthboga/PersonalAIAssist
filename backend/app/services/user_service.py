"""User service – registration, authentication, Google OAuth link-or-create."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, NotFoundError, ValidationError
from app.core.security import hash_password, verify_password
from app.database.models import User
from app.database.repositories.user_repo import UserRepository
from app.security.email_validation import normalize_email, validate_registration_email


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self._repo = UserRepository(db)

    def _ensure_registration_allowed(self, email: str) -> None:
        settings = get_settings()
        if not settings.is_registration_allowed_for(email):
            if not settings.ALLOW_REGISTRATION:
                raise ValidationError("Registration is disabled")
            raise ValidationError("This email is not allowed to register")

    async def register(
        self,
        email: str,
        password: str,
        full_name: str | None = None,
    ) -> User:
        normalized = validate_registration_email(email)
        self._ensure_registration_allowed(normalized)
        existing = await self._repo.get_by_email(normalized)
        if existing is not None:
            raise ValidationError(f"Email '{normalized}' is already registered")

        hashed = hash_password(password)
        return await self._repo.create(
            email=normalized,
            hashed_password=hashed,
            full_name=full_name,
        )

    async def authenticate(self, email: str, password: str) -> User:
        normalized = normalize_email(email)
        user = await self._repo.get_by_email(normalized)
        if user is None:
            raise AuthenticationError("Invalid email or password")
        if user.hashed_password is None:
            provider = (user.oauth_provider or "Google").title()
            raise AuthenticationError(
                f"This account uses {provider} sign-in. Use Continue with Google."
            )
        if not verify_password(password, user.hashed_password):
            raise AuthenticationError("Invalid email or password")
        if not user.is_active:
            raise AuthenticationError("Account is deactivated")
        return user

    async def login_or_register_google(
        self,
        *,
        email: str,
        email_verified: bool,
        full_name: str | None,
        oauth_sub: str,
    ) -> User:
        """Create or link a user from a verified Google profile."""
        if not email_verified:
            raise ValidationError("Google email is not verified")
        if not oauth_sub:
            raise ValidationError("Missing Google account id")

        normalized = normalize_email(email)
        if not normalized or "@" not in normalized:
            raise ValidationError("Google did not return a valid email")

        by_sub = await self._repo.get_by_oauth_sub("google", oauth_sub)
        if by_sub is not None:
            if not by_sub.is_active:
                raise AuthenticationError("Account is deactivated")
            updates: dict[str, object] = {}
            if by_sub.email != normalized:
                updates["email"] = normalized
            if full_name and not by_sub.full_name:
                updates["full_name"] = full_name
            if updates:
                return await self._repo.update(by_sub, **updates)
            return by_sub

        existing = await self._repo.get_by_email(normalized)
        if existing is not None:
            if not existing.is_active:
                raise AuthenticationError("Account is deactivated")
            # Never auto-link Google to an existing password/other account.
            # Auto-link enabled account takeover: register victim email → victim
            # later signs in with Google and lands on the attacker's account.
            raise ValidationError(
                "An account with this email already exists. "
                "Sign in with your password instead of Google."
            )

        self._ensure_registration_allowed(normalized)
        return await self._repo.create(
            email=normalized,
            hashed_password=None,
            full_name=full_name,
            oauth_provider="google",
            oauth_sub=oauth_sub,
        )

    async def get_user(self, user_id: int) -> User:
        user = await self._repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User")
        return user
