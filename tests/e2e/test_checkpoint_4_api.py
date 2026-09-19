import asyncio

import httpx

from apps.api.dependencies import reset_run_service
from apps.api.main import app


TAMPER_SECRET = "checkpoint-4-tamper-secret"


async def request(method: str, path: str, **kwargs):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


def setup_function():
    reset_run_service()


def test_api_exposes_hashes_and_clean_verification(monkeypatch):
    monkeypatch.delenv("ENABLE_DEMO_TAMPER", raising=False)
    monkeypatch.delenv("DEMO_TAMPER_SECRET", raising=False)

    async def scenario():
        health = await request("GET", "/health/ready")
        assert health.status_code == 200
        assert health.json()["storage_mode"] == "memory_hash_chain"
        assert health.json()["ledger_algorithm"] == "sha256"
        assert health.json()["ledger_schema_version"] == "ledger-event-v1"
        assert health.json()["verify_ready"] is True

        run = await request("POST", "/v1/runs", json={
            "order_id": "ORD-8842", "mode": "enforce", "scenario": "benign"
        })
        trace_id = run.json()["trace_id"]
        events = await request("GET", f"/v1/traces/{trace_id}/events")
        first = events.json()["items"][0]
        assert first["event_id"].startswith("EVT-")
        assert first["schema_version"] == "ledger-event-v1"
        assert first["previous_hash"].startswith("sha256:")
        assert first["event_hash"].startswith("sha256:")

        verified = await request("GET", f"/v1/traces/{trace_id}/verify")
        assert verified.status_code == 200
        assert verified.json()["valid"] is True
        assert verified.json()["checked_event_count"] == len(events.json()["items"])

        missing = await request("GET", "/v1/traces/TR-UNKNOWN/verify")
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "TRACE_NOT_FOUND"

    asyncio.run(scenario())


def test_demo_tamper_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ENABLE_DEMO_TAMPER", raising=False)
    monkeypatch.delenv("DEMO_TAMPER_SECRET", raising=False)

    async def scenario():
        response = await request(
            "POST",
            "/v1/demo/traces/TR-UNKNOWN/tamper",
            json={"sequence": 1, "replacement_summary": "Changed"},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "LEDGER_TAMPER_DISABLED"

    asyncio.run(scenario())


def test_disposable_terminal_trace_can_be_tampered_and_detected(monkeypatch):
    monkeypatch.setenv("ENABLE_DEMO_TAMPER", "true")
    monkeypatch.setenv("DEMO_TAMPER_SECRET", TAMPER_SECRET)

    async def scenario():
        run = await request("POST", "/v1/runs", json={
            "order_id": "ORD-8842", "mode": "enforce", "scenario": "benign"
        })
        trace_id = run.json()["trace_id"]
        clean = await request("GET", f"/v1/traces/{trace_id}/verify")
        assert clean.json()["valid"] is True

        unauthorized = await request(
            "POST",
            f"/v1/demo/traces/{trace_id}/tamper",
            headers={"X-Demo-Tamper-Secret": "wrong"},
            json={"sequence": 5, "replacement_summary": "Changed"},
        )
        assert unauthorized.status_code == 401

        tampered = await request(
            "POST",
            f"/v1/demo/traces/{trace_id}/tamper",
            headers={"X-Demo-Tamper-Secret": TAMPER_SECRET},
            json={"sequence": 5, "replacement_summary": "Disposable alteration"},
        )
        assert tampered.status_code == 200
        assert tampered.json()["sequence"] == 5

        invalid = await request("GET", f"/v1/traces/{trace_id}/verify")
        assert invalid.status_code == 200
        assert invalid.json()["valid"] is False
        assert invalid.json()["first_bad_sequence"] == 5
        assert invalid.json()["failure_code"] == "EVENT_HASH_MISMATCH"

    asyncio.run(scenario())


def test_pending_trace_cannot_be_tampered(monkeypatch):
    monkeypatch.setenv("ENABLE_DEMO_TAMPER", "true")
    monkeypatch.setenv("DEMO_TAMPER_SECRET", TAMPER_SECRET)

    async def scenario():
        run = await request("POST", "/v1/runs", json={
            "order_id": "ORD-8842", "mode": "enforce", "scenario": "adversarial"
        })
        response = await request(
            "POST",
            f"/v1/demo/traces/{run.json()['trace_id']}/tamper",
            headers={"X-Demo-Tamper-Secret": TAMPER_SECRET},
            json={"sequence": 1, "replacement_summary": "Not allowed"},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "LEDGER_TAMPER_VALIDATION_ERROR"

    asyncio.run(scenario())
