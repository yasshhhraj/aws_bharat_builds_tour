"""Whitelist-based conversion from Manifest state to Cedar PARC input."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from packages.domain.models import PolicyRequest, TrajectoryState

from .models import CedarAuthorizationRequest


def build_cedar_request(
    request: PolicyRequest,
    state: TrajectoryState,
    *,
    bundle_hash: str,
) -> CedarAuthorizationRequest:
    mandate = state.mandate
    if mandate is None:
        raise ValueError("Shipment mandate is required for Cedar evaluation.")
    source = request.context
    owner = source.get("tool_owner")
    effect_class = source.get("effect_class")
    if not isinstance(owner, str) or not isinstance(effect_class, str):
        raise ValueError("Registered tool metadata is required for Cedar evaluation.")
    args = source.get("arguments")
    resource = source.get("resource")
    approval = source.get("approval")
    if not isinstance(args, dict) or not isinstance(resource, dict):
        raise ValueError("Typed tool context is required for Cedar evaluation.")
    if approval is None:
        approval = {}
    if not isinstance(approval, dict):
        raise ValueError("Approval context must be a record.")

    fact_id = args.get("weight_fact_id")
    fact = state.facts.get(str(fact_id)) if fact_id is not None else None
    prepared_id = args.get("prepared_action_id")
    prepared = (
        state.prepared_actions.get(str(prepared_id))
        if prepared_id is not None
        else None
    )
    policy_version = state.policy_version
    allowed_effects = sorted(item.value for item in mandate.allowed_effect_classes)
    attempted_weight = _strict_int(args.get("weight_value", 0), "attempted weight")
    authoritative_weight = _strict_int(
        fact.value if fact is not None else 0, "authoritative weight"
    )
    vehicle_capacity = _strict_int(resource.get("capacity_kg", 0), "vehicle capacity")
    committed = _strict_int(state.spend_committed_minor, "committed spend")
    reserved = _strict_int(state.spend_reserved_minor, "reserved spend")
    threshold = _strict_int(mandate.approval_threshold_minor, "approval threshold")
    template_variables = args.get("template_variables", {})
    variables_allowed = isinstance(template_variables, dict) and set(
        template_variables
    ).issubset({"order_id", "carrier_id"})
    forbidden = {"phone", "email", "address", "name", "payment", "message"}

    approval_status = str(approval.get("status", "none"))
    approval_label = str(approval.get("approver_label") or "")
    prepared_by = prepared.prepared_by.value if prepared is not None else ""
    context: dict[str, Any] = {
        "policyVersion": policy_version,
        "mandatePolicyVersion": mandate.policy_version,
        "allowedEffectClasses": allowed_effects,
        "cargoClass": mandate.cargo_class,
        "currency": mandate.currency,
        "principalId": request.principal.value,
        "provenanceFactPresent": fact is not None,
        "provenanceFactHashValid": bool(
            fact is not None and _valid_fact_hash(state.order_id, fact)
        ),
        "attemptedWeight": attempted_weight,
        "attemptedUnit": str(args.get("weight_unit", "")),
        "authoritativeWeight": authoritative_weight,
        "authoritativeUnit": str(fact.unit if fact is not None else ""),
        "vehicleMetadataPresent": bool(resource)
        if request.action == "create_dispatch_plan"
        else False,
        "vehicleAvailable": bool(resource.get("available", False)),
        "vehicleRefrigerated": bool(resource.get("refrigerated", False)),
        "vehicleCapacityKg": vehicle_capacity,
        "carrierMetadataPresent": bool(resource)
        if request.action in {"select_carrier_quote", "prepare_freight_booking"}
        else False,
        "coldChainCertified": bool(resource.get("cold_chain_certified", False)),
        "laneSupported": bool(resource.get("lane_supported", False)),
        "quoteIssuer": str(resource.get("quote_issuer", "")),
        "preparedActionPresent": prepared is not None,
        "preparedStatus": prepared.status.value if prepared is not None else "none",
        "preparedCurrency": prepared.currency if prepared is not None else "",
        "preparedBy": prepared_by,
        "actionHashMatches": bool(
            prepared is not None and args.get("action_hash") == prepared.action_hash
        ),
        "spendCommittedMinor": committed,
        "spendReservedMinor": reserved,
        "approvalThresholdMinor": threshold,
        "approvalStatus": approval_status,
        "approvalExpired": bool(approval.get("is_expired", False)),
        "approvalActionMatches": bool(
            prepared is not None
            and approval.get("prepared_action_id") == prepared.prepared_action_id
            and approval.get("action_hash") == prepared.action_hash
        ),
        "approvalStateMatches": bool(
            prepared is not None and approval.get("state_hash") == prepared.state_hash
        ),
        "approvalPolicyMatches": bool(
            approval.get("policy_version") == state.policy_version
        ),
        "approverLabel": approval_label,
        "approverConflictsWithPreparer": bool(
            prepared is not None and approval_label == prepared_by
        ),
        "containsForbiddenPiiField": bool(forbidden.intersection(args)),
        "templateId": str(args.get("template_id", "")),
        "syntheticRecipientValid": str(args.get("recipient_ref", "")).startswith(
            "DEMO-RECIPIENT-"
        ),
        "templateVariablesAllowed": variables_allowed,
    }
    principal_uid = f'Manifest::Agent::"{request.principal.value}"'
    action_uid = f'Manifest::Action::"{request.action}"'
    resource_uid = f'Manifest::ShipmentAction::"{request.request_id}"'
    entities = [
        {
            "uid": {"type": "Manifest::Agent", "id": request.principal.value},
            "attrs": {},
            "parents": [],
        },
        {
            "uid": {"type": "Manifest::ShipmentAction", "id": request.request_id},
            "attrs": {
                "orderId": state.order_id,
                "toolName": request.action,
                "owner": {
                    "__entity": {"type": "Manifest::Agent", "id": owner}
                },
                "effectClass": effect_class,
            },
            "parents": [],
        },
    ]
    return CedarAuthorizationRequest(
        request_id=request.request_id,
        principal=principal_uid,
        action=action_uid,
        resource=resource_uid,
        context=context,
        entities=entities,
        policy_version=policy_version,
        bundle_hash=bundle_hash,
    )


def _strict_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer.")
    return value


def _valid_fact_hash(order_id: str, fact: Any) -> bool:
    payload = json.dumps(
        {
            "name": fact.name,
            "order_id": order_id,
            "source_id": fact.source_id,
            "unit": fact.unit,
            "value": fact.value,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    expected = "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return expected == fact.source_hash

