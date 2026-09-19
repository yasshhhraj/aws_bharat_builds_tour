import asyncio
from pathlib import Path

import httpx

from apps.api.dependencies import reset_run_service
from apps.api.main import app


async def request(method: str, path: str, **kwargs):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        return await client.request(method, path, **kwargs)


def setup_function():
    reset_run_service()


def test_dashboard_assets_are_complete_and_local_only():
    async def scenario():
        root = await request("GET", "/")
        assert root.status_code == 307
        assert root.headers["location"] == "/dashboard/"

    asyncio.run(scenario())

    static = Path(__file__).resolve().parents[2] / "apps" / "dashboard" / "static"
    expected = (
        "index.html",
        "styles.css",
        "js/api.js",
        "js/state.js",
        "js/format.js",
        "js/charts.js",
        "js/render.js",
        "js/app.js",
    )
    for relative_path in expected:
        assert (static / relative_path).is_file(), relative_path

    page = (static / "index.html").read_text(encoding="utf-8")
    assert "Manifest" in page
    assert "Trajectory control plane" in page
    assert 'src="/dashboard/js/app.js"' in page
    assert "https://" not in page
    assert "http://" not in page


def test_health_discloses_dashboard_and_projection_capabilities():
    async def scenario():
        response = await request("GET", "/health/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["version"] == "0.7.0"
        assert body["dashboard_mode"] == "static_no_build"
        assert body["dashboard_ready"] is True
        assert body["projection_version"] == "dashboard-v1"

    asyncio.run(scenario())


def test_adversarial_projection_joins_risk_spend_and_provenance():
    async def scenario():
        run = await request(
            "POST",
            "/v1/runs",
            json={
                "order_id": "ORD-8842",
                "mode": "enforce",
                "scenario": "adversarial",
            },
        )
        assert run.status_code == 201
        trace_id = run.json()["trace_id"]

        before_events = await request("GET", f"/v1/traces/{trace_id}/events")
        projection = await request("GET", f"/v1/traces/{trace_id}/projection")
        after_events = await request("GET", f"/v1/traces/{trace_id}/events")

        assert projection.status_code == 200
        body = projection.json()
        assert body["trace_id"] == trace_id
        assert body["risk_signal_score"] == 60
        assert body["risk_signal_method"] == (
            "20_per_unique_non_allow_policy_family_capped_100"
        )
        assert body["weight_provenance"]["authoritative_value"] == 500
        assert body["weight_provenance"]["final_value"] == 500
        assert [
            item["attempted_value"]
            for item in body["weight_provenance"]["attempts"]
        ] == [50, 500]
        assert body["spend_points"][-1]["projected_minor"] == 455000
        assert before_events.json() == after_events.json()

        missing = await request("GET", "/v1/traces/TR-UNKNOWN/projection")
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "TRACE_NOT_FOUND"

    asyncio.run(scenario())
