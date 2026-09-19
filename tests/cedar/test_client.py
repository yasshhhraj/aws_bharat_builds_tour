import io
import json
from urllib.error import URLError

import pytest

import packages.cedar_adapter.client as client_module
from packages.cedar_adapter import CedarClient
from packages.cedar_adapter.client import CedarClientError


class FakeResponse:
    def __init__(self, value):
        self.body = io.BytesIO(json.dumps(value).encode("utf-8"))

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, size):
        return self.body.read(size)


def test_client_rejects_non_loopback_and_unbounded_timeouts():
    with pytest.raises(ValueError, match="loopback"):
        CedarClient("https://pdp.example.invalid")
    with pytest.raises(ValueError, match="timeout"):
        CedarClient("http://127.0.0.1:8765", timeout_ms=0)


def test_health_response_is_strictly_parsed(monkeypatch):
    monkeypatch.setattr(
        client_module,
        "urlopen",
        lambda request, timeout: FakeResponse(
            {
                "status": "ready",
                "engine": "cedar",
                "cedar_version": "4.12.0",
                "policy_version": "demo-v1",
                "bundle_hash": "sha256:bundle",
                "schema_hash": "sha256:schema",
                "validation": "passed",
            }
        ),
    )
    health = CedarClient("http://127.0.0.1:8765").health()
    assert health.engine == "cedar"
    assert health.bundle_hash == "sha256:bundle"


def test_transport_failures_are_safe_and_do_not_echo_payload(monkeypatch):
    monkeypatch.setattr(
        client_module,
        "urlopen",
        lambda request, timeout: (_ for _ in ()).throw(URLError("secret-body")),
    )
    with pytest.raises(CedarClientError) as caught:
        CedarClient("http://127.0.0.1:8765").health()
    assert "secret-body" not in str(caught.value)

