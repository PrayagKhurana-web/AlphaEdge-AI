"""FastAPI dependencies for authentication."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database.session import get_db_session
from app.modules.auth.application.email_verification import (
    EmailVerificationService,
)
from app.modules.auth.application.service import (
    AuthenticationService,
)
from app.modules.auth.domain.entities import User
from app.modules.auth.domain.exceptions import (
    InvalidAccessTokenError,
)
from app.modules.auth.infrastructure.email_delivery import (
    ConsoleEmailVerificationSender,
)
from app.modules.auth.infrastructure.repository import (
    SqlAlchemyEmailVerificationRepository,
    SqlAlchemyUserRepository,
)
from app.modules.auth.infrastructure.security import (
    AccessTokenService,
    EmailVerificationTokenService,
    PasswordService,
)


DatabaseSessionDependency = Annotated[
    AsyncSession,
    Depends(get_db_session),
]

_bearer_scheme = HTTPBearer(auto_error=False)


def get_authentication_service(
    session: DatabaseSessionDependency,
) -> AuthenticationService:
    return AuthenticationService(
        repository=SqlAlchemyUserRepository(session),
        password_service=PasswordService(),
        token_service=AccessTokenService(get_settings()),
    )


AuthenticationServiceDependency = Annotated[
    AuthenticationService,
    Depends(get_authentication_service),
]


def get_email_verification_service(
    session: DatabaseSessionDependency,
) -> EmailVerificationService:
    settings = get_settings()

    return EmailVerificationService(
        user_repository=SqlAlchemyUserRepository(session),
        verification_repository=(
            SqlAlchemyEmailVerificationRepository(session)
        ),
        token_service=EmailVerificationTokenService(settings),
        sender=ConsoleEmailVerificationSender(settings),
    )


EmailVerificationServiceDependency = Annotated[
    EmailVerificationService,
    Depends(get_email_verification_service),
]


async def get_current_user(
    session: DatabaseSessionDependency,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ],
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "AUTHENTICATION_REQUIRED",
                "message": "A valid bearer token is required.",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_service = AccessTokenService(get_settings())

    try:
        user_id = token_service.decode_user_id(
            credentials.credentials
        )
    except InvalidAccessTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_ACCESS_TOKEN",
                "message": str(exc),
            },
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    repository = SqlAlchemyUserRepository(session)
    user = await repository.get_by_id(user_id)

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_ACCESS_TOKEN",
                "message": (
                    "The authenticated user is unavailable."
                ),
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


CurrentUserDependency = Annotated[
    User,
    Depends(get_current_user),
]
