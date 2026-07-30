"""Authentication API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.modules.auth.api.dependencies import (
    AuthenticationServiceDependency,
    CurrentUserDependency,
)
from app.modules.auth.api.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.modules.auth.domain.exceptions import (
    EmailAlreadyRegisteredError,
    InactiveUserError,
    InvalidCredentialsError,
)


router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    payload: RegisterRequest,
    authentication_service: AuthenticationServiceDependency,
) -> TokenResponse:
    try:
        result = await authentication_service.register(
            email=str(payload.email),
            password=payload.password,
        )
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "EMAIL_ALREADY_REGISTERED",
                "message": str(exc),
            },
        ) from exc

    return TokenResponse.from_result(result)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate an existing user",
)
async def login(
    payload: LoginRequest,
    authentication_service: AuthenticationServiceDependency,
) -> TokenResponse:
    try:
        result = await authentication_service.login(
            email=str(payload.email),
            password=payload.password,
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_CREDENTIALS",
                "message": str(exc),
            },
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except InactiveUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "INACTIVE_USER",
                "message": str(exc),
            },
        ) from exc

    return TokenResponse.from_result(result)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the authenticated user",
)
async def get_me(
    current_user: CurrentUserDependency,
) -> UserResponse:
    return UserResponse.from_domain(current_user)
