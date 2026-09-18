import asyncio

import httpx

from apps.api.dependencies import reset_run_service
from apps.api.main import app


async def request(method: str, path: str, **kwargs):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


def setup_function():
    reset_run_service()


def test_adversarial_enforce_api_exposes_decisions_and_approval():
    async def scenario():
        run = await request("POST", "/v1/runs", json={
            "order_id": "ORD-8842", "mode": "enforce", "scenario": "adversarial"
        })
        assert run.status_code == 201
        summary = run.json()
        assert summary["status"] == "pending_approval"
        assert summary["projected_spend_minor"] == 455000
        trace_id = summary["trace_id"]

        decisions = await request("GET", f"/v1/traces/{trace_id}/decisions")
        assert decisions.status_code == 200
        assert len(decisions.json()["items"]) == summary["decision_count"]
        assert {item["reason_code"] for item in decisions.json()["items"]} >= {
            "PROVENANCE_VALUE_MISMATCH",
            "COLD_CHAIN_CARRIER_REQUIRED",
            "SPEND_APPROVAL_REQUIRED",
        }

        approvals = await request("GET", f"/v1/approvals?trace_id={trace_id}")
        assert approvals.status_code == 200
        assert approvals.json()["items"][0]["approval_id"] == summary["pending_approval_id"]

    asyncio.run(scenario())
