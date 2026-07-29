"""Application service for registration and authentication."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.auth.domain.entities import User
from app.modules.auth.domain.exceptions import (
    EmailAlreadyRegisteredError,
    InactiveUserError,
    InvalidCredentialsError,
)
from app.modules.auth.infrastructure.repository import (
    SqlAlchemyUserRepository,
)
from app.modules.auth.infrastructure.security import (
    AccessTokenService,
    PasswordService,
)


@dataclass(frozen=True, slots=True)
class AuthenticationResult:
    user: User
    access_token: str


class AuthenticationService:
    """Coordinate registration, login, and token creation."""

    def __init__(
        self,
        *,
        repository: SqlAlchemyUserRepository,
        password_service: PasswordService,
        token_service: AccessTokenService,
    ) -> None:
        self._repository = repository
        self._password_service = password_service
        self._token_service = token_service

    @staticmethod
    def normalize_email(email: str) -> str:
        return email.strip().lower()

    async def register(
        self,
        *,
        email: str,
        password: str,
    ) -> AuthenticationResult:
        normalized_email = self.normalize_email(email)

        existing_user = await self._repository.get_by_email(
            normalized_email
        )

        if existing_user is not None:
            raise EmailAlreadyRegisteredError(
                "An account with this email already exists."
            )

        password_hash = self._password_service.hash_password(
            password
        )

        user = await self._repository.create(
            email=normalized_email,
            password_hash=password_hash,
        )

        return AuthenticationResult(
            user=user,
            access_token=self._token_service.create_access_token(
                user_id=user.id
            ),
        )

    async def login(
        self,
        *,
        email: str,
        password: str,
    ) -> AuthenticationResult:
        normalized_email = self.normalize_email(email)

        user = await self._repository.get_by_email(
            normalized_email
        )

        if user is None:
            raise InvalidCredentialsError(
                "The email or password is incorrect."
            )

        if not self._password_service.verify_password(
            password,
            user.password_hash,
        ):
            raise InvalidCredentialsError(
                "The email or password is incorrect."
            )

        if not user.is_active:
            raise InactiveUserError(
                "This user account is inactive."
            )

        return AuthenticationResult(
            user=user,
            access_token=self._token_service.create_access_token(
                user_id=user.id
            ),
        )
