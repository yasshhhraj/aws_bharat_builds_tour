import json

import pytest

from packages.cedar_adapter.context import build_cedar_request
from packages.domain.enums import AgentName
from packages.domain.models import PolicyRequest
from packages.evaluation.cases import build_evaluation_state


def request_for(arguments):
    return PolicyRequest(
        request_id="REQ-CEDAR-CONTEXT",
        principal=AgentName.CUSTOMER_COMMUNICATIONS,
        action="write_tracking_outbox",
        resource_type="shipment_action",
        resource_id="ORD-8842",
        context={
            "tool_owner": "customer_communications",
            "effect_class": "customer_disclosure",
            "arguments": arguments,
            "resource": {},
        },
    )


def test_context_is_whitelisted_and_raw_pii_never_crosses_boundary():
    state = build_evaluation_state().state
    cedar = build_cedar_request(
        request_for({"message": "user@example.invalid", "email": "hidden"}),
        state,
        bundle_hash="sha256:test",
    )
    encoded = json.dumps(cedar.as_dict())
    assert "user@example.invalid" not in encoded
    assert "hidden" not in encoded
    assert cedar.context["containsForbiddenPiiField"] is True
    assert cedar.resource == 'Manifest::ShipmentAction::"REQ-CEDAR-CONTEXT"'


def test_context_rejects_non_integer_money_values():
    state = build_evaluation_state().state
    state.spend_committed_minor = True
    with pytest.raises(ValueError, match="committed spend"):
        build_cedar_request(
            request_for({"template_id": "TRACKING_UPDATE_V1"}),
            state,
            bundle_hash="sha256:test",
        )

