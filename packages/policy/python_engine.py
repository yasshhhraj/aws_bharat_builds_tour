"""Readable executable specification for Manifest's six policy families."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from packages.domain.enums import ApprovalStatus, CommitmentStatus, DecisionOutcome
from packages.domain.models import PolicyRequest, PolicySignal, PreparedAction, TrajectoryState


def signal(
    family: str,
    policy_id: str,
    outcome: DecisionOutcome,
    reason_code: str,
    because: str,
    guidance: dict[str, Any] | None = None,
) -> PolicySignal:
    return PolicySignal(family, policy_id, outcome, reason_code, because, guidance)


class PythonReferencePolicyEngine:
    """Six deterministic evaluators; no model output participates in decisions."""

    name = "python_reference"
    policy_version = "demo-v1"
    bundle_hash = None

    def evaluate(
        self, request: PolicyRequest, state: TrajectoryState
    ) -> tuple[PolicySignal, ...]:
        evaluators = (
            self._ownership_and_mandate,
            self._provenance,
            self._cold_chain,
            self._commitment_budget,
            self._separation_of_duties,
            self._pii_boundary,
        )
        signals: list[PolicySignal] = []
        for evaluator in evaluators:
            signals.extend(evaluator(request, state))
        return tuple(signals)

    def validate_startup(self) -> None:
        if not self.policy_version or not self.name:
            raise ValueError("Policy engine identity is incomplete.")

    def describe(self) -> dict[str, object]:
        return {
            "policy_engine": self.name,
            "policy_version": self.policy_version,
            "policy_engine_ready": True,
            "policy_bundle_hash": None,
            "policy_schema_hash": None,
            "cedar_runtime_version": None,
            "policy_fallback_active": True,
        }

    def _ownership_and_mandate(
        self, request: PolicyRequest, state: TrajectoryState
    ) -> list[PolicySignal]:
        context = request.context
        mandate = state.mandate
        if mandate is None:
            return [signal("ownership", "OWN-000", DecisionOutcome.BLOCK, "MISSING_POLICY_CONTEXT", "The shipment mandate is missing.")]
        if state.policy_version != mandate.policy_version or state.policy_version != self.policy_version:
            return [signal("ownership", "OWN-001", DecisionOutcome.BLOCK, "MISSING_POLICY_CONTEXT", "The policy version does not match the trace mandate.")]
        owner = context.get("tool_owner")
        if owner is None or owner != request.principal.value:
            return [signal("ownership", "OWN-002", DecisionOutcome.BLOCK, "TOOL_OWNER_MISMATCH", f"Agent {request.principal.value} does not own {request.action}.")]
        effect = context.get("effect_class")
        if effect not in {item.value for item in mandate.allowed_effect_classes}:
            return [signal("ownership", "OWN-003", DecisionOutcome.BLOCK, "EFFECT_NOT_ALLOWED_BY_MANDATE", f"Effect class {effect or 'missing'} is not allowed by the shipment mandate.")]
        if request.action in {"confirm_freight_booking", "cancel_freight_booking"}:
            prepared_id = context.get("arguments", {}).get("prepared_action_id")
            if not prepared_id or prepared_id not in state.prepared_actions:
                return [signal("ownership", "OWN-004", DecisionOutcome.BLOCK, "PREPARED_ACTION_REQUIRED", "A matching prepared action is required before confirmation.")]
        return []

    def _provenance(self, request: PolicyRequest, state: TrajectoryState) -> list[PolicySignal]:
        if request.action != "create_dispatch_plan":
            return []
        args = request.context.get("arguments", {})
        fact_id = args.get("weight_fact_id")
        if not fact_id or fact_id not in state.facts:
            return [signal("provenance", "PROV-001", DecisionOutcome.BLOCK, "PROVENANCE_REFERENCE_MISSING", "The dispatch weight has no trace-scoped source fact.")]
        fact = state.facts[fact_id]
        if fact.name != "shipment_weight" or not self._valid_fact_hash(state.order_id, fact):
            return [signal("provenance", "PROV-002", DecisionOutcome.BLOCK, "PROVENANCE_REFERENCE_MISSING", "The referenced weight fact is invalid or corrupted.")]
        if args.get("weight_unit") != fact.unit:
            return [signal("provenance", "PROV-003", DecisionOutcome.GUIDE, "PROVENANCE_UNIT_MISMATCH", f"Attempted unit {args.get('weight_unit')} differs from sourced unit {fact.unit}.", {"required_fact_id": fact.fact_id, "required_value": fact.value, "required_unit": fact.unit})]
        if args.get("weight_value") != fact.value:
            return [signal("provenance", "PROV-004", DecisionOutcome.GUIDE, "PROVENANCE_VALUE_MISMATCH", f"Attempted weight {args.get('weight_value')} kg differs from sourced weight {fact.value} kg.", {"required_fact_id": fact.fact_id, "required_value": fact.value, "required_unit": fact.unit})]
        return []

    def _cold_chain(self, request: PolicyRequest, state: TrajectoryState) -> list[PolicySignal]:
        if state.mandate is None or state.mandate.cargo_class != "perishable":
            return []
        resource = request.context.get("resource", {})
        if request.action == "create_dispatch_plan":
            if not resource:
                return [signal("cold_chain", "COLD-001", DecisionOutcome.BLOCK, "MISSING_POLICY_CONTEXT", "Vehicle safety metadata is missing.")]
            fact_id = request.context.get("arguments", {}).get("weight_fact_id")
            fact = state.facts.get(fact_id)
            required_weight = fact.value if fact else None
            if not resource.get("available") or not resource.get("refrigerated") or required_weight is None or resource.get("capacity_kg", -1) < required_weight:
                return [signal("cold_chain", "COLD-002", DecisionOutcome.GUIDE, "COLD_CHAIN_VEHICLE_REQUIRED", "Perishable cargo requires an available refrigerated vehicle with sufficient capacity.", {"required_vehicle": {"minimum_capacity_kg": required_weight, "refrigerated": True}})]
        if request.action in {"select_carrier_quote", "prepare_freight_booking"}:
            if not resource:
                return [signal("cold_chain", "COLD-003", DecisionOutcome.BLOCK, "MISSING_POLICY_CONTEXT", "Carrier certification metadata is missing.")]
            if not resource.get("cold_chain_certified") or not resource.get("lane_supported"):
                return [signal("cold_chain", "COLD-004", DecisionOutcome.GUIDE, "COLD_CHAIN_CARRIER_REQUIRED", "Perishable cargo requires a lane-supported cold-chain carrier.", {"required_carrier": {"cold_chain_certified": True, "lane_supported": True}})]
        return []

    def _commitment_budget(self, request: PolicyRequest, state: TrajectoryState) -> list[PolicySignal]:
        if request.action != "confirm_freight_booking":
            return []
        args = request.context.get("arguments", {})
        prepared = state.prepared_actions.get(args.get("prepared_action_id"))
        if prepared is None or state.mandate is None:
            return []
        values = (state.spend_committed_minor, state.spend_reserved_minor, prepared.amount_minor)
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values):
            return [signal("spend", "SPEND-001", DecisionOutcome.BLOCK, "MISSING_POLICY_CONTEXT", "Spend values must be non-negative integer minor units.")]
        if prepared.currency != state.mandate.currency:
            return [signal("spend", "SPEND-002", DecisionOutcome.BLOCK, "MISSING_POLICY_CONTEXT", "Prepared-action currency does not match the mandate.")]
        # The prepared action is already represented in reserved spend, so do not add it twice.
        projected = state.spend_committed_minor + state.spend_reserved_minor
        if projected > state.mandate.approval_threshold_minor:
            approval = request.context.get("approval", {})
            approval_status = approval.get("status")
            if approval_status == ApprovalStatus.APPROVED.value:
                if approval.get("is_expired"):
                    return [signal("spend", "SPEND-005", DecisionOutcome.BLOCK, "APPROVAL_EXPIRED", "The approval expired before confirmation.")]
                if approval.get("prepared_action_id") != prepared.prepared_action_id or approval.get("action_hash") != prepared.action_hash:
                    return [signal("spend", "SPEND-006", DecisionOutcome.BLOCK, "APPROVAL_ACTION_MISMATCH", "The approval does not match the prepared action.")]
                if approval.get("state_hash") != prepared.state_hash:
                    return [signal("spend", "SPEND-007", DecisionOutcome.BLOCK, "APPROVAL_STATE_MISMATCH", "The approval does not match the prepared trajectory state.")]
                if approval.get("policy_version") != state.policy_version:
                    return [signal("spend", "SPEND-008", DecisionOutcome.BLOCK, "APPROVAL_POLICY_MISMATCH", "The approval uses a different policy version.")]
                return [signal("spend", "SPEND-009", DecisionOutcome.ALLOW, "SPEND_EXCEPTION_APPROVED", f"A bound approval permits projected spend INR {projected / 100:,.0f}.")]
            if approval_status == ApprovalStatus.EXPIRED.value:
                return [signal("spend", "SPEND-010", DecisionOutcome.BLOCK, "APPROVAL_EXPIRED", "The approval expired before confirmation.")]
            if approval_status == ApprovalStatus.REJECTED.value:
                return [signal("spend", "SPEND-011", DecisionOutcome.BLOCK, "APPROVAL_REJECTED", "The prepared commitment was rejected.")]
            return [signal("spend", "SPEND-003", DecisionOutcome.ESCALATE, "SPEND_APPROVAL_REQUIRED", f"Projected spend INR {projected / 100:,.0f} exceeds the INR {state.mandate.approval_threshold_minor / 100:,.0f} ceiling.")]
        return [signal("spend", "SPEND-004", DecisionOutcome.ALLOW, "SPEND_WITHIN_CEILING", f"Projected spend INR {projected / 100:,.0f} is within the shipment ceiling.")]

    def _separation_of_duties(self, request: PolicyRequest, state: TrajectoryState) -> list[PolicySignal]:
        if request.action in {"select_carrier_quote", "prepare_freight_booking"}:
            quote_issuer = request.context.get("resource", {}).get("quote_issuer")
            if quote_issuer == request.principal.value:
                return [signal("separation", "SOD-000", DecisionOutcome.BLOCK, "SEPARATION_OF_DUTIES_VIOLATION", "The actor selecting a quote cannot also be its issuer.")]
        if request.action == "cancel_freight_booking":
            args = request.context.get("arguments", {})
            prepared = state.prepared_actions.get(args.get("prepared_action_id"))
            if prepared is None:
                return []
            if args.get("action_hash") != prepared.action_hash:
                return [signal("separation", "SOD-004", DecisionOutcome.BLOCK, "PREPARED_ACTION_MISMATCH", "The cancellation does not match the prepared action.")]
            if prepared.status == CommitmentStatus.CONFIRMED:
                return [signal("separation", "SOD-005", DecisionOutcome.BLOCK, "PREPARED_ACTION_MISMATCH", "A confirmed action cannot be cancelled.")]
            if prepared.status == CommitmentStatus.CANCELLED:
                return [signal("separation", "SOD-006", DecisionOutcome.ALLOW, "CANCELLATION_ALREADY_APPLIED", "The prepared action is already cancelled.")]
            return [signal("separation", "SOD-007", DecisionOutcome.ALLOW, "CANCELLATION_ALLOWED", "The pending prepared action may be cancelled.")]
        if request.action != "confirm_freight_booking":
            return []
        args = request.context.get("arguments", {})
        prepared: PreparedAction | None = state.prepared_actions.get(args.get("prepared_action_id"))
        if prepared is None:
            return []
        if prepared.status in {CommitmentStatus.PENDING_APPROVAL, CommitmentStatus.CONFIRMED}:
            return [signal("separation", "SOD-001", DecisionOutcome.BLOCK, "PREPARED_ACTION_MISMATCH", "The prepared action is not confirmable in its current state.")]
        if args.get("action_hash") != prepared.action_hash:
            return [signal("separation", "SOD-002", DecisionOutcome.BLOCK, "PREPARED_ACTION_MISMATCH", "The confirmation does not match the prepared action.")]
        if state.approved_by and state.approved_by == prepared.prepared_by.value:
            return [signal("separation", "SOD-003", DecisionOutcome.BLOCK, "SEPARATION_OF_DUTIES_VIOLATION", "The preparer cannot approve the same commitment.")]
        approval = request.context.get("approval", {})
        if prepared.status == CommitmentStatus.APPROVED:
            if approval.get("approver_label") == prepared.prepared_by.value:
                return [signal("separation", "SOD-008", DecisionOutcome.BLOCK, "APPROVER_CONFLICT", "The action preparer cannot approve the same commitment.")]
        return []

    def _pii_boundary(self, request: PolicyRequest, state: TrajectoryState) -> list[PolicySignal]:
        if request.action != "write_tracking_outbox":
            return []
        args = request.context.get("arguments", {})
        forbidden = {"phone", "email", "address", "name", "payment", "message"}
        if forbidden.intersection(args):
            return [signal("pii", "PII-001", DecisionOutcome.BLOCK, "PII_FIELD_NOT_ALLOWED", "Raw contact or free-form message fields are not allowed at the disclosure boundary.")]
        if args.get("template_id") != "TRACKING_UPDATE_V1":
            return [signal("pii", "PII-002", DecisionOutcome.BLOCK, "DISCLOSURE_TEMPLATE_NOT_ALLOWED", "The notification template is not allowlisted.")]
        if not str(args.get("recipient_ref", "")).startswith("DEMO-RECIPIENT-"):
            return [signal("pii", "PII-003", DecisionOutcome.BLOCK, "PII_FIELD_NOT_ALLOWED", "Only synthetic recipient references are allowed.")]
        variables = args.get("template_variables")
        if not isinstance(variables, dict) or not set(variables).issubset({"order_id", "carrier_id"}):
            return [signal("pii", "PII-004", DecisionOutcome.BLOCK, "PII_FIELD_NOT_ALLOWED", "Notification variables contain a field outside the allowlist.")]
        return []

    @staticmethod
    def _valid_fact_hash(order_id: str, fact: Any) -> bool:
        payload = json.dumps(
            {"name": fact.name, "order_id": order_id, "source_id": fact.source_id, "unit": fact.unit, "value": fact.value},
            sort_keys=True,
            separators=(",", ":"),
        )
        expected = "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return expected == fact.source_hash
