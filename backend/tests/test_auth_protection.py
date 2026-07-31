import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def transport() -> ASGITransport:
    return ASGITransport(app=app)


@pytest.mark.asyncio
async def test_get_me_requires_bearer_token(
    transport: ASGITransport,
) -> None:
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {
        "detail": {
            "code": "AUTHENTICATION_REQUIRED",
            "message": "A valid bearer token is required.",
        }
    }


@pytest.mark.asyncio
async def test_get_me_rejects_malformed_token(
    transport: ASGITransport,
) -> None:
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/v1/auth/me",
            headers={
                "Authorization": "Bearer definitely-not-a-jwt",
            },
        )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"

    body = response.json()
    assert body["detail"]["code"] == "INVALID_ACCESS_TOKEN"
    assert body["detail"]["message"]
