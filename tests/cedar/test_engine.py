from pathlib import Path

import pytest

from packages.cedar_adapter.client import CedarClientError
from packages.cedar_adapter.engine import CedarPolicyEngine
from packages.cedar_adapter.models import CedarAuthorizationResponse, CedarHealth
from packages.domain.enums import AgentName
from packages.domain.models import PolicyRequest
from packages.evaluation.cases import build_evaluation_state


class FakeClient:
    def __init__(self, *, request_id="REQ-1"):
        self.request_id = request_id

    def health(self):
        return CedarHealth(
            "ready",
            "cedar",
            "4.12.0",
            "demo-v1",
            "sha256:bundle",
            "sha256:schema",
            "passed",
        )

    def authorize(self, request):
        return CedarAuthorizationResponse(
            self.request_id,
            "allow",
            ("BASE-PERMIT-REGISTERED",),
            (),
            "demo-v1",
            "sha256:bundle",
            1,
        )


def policy_request():
    return PolicyRequest(
        "REQ-1",
        AgentName.INVENTORY,
        "get_order",
        "shipment_action",
        "ORD-8842",
        {
            "tool_owner": "inventory",
            "effect_class": "read",
            "arguments": {},
            "resource": {},
        },
    )


def engine(client=None, expected_hash=None):
    return CedarPolicyEngine(
        client or FakeClient(),
        metadata_path=Path("policies/demo-v1/metadata.json"),
        expected_bundle_hash=expected_hash,
    )


def test_startup_pins_bundle_and_exposes_health_metadata():
    cedar = engine(expected_hash="sha256:bundle")
    cedar.validate_startup()
    assert cedar.describe()["policy_engine_ready"] is True
    assert cedar.describe()["cedar_runtime_version"] == "4.12.0"


def test_startup_rejects_unexpected_bundle_hash():
    with pytest.raises(CedarClientError, match="bundle hash"):
        engine(expected_hash="sha256:other").validate_startup()


def test_response_correlation_mismatch_fails_closed():
    cedar = engine(FakeClient(request_id="REQ-WRONG"))
    cedar.validate_startup()
    with pytest.raises(CedarClientError, match="request ID"):
        cedar.evaluate(policy_request(), build_evaluation_state().state)

