import asyncio

import httpx

from apps.api.dependencies import reset_run_service
from apps.api.main import app


SECRET = "checkpoint-3-test-secret"


async def request(method: str, path: str, **kwargs):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


def setup_function():
    reset_run_service()


def test_api_approval_completes_same_run(monkeypatch):
    monkeypatch.setenv("DEMO_APPROVER_SECRET", SECRET)

    async def scenario():
        run = await request("POST", "/v1/runs", json={
            "order_id": "ORD-8842", "mode": "enforce", "scenario": "adversarial"
        })
        summary = run.json()
        approval_id = summary["pending_approval_id"]

        approval = await request("GET", f"/v1/approvals/{approval_id}")
        assert approval.status_code == 200
        assert approval.json()["status"] == "pending_approval"
        assert approval.json()["version"] == 1

        decided = await request(
            "POST",
            f"/v1/approvals/{approval_id}",
            headers={"X-Demo-Approver-Secret": SECRET},
            json={
                "decision": "approve",
                "approver_label": "DEMO-APPROVER-OPS-1",
                "comment": "Approved through the API test.",
                "expected_version": 1,
                "idempotency_key": "approval-api-approve-001",
            },
        )
        assert decided.status_code == 200
        body = decided.json()
        assert body["approval"]["status"] == "approved"
        assert body["run"]["trace_id"] == summary["trace_id"]
        assert body["run"]["status"] == "completed"
        assert body["run"]["spend_committed_minor"] == 455000
        assert body["run"]["spend_reserved_minor"] == 0
        assert body["run"]["notification_id"] == "NOTIFY-ORD-8842"

        events = await request("GET", f"/v1/traces/{summary['trace_id']}/events")
        assert SECRET not in events.text

        replay = await request(
            "POST",
            f"/v1/approvals/{approval_id}",
            headers={"X-Demo-Approver-Secret": SECRET},
            json={
                "decision": "approve",
                "approver_label": "DEMO-APPROVER-OPS-1",
                "comment": "Approved through the API test.",
                "expected_version": 1,
                "idempotency_key": "approval-api-approve-001",
            },
        )
        assert replay.status_code == 200
        assert replay.json()["idempotent_replay"] is True

    asyncio.run(scenario())


def test_api_rejects_unauthorized_and_stale_requests(monkeypatch):
    monkeypatch.setenv("DEMO_APPROVER_SECRET", SECRET)

    async def scenario():
        run = await request("POST", "/v1/runs", json={
            "order_id": "ORD-8842", "mode": "enforce", "scenario": "adversarial"
        })
        approval_id = run.json()["pending_approval_id"]
        payload = {
            "decision": "reject",
            "approver_label": "DEMO-APPROVER-OPS-2",
            "comment": None,
            "expected_version": 1,
            "idempotency_key": "approval-api-reject-001",
        }

        unauthorized = await request("POST", f"/v1/approvals/{approval_id}", json=payload)
        assert unauthorized.status_code == 401
        assert unauthorized.json()["error"]["code"] == "APPROVER_UNAUTHORIZED"

        stale = await request(
            "POST",
            f"/v1/approvals/{approval_id}",
            headers={"X-Demo-Approver-Secret": SECRET},
            json={**payload, "expected_version": 2},
        )
        assert stale.status_code == 409
        assert stale.json()["error"]["code"] == "APPROVAL_VERSION_CONFLICT"

        rejected = await request(
            "POST",
            f"/v1/approvals/{approval_id}",
            headers={"X-Demo-Approver-Secret": SECRET},
            json=payload,
        )
        assert rejected.status_code == 200
        assert rejected.json()["approval"]["status"] == "rejected"
        assert rejected.json()["run"]["status"] == "cancelled"

    asyncio.run(scenario())


def test_api_reports_missing_approval_secret_configuration(monkeypatch):
    monkeypatch.delenv("DEMO_APPROVER_SECRET", raising=False)

    async def scenario():
        run = await request("POST", "/v1/runs", json={
            "order_id": "ORD-8842", "mode": "enforce", "scenario": "adversarial"
        })
        approval_id = run.json()["pending_approval_id"]
        response = await request(
            "POST",
            f"/v1/approvals/{approval_id}",
            headers={"X-Demo-Approver-Secret": "anything"},
            json={
                "decision": "approve",
                "approver_label": "DEMO-APPROVER-OPS-1",
                "expected_version": 1,
                "idempotency_key": "approval-api-missing-secret-001",
            },
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "APPROVAL_AUTH_NOT_CONFIGURED"

    asyncio.run(scenario())


def test_api_rejects_conflicting_replay_and_invalid_requests(monkeypatch):
    monkeypatch.setenv("DEMO_APPROVER_SECRET", SECRET)

    async def scenario():
        missing = await request("GET", "/v1/approvals/APR-UNKNOWN")
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "APPROVAL_NOT_FOUND"

        run = await request("POST", "/v1/runs", json={
            "order_id": "ORD-8842", "mode": "enforce", "scenario": "adversarial"
        })
        approval_id = run.json()["pending_approval_id"]
        base = {
            "decision": "approve",
            "approver_label": "DEMO-APPROVER-OPS-1",
            "comment": None,
            "expected_version": 1,
            "idempotency_key": "approval-api-conflict-001",
        }
        first = await request(
            "POST",
            f"/v1/approvals/{approval_id}",
            headers={"X-Demo-Approver-Secret": SECRET},
            json=base,
        )
        assert first.status_code == 200

        conflict = await request(
            "POST",
            f"/v1/approvals/{approval_id}",
            headers={"X-Demo-Approver-Secret": SECRET},
            json={**base, "decision": "reject"},
        )
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "APPROVAL_IDEMPOTENCY_CONFLICT"

        invalid = await request(
            "POST",
            f"/v1/approvals/{approval_id}",
            headers={"X-Demo-Approver-Secret": SECRET},
            json={**base, "approver_label": "not-an-allowed-label"},
        )
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"

    asyncio.run(scenario())
