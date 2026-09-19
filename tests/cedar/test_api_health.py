import asyncio

import httpx

from apps.api.dependencies import reset_run_service
from apps.api.main import app


def test_health_fails_safely_when_configured_engine_cannot_start(monkeypatch):
    async def scenario():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.get("/health/ready")

    monkeypatch.setenv("MANIFEST_POLICY_ENGINE", "not-a-policy-engine")
    reset_run_service()
    try:
        response = asyncio.run(scenario())
    finally:
        reset_run_service()
    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "POLICY_ENGINE_UNAVAILABLE",
            "message": "The configured policy engine is not ready.",
        }
    }

