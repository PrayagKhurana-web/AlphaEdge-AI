"""Application service for email verification."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.modules.auth.domain.entities import User
from app.modules.auth.domain.exceptions import (
    EmailAlreadyVerifiedError,
    InvalidEmailVerificationTokenError,
)
from app.modules.auth.infrastructure.email_delivery import (
    ConsoleEmailVerificationSender,
)
from app.modules.auth.infrastructure.repository import (
    SqlAlchemyEmailVerificationRepository,
    SqlAlchemyUserRepository,
)
from app.modules.auth.infrastructure.security import (
    EmailVerificationTokenService,
)


@dataclass(frozen=True, slots=True)
class VerificationRequestResult:
    message: str


class EmailVerificationService:
    """Issue and consume secure email-verification tokens."""

    def __init__(
        self,
        *,
        user_repository: SqlAlchemyUserRepository,
        verification_repository:
            SqlAlchemyEmailVerificationRepository,
        token_service: EmailVerificationTokenService,
        sender: ConsoleEmailVerificationSender,
    ) -> None:
        self._user_repository = user_repository
        self._verification_repository = (
            verification_repository
        )
        self._token_service = token_service
        self._sender = sender

    async def issue_for_user(
        self,
        user: User,
    ) -> VerificationRequestResult:
        if user.is_email_verified:
            raise EmailAlreadyVerifiedError(
                "This email address is already verified."
            )

        now = datetime.now(UTC)
        raw_token = self._token_service.generate_raw_token()
        token_hash = self._token_service.hash_token(raw_token)
        expires_at = self._token_service.calculate_expiry(
            issued_at=now
        )

        await self._verification_repository.invalidate_active_tokens(
            user_id=user.id,
            used_at=now,
        )

        await self._verification_repository.create(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )

        await self._sender.send(
            email=user.email,
            raw_token=raw_token,
        )

        return VerificationRequestResult(
            message=(
                "A verification link has been sent if the "
                "account is eligible for verification."
            )
        )

    async def verify(self, *, raw_token: str) -> User:
        token_hash = self._token_service.hash_token(
            raw_token.strip()
        )

        token = (
            await self._verification_repository
            .get_active_by_hash(token_hash)
        )

        if token is None:
            raise InvalidEmailVerificationTokenError(
                "The verification link is invalid or has already been used."
            )

        now = datetime.now(UTC)

        expires_at = token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if expires_at <= now:
            await self._verification_repository.mark_used(
                token_id=token.id,
                used_at=now,
            )
            raise InvalidEmailVerificationTokenError(
                "The verification link has expired."
            )

        user = await self._user_repository.get_by_id(
            token.user_id
        )

        if user is None or not user.is_active:
            raise InvalidEmailVerificationTokenError(
                "The verification link is invalid."
            )

        if user.is_email_verified:
            await self._verification_repository.mark_used(
                token_id=token.id,
                used_at=now,
            )
            return user

        try:
            verified_user = (
                await self._user_repository.mark_email_verified(
                    user_id=user.id,
                    verified_at=now,
                    commit=False,
                )
            )

            if verified_user is None:
                raise InvalidEmailVerificationTokenError(
                    "The verification link is invalid."
                )

            await self._verification_repository.mark_used(
                token_id=token.id,
                used_at=now,
                commit=False,
            )

            await self._verification_repository.commit()

        except Exception:
            await self._verification_repository.rollback()
            raise

        refreshed_user = await self._user_repository.get_by_id(
            user.id
        )

        if refreshed_user is None:
            raise InvalidEmailVerificationTokenError(
                "The verified user is unavailable."
            )

        return refreshed_user
