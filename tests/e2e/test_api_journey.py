import asyncio
import os

import httpx

from apps.api.dependencies import reset_run_service
from apps.api.main import app


async def request(method: str, path: str, **kwargs):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


def setup_function():
    reset_run_service()


def test_api_complete_journey():
    async def scenario():
        health = await request("GET", "/health/ready")
        assert health.status_code == 200
        assert health.json()["governor_mode"] == "policy_enforced"
        assert health.json()["policy_engine"] == os.environ.get(
            "MANIFEST_POLICY_ENGINE", "python_reference"
        )

        orders = await request("GET", "/v1/fixtures/orders")
        assert orders.status_code == 200
        assert orders.json()["items"][0]["order_id"] == "ORD-8842"

        run = await request(
            "POST",
            "/v1/runs",
            json={"order_id": "ORD-8842", "mode": "enforce", "scenario": "benign"},
        )
        assert run.status_code == 201
        summary = run.json()
        assert summary["status"] == "completed"
        trace_id = summary["trace_id"]

        stored = await request("GET", f"/v1/runs/{trace_id}")
        assert stored.status_code == 200
        assert stored.json() == summary

        events = await request("GET", f"/v1/traces/{trace_id}/events")
        assert events.status_code == 200
        items = events.json()["items"]
        assert len(items) == summary["event_count"]
        assert [item["sequence"] for item in items] == list(range(1, len(items) + 1))

        reset = await request("POST", "/v1/demo/reset")
        assert reset.status_code == 200
        assert reset.json() == {"status": "reset", "removed_run_count": 1}

    asyncio.run(scenario())


def test_api_errors_use_safe_envelope():
    async def scenario():
        unknown_order = await request(
            "POST", "/v1/runs", json={"order_id": "UNKNOWN", "mode": "shadow"}
        )
        assert unknown_order.status_code == 404
        assert unknown_order.json()["error"]["code"] == "ORDER_NOT_FOUND"

        unknown_trace = await request("GET", "/v1/runs/TR-UNKNOWN")
        assert unknown_trace.status_code == 404
        assert unknown_trace.json()["error"]["code"] == "TRACE_NOT_FOUND"

        invalid_mode = await request(
            "POST", "/v1/runs", json={"order_id": "ORD-8842", "mode": "invalid"}
        )
        assert invalid_mode.status_code == 422
        assert invalid_mode.json()["error"]["code"] == "VALIDATION_ERROR"

    asyncio.run(scenario())
