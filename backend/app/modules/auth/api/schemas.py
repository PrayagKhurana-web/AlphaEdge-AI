"""Pydantic schemas for authentication endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
)

from app.modules.auth.application.service import (
    AuthenticationResult,
)
from app.modules.auth.domain.entities import User


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=20, max_length=512)


class MessageResponse(BaseModel):
    message: str


class UserResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    email: EmailStr
    is_active: bool = Field(alias="isActive")
    is_email_verified: bool = Field(
        alias="isEmailVerified"
    )
    email_verified_at: datetime | None = Field(
        alias="emailVerifiedAt"
    )
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    @classmethod
    def from_domain(cls, user: User) -> "UserResponse":
        return cls(
            id=user.id,
            email=user.email,
            isActive=user.is_active,
            isEmailVerified=user.is_email_verified,
            emailVerifiedAt=user.email_verified_at,
            createdAt=user.created_at,
            updatedAt=user.updated_at,
        )


class TokenResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    access_token: str = Field(alias="accessToken")
    token_type: str = Field(
        default="bearer",
        alias="tokenType",
    )
    user: UserResponse

    @classmethod
    def from_result(
        cls,
        result: AuthenticationResult,
    ) -> "TokenResponse":
        return cls(
            accessToken=result.access_token,
            tokenType="bearer",
            user=UserResponse.from_domain(result.user),
        )
