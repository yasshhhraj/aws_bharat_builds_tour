import asyncio

import httpx

from apps.api.dependencies import reset_run_service
from apps.api.main import app
from apps.runtime.strands_runtime import StrandsRuntime
from packages.domain.errors import ProviderTimeoutError


async def request(method: str, path: str, **kwargs):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


def setup_function():
    reset_run_service()


def teardown_function():
    reset_run_service()


def test_health_discloses_fixed_recorded_model_without_hosted_credentials(monkeypatch):
    monkeypatch.setenv("MANIFEST_AGENT_RUNTIME", "strands")
    monkeypatch.setenv("MANIFEST_MODEL_PROVIDER", "recorded")
    monkeypatch.setenv("MANIFEST_MODEL_ID", "manifest-recorded-v1")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("BEDROCK_MANTLE_API_KEY", raising=False)

    async def scenario():
        response = await request("GET", "/health/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["runtime_mode"] == "strands"
        assert body["model_provider"] == "recorded"
        assert body["requested_model_id"] == "manifest-recorded-v1"
        assert body["resolved_model_id"] == "manifest-recorded-v1"
        assert body["provider_route_kind"] == "fixed"
        assert body["provider_fallback_active"] is False

    asyncio.run(scenario())


def test_provider_timeout_returns_safe_trace_envelope_and_no_effects(monkeypatch):
    monkeypatch.setenv("MANIFEST_AGENT_RUNTIME", "strands")
    monkeypatch.setenv("MANIFEST_MODEL_PROVIDER", "openrouter")
    monkeypatch.setenv("MANIFEST_MODEL_ID", "openrouter/free")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-only-value")

    def timeout(_self, _request):
        raise ProviderTimeoutError("OpenRouter model request timed out.")

    monkeypatch.setattr(StrandsRuntime, "invoke", timeout)

    async def scenario():
        response = await request(
            "POST",
            "/v1/runs",
            json={"order_id": "ORD-8842", "mode": "enforce", "scenario": "benign"},
        )
        assert response.status_code == 504
        error = response.json()["error"]
        assert error["code"] == "PROVIDER_TIMEOUT"
        assert error["message"] == "OpenRouter model request timed out."
        assert error["trace_id"].startswith("TR-")
        assert "test-only-value" not in response.text

        trace_id = error["trace_id"]
        stored = await request("GET", f"/v1/runs/{trace_id}")
        assert stored.status_code == 200
        assert stored.json()["status"] == "failed"
        assert stored.json()["confirmed_booking_id"] is None
        assert stored.json()["notification_id"] is None

        projection = await request("GET", f"/v1/traces/{trace_id}/projection")
        assert projection.json()["failure_code"] == "PROVIDER_TIMEOUT"
        assert projection.json()["booking_confirmation_count"] == 0
        assert projection.json()["notification_count"] == 0

        verification = await request("GET", f"/v1/traces/{trace_id}/verify")
        assert verification.json()["valid"] is True

    asyncio.run(scenario())
