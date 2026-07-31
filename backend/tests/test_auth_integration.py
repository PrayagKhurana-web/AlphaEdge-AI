from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.database.base import Base
from app.core.database.session import get_db_session
from app.main import app

# Import the model so its table is registered in Base.metadata.
from app.modules.auth.infrastructure.models import UserModel  # noqa: F401


@pytest_asyncio.fixture
async def client(
    tmp_path: Path,
) -> AsyncIterator[AsyncClient]:
    database_path = tmp_path / "auth-integration.db"

    test_engine = create_async_engine(
        f"sqlite+aiosqlite:///{database_path.as_posix()}",
    )

    test_session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def override_get_db_session() -> (
        AsyncIterator[AsyncSession]
    ):
        async with test_session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = (
        override_get_db_session
    )

    transport = ASGITransport(app=app)

    try:
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()

        async with test_engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)

        await test_engine.dispose()


@pytest.mark.asyncio
async def test_register_creates_user_and_returns_token(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "  NewUser@Example.com ",
            "password": "SecurePass123",
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert body["accessToken"]
    assert body["tokenType"] == "bearer"
    assert body["user"]["email"] == "newuser@example.com"
    assert body["user"]["isActive"] is True
    assert isinstance(body["user"]["id"], int)


@pytest.mark.asyncio
async def test_duplicate_registration_returns_conflict(
    client: AsyncClient,
) -> None:
    payload = {
        "email": "duplicate@example.com",
        "password": "SecurePass123",
    }

    first_response = await client.post(
        "/api/v1/auth/register",
        json=payload,
    )
    second_response = await client.post(
        "/api/v1/auth/register",
        json=payload,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json() == {
        "detail": {
            "code": "EMAIL_ALREADY_REGISTERED",
            "message": (
                "An account with this email already exists."
            ),
        }
    }


@pytest.mark.asyncio
async def test_registered_user_can_login(
    client: AsyncClient,
) -> None:
    registration = {
        "email": "login@example.com",
        "password": "SecurePass123",
    }

    register_response = await client.post(
        "/api/v1/auth/register",
        json=registration,
    )

    login_response = await client.post(
        "/api/v1/auth/login",
        json=registration,
    )

    assert register_response.status_code == 201
    assert login_response.status_code == 200

    body = login_response.json()

    assert body["accessToken"]
    assert body["tokenType"] == "bearer"
    assert body["user"]["email"] == "login@example.com"


@pytest.mark.asyncio
async def test_authenticated_user_can_access_me(
    client: AsyncClient,
) -> None:
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "me@example.com",
            "password": "SecurePass123",
        },
    )

    assert register_response.status_code == 201

    registration_body = register_response.json()
    access_token = registration_body["accessToken"]

    me_response = await client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    assert me_response.status_code == 200

    body = me_response.json()

    assert body["id"] == registration_body["user"]["id"]
    assert body["email"] == "me@example.com"
    assert body["isActive"] is True
