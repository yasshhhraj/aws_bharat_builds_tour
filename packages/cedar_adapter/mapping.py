"""Deterministic translation of Cedar diagnostics into Manifest policy signals."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from packages.domain.enums import DecisionOutcome
from packages.domain.models import PolicyRequest, PolicySignal, TrajectoryState
from packages.governor.reasons import REASON_CODES

from .models import CedarAuthorizationResponse


FAMILY_ORDER = {
    "ownership": 0,
    "provenance": 1,
    "cold_chain": 2,
    "spend": 3,
    "separation": 4,
    "pii": 5,
    "default": 6,
}


class CedarMappingError(RuntimeError):
    pass


class CedarPolicyMetadata:
    def __init__(self, path: Path) -> None:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            policies = value["policies"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise CedarMappingError("Cedar policy metadata is invalid.") from exc
        if not isinstance(policies, dict) or not policies:
            raise CedarMappingError("Cedar policy metadata is empty.")
        self.policy_version = str(value.get("policy_version", ""))
        self.policies: dict[str, dict[str, Any]] = {}
        for policy_id, item in policies.items():
            if not isinstance(item, dict):
                raise CedarMappingError("Cedar policy metadata entry is invalid.")
            reason = str(item.get("reason_code", ""))
            if reason not in REASON_CODES:
                raise CedarMappingError("Cedar metadata uses an unknown reason code.")
            try:
                DecisionOutcome(str(item["outcome"]))
                family = str(item["family"])
                int(item["order"])
            except (KeyError, TypeError, ValueError) as exc:
                raise CedarMappingError("Cedar policy metadata entry is invalid.") from exc
            if family not in FAMILY_ORDER:
                raise CedarMappingError("Cedar policy metadata family is invalid.")
            self.policies[str(policy_id)] = item

    def map_response(
        self,
        response: CedarAuthorizationResponse,
        request: PolicyRequest,
        state: TrajectoryState,
    ) -> tuple[PolicySignal, ...]:
        if response.errors:
            raise CedarMappingError("Cedar returned authorization diagnostics.")
        if response.decision not in {"allow", "deny"}:
            raise CedarMappingError("Cedar returned an invalid decision.")
        policy_ids = list(response.determining_policy_ids)
        if response.decision == "deny" and not policy_ids:
            return (
                PolicySignal(
                    "ownership",
                    "CEDAR-IMPLICIT-DENY",
                    DecisionOutcome.BLOCK,
                    "MISSING_POLICY_CONTEXT",
                    "No Cedar permit policy matched the authorization request.",
                ),
            )
        unknown = [item for item in policy_ids if item not in self.policies]
        if unknown:
            raise CedarMappingError("Cedar returned an unknown determining policy.")
        if response.decision == "allow":
            policy_ids = [item for item in policy_ids if item != "BASE-PERMIT-REGISTERED"]
            if request.action == "confirm_freight_booking":
                mandate = state.mandate
                if mandate is None:
                    raise CedarMappingError("Shipment mandate is missing.")
                projected = state.spend_committed_minor + state.spend_reserved_minor
                approval = request.context.get("approval", {})
                policy_ids = [
                    "SPEND-009"
                    if projected > mandate.approval_threshold_minor
                    and isinstance(approval, dict)
                    and approval.get("status") == "approved"
                    else "SPEND-004"
                ]
            if not policy_ids:
                policy_ids = ["BASE-PERMIT-REGISTERED"]
        signals = [self._signal(policy_id, request, state) for policy_id in policy_ids]
        signals.sort(
            key=lambda item: (
                FAMILY_ORDER[item.family],
                int(self.policies[item.policy_id]["order"]),
                item.policy_id,
            )
        )
        return tuple(signals)

    def _signal(
        self, policy_id: str, request: PolicyRequest, state: TrajectoryState
    ) -> PolicySignal:
        item = self.policies[policy_id]
        reason_code = str(item["reason_code"])
        because = str(item["because"])
        guidance = None
        guidance_type = item.get("guidance")
        args = request.context.get("arguments", {})
        if guidance_type == "weight":
            fact = state.facts.get(str(args.get("weight_fact_id")))
            if fact is not None:
                guidance = {
                    "required_fact_id": fact.fact_id,
                    "required_value": fact.value,
                    "required_unit": fact.unit,
                }
                if reason_code == "PROVENANCE_VALUE_MISMATCH":
                    because = (
                        f"Attempted weight {args.get('weight_value')} kg differs from "
                        f"sourced weight {fact.value} kg."
                    )
                elif reason_code == "PROVENANCE_UNIT_MISMATCH":
                    because = (
                        f"Attempted unit {args.get('weight_unit')} differs from sourced "
                        f"unit {fact.unit}."
                    )
        elif guidance_type == "vehicle":
            fact = state.facts.get(str(args.get("weight_fact_id")))
            guidance = {
                "required_vehicle": {
                    "minimum_capacity_kg": fact.value if fact is not None else None,
                    "refrigerated": True,
                }
            }
        elif guidance_type == "carrier":
            guidance = {
                "required_carrier": {
                    "cold_chain_certified": True,
                    "lane_supported": True,
                }
            }
        if reason_code in {"SPEND_APPROVAL_REQUIRED", "SPEND_WITHIN_CEILING", "SPEND_EXCEPTION_APPROVED"}:
            mandate = state.mandate
            projected = state.spend_committed_minor + state.spend_reserved_minor
            if mandate is not None:
                if reason_code == "SPEND_APPROVAL_REQUIRED":
                    because = (
                        f"Projected spend INR {projected / 100:,.0f} exceeds the INR "
                        f"{mandate.approval_threshold_minor / 100:,.0f} ceiling."
                    )
                elif reason_code == "SPEND_WITHIN_CEILING":
                    because = f"Projected spend INR {projected / 100:,.0f} is within the shipment ceiling."
                else:
                    because = f"A bound approval permits projected spend INR {projected / 100:,.0f}."
        return PolicySignal(
            family=str(item["family"]),
            policy_id=policy_id,
            outcome=DecisionOutcome(str(item["outcome"])),
            reason_code=reason_code,
            because=because,
            guidance=guidance,
        )

