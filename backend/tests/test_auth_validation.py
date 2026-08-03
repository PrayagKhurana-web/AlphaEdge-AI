import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def transport() -> ASGITransport:
    return ASGITransport(app=app)


@pytest.mark.asyncio
async def test_register_rejects_invalid_email(
    transport: ASGITransport,
) -> None:
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "ValidPass123",
            },
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_rejects_short_password(
    transport: ASGITransport,
) -> None:
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "password": "short",
            },
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_rejects_empty_password(
    transport: ASGITransport,
) -> None:
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "",
            },
        )

    assert response.status_code == 422
