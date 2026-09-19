from pathlib import Path

import pytest

from packages.cedar_adapter.mapping import CedarMappingError, CedarPolicyMetadata
from packages.cedar_adapter.models import CedarAuthorizationResponse
from packages.domain.enums import AgentName, DecisionOutcome
from packages.domain.models import PolicyRequest
from packages.evaluation.cases import build_evaluation_state


METADATA = Path("policies/demo-v1/metadata.json")


def response(*ids, decision="deny", errors=()):
    return CedarAuthorizationResponse(
        request_id="REQ-1",
        decision=decision,
        determining_policy_ids=ids,
        errors=errors,
        policy_version="demo-v1",
        bundle_hash="sha256:test",
        evaluation_us=10,
    )


def request():
    return PolicyRequest(
        "REQ-1",
        AgentName.DISPATCH,
        "create_dispatch_plan",
        "shipment_action",
        "ORD-8842",
        {
            "tool_owner": "dispatch",
            "effect_class": "operational_write",
            "arguments": {"weight_fact_id": "UNKNOWN"},
            "resource": {},
        },
    )


def test_determining_policies_map_in_stable_family_order():
    metadata = CedarPolicyMetadata(METADATA)
    signals = metadata.map_response(
        response("COLD-001", "PROV-001"),
        request(),
        build_evaluation_state().state,
    )
    assert [item.policy_id for item in signals] == ["PROV-001", "COLD-001"]
    assert all(item.outcome == DecisionOutcome.BLOCK for item in signals)


def test_implicit_deny_is_fail_closed():
    signals = CedarPolicyMetadata(METADATA).map_response(
        response(), request(), build_evaluation_state().state
    )
    assert signals[0].policy_id == "CEDAR-IMPLICIT-DENY"
    assert signals[0].outcome == DecisionOutcome.BLOCK


@pytest.mark.parametrize(
    "cedar_response",
    [response("UNKNOWN"), response("PROV-001", errors=("validation",))],
)
def test_unknown_policies_and_diagnostics_fail_closed(cedar_response):
    with pytest.raises(CedarMappingError):
        CedarPolicyMetadata(METADATA).map_response(
            cedar_response, request(), build_evaluation_state().state
        )

