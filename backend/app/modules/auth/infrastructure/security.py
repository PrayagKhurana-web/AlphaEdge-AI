"""Password hashing and JWT token handling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import Settings
from app.modules.auth.domain.exceptions import InvalidAccessTokenError


_password_hash = PasswordHash.recommended()


class PasswordService:
    """Hash and verify user passwords."""

    @staticmethod
    def hash_password(password: str) -> str:
        return _password_hash.hash(password)

    @staticmethod
    def verify_password(
        plain_password: str,
        password_hash: str,
    ) -> bool:
        return _password_hash.verify(
            plain_password,
            password_hash,
        )


class AccessTokenService:
    """Create and validate signed JWT access tokens."""

    def __init__(self, settings: Settings) -> None:
        self._secret_key = settings.auth_secret_key
        self._algorithm = settings.auth_algorithm
        self._expiry_minutes = (
            settings.auth_access_token_expire_minutes
        )

    def create_access_token(self, *, user_id: int) -> str:
        now = datetime.now(UTC)

        payload: dict[str, Any] = {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(minutes=self._expiry_minutes),
            "type": "access",
        }

        return jwt.encode(
            payload,
            self._secret_key,
            algorithm=self._algorithm,
        )

    def decode_user_id(self, token: str) -> int:
        try:
            payload = jwt.decode(
                token,
                self._secret_key,
                algorithms=[self._algorithm],
            )

            if payload.get("type") != "access":
                raise InvalidAccessTokenError(
                    "The token is not an access token."
                )

            subject = payload.get("sub")

            if not isinstance(subject, str):
                raise InvalidAccessTokenError(
                    "The access token subject is invalid."
                )

            user_id = int(subject)

            if user_id <= 0:
                raise ValueError

            return user_id

        except (
            InvalidTokenError,
            TypeError,
            ValueError,
        ) as exc:
            raise InvalidAccessTokenError(
                "The access token is invalid or expired."
            ) from exc
