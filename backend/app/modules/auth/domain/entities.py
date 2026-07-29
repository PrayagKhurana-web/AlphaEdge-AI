"""Domain entities for authentication."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class User:
    id: int
    email: str
    password_hash: str
    is_active: bool
    is_email_verified: bool
    email_verified_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class EmailVerificationToken:
    id: int
    user_id: int
    token_hash: str
    expires_at: datetime
    used_at: datetime | None
    created_at: datetime
