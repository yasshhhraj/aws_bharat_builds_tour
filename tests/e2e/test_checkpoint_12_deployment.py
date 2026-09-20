import asyncio
from pathlib import Path

import boto3
import httpx
import pytest

from apps.api.dependencies import reset_run_service
from apps.api.main import app
from packages.domain.errors import StorageConfigurationError
from packages.storage.dynamodb import DynamoDBTraceStore


async def request(method: str, path: str, **kwargs):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


def setup_function():
    reset_run_service()


def teardown_function():
    reset_run_service()


def test_aws_deployment_requires_demo_secret_for_mutations(monkeypatch):
    monkeypatch.setenv("MANIFEST_DEPLOYMENT_MODE", "aws")
    monkeypatch.setenv("DEMO_ACCESS_SECRET", "checkpoint-12-access-secret")
    monkeypatch.setenv("MANIFEST_AGENT_RUNTIME", "strands")
    monkeypatch.setenv("MANIFEST_MODEL_PROVIDER", "recorded")
    monkeypatch.setenv("MANIFEST_MODEL_ID", "manifest-recorded-v1")
    monkeypatch.setenv("MANIFEST_STORAGE_BACKEND", "memory")
    monkeypatch.setenv("MANIFEST_POLICY_ENGINE", "python_reference")

    payload = {"order_id": "ORD-8842", "mode": "enforce", "scenario": "benign"}

    async def scenario():
        health = await request("GET", "/health/ready")
        assert health.status_code == 200
        assert health.json()["deployment_mode"] == "aws"
        assert health.json()["demo_access_required"] is True
        assert health.json()["demo_access_ready"] is True

        missing = await request("POST", "/v1/runs", json=payload)
        assert missing.status_code == 401
        assert missing.json()["error"]["code"] == "DEMO_ACCESS_UNAUTHORIZED"

        wrong = await request(
            "POST",
            "/v1/runs",
            headers={"X-Manifest-Demo-Secret": "wrong"},
            json=payload,
        )
        assert wrong.status_code == 401

        accepted = await request(
            "POST",
            "/v1/runs",
            headers={"X-Manifest-Demo-Secret": "checkpoint-12-access-secret"},
            json=payload,
        )
        assert accepted.status_code == 201
        assert accepted.json()["status"] == "completed"

        reset = await request("POST", "/v1/demo/reset")
        assert reset.status_code == 401

    asyncio.run(scenario())


def test_aws_deployment_fails_closed_without_access_configuration(monkeypatch):
    monkeypatch.setenv("MANIFEST_DEPLOYMENT_MODE", "aws")
    monkeypatch.delenv("DEMO_ACCESS_SECRET", raising=False)
    monkeypatch.setenv("MANIFEST_STORAGE_BACKEND", "memory")
    monkeypatch.setenv("MANIFEST_POLICY_ENGINE", "python_reference")

    async def scenario():
        response = await request(
            "POST",
            "/v1/runs",
            json={"order_id": "ORD-8842", "mode": "enforce", "scenario": "benign"},
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "DEMO_ACCESS_NOT_CONFIGURED"

    asyncio.run(scenario())


def test_aws_dynamodb_uses_instance_role_and_managed_endpoint(monkeypatch):
    captured = {}
    sentinel = object()

    def fake_client(service_name, **kwargs):
        captured["service_name"] = service_name
        captured.update(kwargs)
        return sentinel

    monkeypatch.setenv("MANIFEST_DEPLOYMENT_MODE", "aws")
    monkeypatch.setenv("MANIFEST_DYNAMODB_TABLE", "manifest-aws-demo")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.delenv("MANIFEST_DYNAMODB_ENDPOINT", raising=False)
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.setattr(boto3, "client", fake_client)

    store = DynamoDBTraceStore()

    assert store.client is sentinel
    assert store.endpoint_url is None
    assert store.describe()["storage_mode"] == "dynamodb_aws"
    assert captured["service_name"] == "dynamodb"
    assert captured["region_name"] == "us-east-1"
    assert "endpoint_url" not in captured
    assert "aws_access_key_id" not in captured
    assert "aws_secret_access_key" not in captured


def test_aws_dynamodb_rejects_local_endpoint_or_fake_credentials(monkeypatch):
    monkeypatch.setenv("MANIFEST_DEPLOYMENT_MODE", "aws")
    monkeypatch.setenv("MANIFEST_DYNAMODB_ENDPOINT", "http://127.0.0.1:18000")
    with pytest.raises(StorageConfigurationError, match="must not configure"):
        DynamoDBTraceStore(client=object())

    monkeypatch.delenv("MANIFEST_DYNAMODB_ENDPOINT")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "local")
    with pytest.raises(StorageConfigurationError, match="instance role"):
        DynamoDBTraceStore(client=object())


def test_dashboard_carries_access_secret_only_in_mutation_header():
    api_source = (Path(__file__).resolve().parents[2] / "apps/dashboard/static/js/api.js").read_text(encoding="utf-8")
    app_source = (Path(__file__).resolve().parents[2] / "apps/dashboard/static/js/app.js").read_text(encoding="utf-8")

    assert "X-Manifest-Demo-Secret" in api_source
    assert "sessionStorage" in app_source
    assert "manifestDemoAccessSecret" in app_source
    assert "localStorage" not in app_source
