"""Database repository for users."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.domain.entities import User
from app.modules.auth.infrastructure.models import UserModel


def _to_domain(model: UserModel) -> User:
    return User(
        id=model.id,
        email=model.email,
        password_hash=model.password_hash,
        is_active=model.is_active,
        created_at=model.created_at,
        updated_at=model.updated_at,
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
        return _to_domain(model) if model is not None else None

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.email == email)
        )
        model = result.scalar_one_or_none()
        return _to_domain(model) if model is not None else None

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
        )

        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)

        return _to_domain(model)
