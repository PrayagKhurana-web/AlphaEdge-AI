"""Database repositories for authentication."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.domain.entities import (
    EmailVerificationToken,
    User,
)
from app.modules.auth.infrastructure.models import (
    EmailVerificationTokenModel,
    UserModel,
)


def _to_user_domain(model: UserModel) -> User:
    return User(
        id=model.id,
        email=model.email,
        password_hash=model.password_hash,
        is_active=model.is_active,
        is_email_verified=model.is_email_verified,
        email_verified_at=model.email_verified_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _to_token_domain(
    model: EmailVerificationTokenModel,
) -> EmailVerificationToken:
    return EmailVerificationToken(
        id=model.id,
        user_id=model.user_id,
        token_hash=model.token_hash,
        expires_at=model.expires_at,
        used_at=model.used_at,
        created_at=model.created_at,
    )


class SqlAlchemyUserRepository:
    """SQLAlchemy-backed user repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: int) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        model = result.scalar_one_or_none()
        return (
            _to_user_domain(model)
            if model is not None
            else None
        )

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.email == email)
        )
        model = result.scalar_one_or_none()
        return (
            _to_user_domain(model)
            if model is not None
            else None
        )

    async def create(
        self,
        *,
        email: str,
        password_hash: str,
    ) -> User:
        model = UserModel(
            email=email,
            password_hash=password_hash,
            is_active=True,
            is_email_verified=False,
        )

        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)

        return _to_user_domain(model)

    async def mark_email_verified(
        self,
        *,
        user_id: int,
        verified_at: datetime,
        commit: bool = True,
    ) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        model = result.scalar_one_or_none()

        if model is None:
            return None

        model.is_email_verified = True
        model.email_verified_at = verified_at

        if commit:
            await self._session.commit()
            await self._session.refresh(model)

        return _to_user_domain(model)


class SqlAlchemyEmailVerificationRepository:
    """Repository for single-use verification tokens."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def invalidate_active_tokens(
        self,
        *,
        user_id: int,
        used_at: datetime,
        commit: bool = True,
    ) -> None:
        await self._session.execute(
            update(EmailVerificationTokenModel)
            .where(
                EmailVerificationTokenModel.user_id == user_id,
                EmailVerificationTokenModel.used_at.is_(None),
            )
            .values(used_at=used_at)
        )

        if commit:
            await self._session.commit()

    async def create(
        self,
        *,
        user_id: int,
        token_hash: str,
        expires_at: datetime,
    ) -> EmailVerificationToken:
        model = EmailVerificationTokenModel(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )

        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)

        return _to_token_domain(model)

    async def get_active_by_hash(
        self,
        token_hash: str,
    ) -> EmailVerificationToken | None:
        result = await self._session.execute(
            select(EmailVerificationTokenModel).where(
                EmailVerificationTokenModel.token_hash == token_hash,
                EmailVerificationTokenModel.used_at.is_(None),
            )
        )
        model = result.scalar_one_or_none()

        return (
            _to_token_domain(model)
            if model is not None
            else None
        )

    async def mark_used(
        self,
        *,
        token_id: int,
        used_at: datetime,
        commit: bool = True,
    ) -> None:
        await self._session.execute(
            update(EmailVerificationTokenModel)
            .where(
                EmailVerificationTokenModel.id == token_id,
                EmailVerificationTokenModel.used_at.is_(None),
            )
            .values(used_at=used_at)
        )

        if commit:
            await self._session.commit()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
