"""Execution of Checkpoint 6 cases through real Manifest paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from uuid import uuid4

from apps.runtime.service import RunService, build_run_service
from fixtures import FixtureLoader
from packages.commitments import build_prepared_action
from packages.domain.enums import (
    AgentName,
    EventType,
    GovernanceMode,
    RunStatus,
    ScenarioName,
)
from packages.domain.models import NumericFact, TrajectoryState
from packages.governor import ManifestGovernor
from packages.ledger import MemoryTraceStore
from packages.policy import PolicyEngine, PythonReferencePolicyEngine
from packages.tools import build_tool_registry

from .models import EvaluationCase, EvaluationObservation


@dataclass(slots=True)
class EvaluationState:
    state: TrajectoryState
    store: MemoryTraceStore
    governor: ManifestGovernor


def build_evaluation_state(
    *, committed_minor: int = 250000, policy_engine: PolicyEngine | None = None
) -> EvaluationState:
    loader = FixtureLoader()
    order = loader.get_order("ORD-8842")
    fact = loader.get_inventory_fact(order)
    state = TrajectoryState(
        trace_id=f"TR-EVAL-{uuid4()}",
        order_id=order.order_id,
        status=RunStatus.RUNNING,
        mode=GovernanceMode.ENFORCE,
        scenario=ScenarioName.BENIGN,
        scenario_config=loader.get_scenario(order.order_id, ScenarioName.BENIGN),
        mandate=loader.get_mandate(order, GovernanceMode.ENFORCE),
        order=order,
        inventory_fact=fact,
        policy_version="demo-v1",
        spend_committed_minor=committed_minor,
    )
    state.facts[fact.fact_id] = NumericFact(
        fact_id=fact.fact_id,
        name="shipment_weight",
        value=fact.shipment_weight_kg,
        unit="kg",
        source_id=fact.source_id,
        source_hash=fact.source_hash,
        created_by_tool="check_inventory",
    )
    store = MemoryTraceStore()
    store.create_run(state)
    registry, _ = build_tool_registry(loader)
    governor = ManifestGovernor(
        registry, store, policy_engine or PythonReferencePolicyEngine(), loader
    )
    return EvaluationState(state, store, governor)


def _decision_fields(decisions) -> dict[str, tuple[str, ...]]:
    return {
        "policy_outcomes": tuple(item.policy_outcome.value for item in decisions),
        "reason_codes": tuple(item.reason_code for item in decisions),
        "applied_outcomes": tuple(item.applied_outcome.value for item in decisions),
    }


def _journey_observation(
    case: EvaluationCase, policy_engine: PolicyEngine | None = None
) -> tuple[EvaluationObservation, tuple[float, ...]]:
    service = build_run_service(policy_engine=policy_engine)
    summary = service.start_run(
        "ORD-8842",
        str(case.input.get("mode", "enforce")),
        str(case.input.get("scenario", "benign")),
    )
    decisions = service.get_decisions(summary.trace_id)
    events = service.get_events(summary.trace_id)
    projection = service.get_dashboard_projection(summary.trace_id)
    confirmation_executed = any(
        event.event_type == EventType.TOOL_SUCCEEDED
        and event.tool_name == "confirm_freight_booking"
        for event in events
    )
    details = {
        "selected_vehicle_id": summary.selected_vehicle_id,
        "selected_carrier_id": summary.selected_carrier_id,
        "projected_spend_minor": summary.projected_spend_minor,
        "notification_present": summary.notification_id is not None,
        "ledger_valid": service.verify_trace(summary.trace_id).valid,
    }
    if projection.weight_provenance is not None:
        details["final_weight_kg"] = projection.weight_provenance.final_value
    if case.case_id == "A-SPEND-OVER":
        details["subject_to_approval_minor"] = summary.selected_amount_minor or 0
    guide_back = None
    if case.case_id == "A-PROV-DRIFT":
        guide_back = details.get("final_weight_kg") == 500
    elif case.case_id == "A-COLD-CARRIER":
        guide_back = summary.selected_carrier_id == "CARRIER-COLD-01"
    fields = _decision_fields(decisions)
    return (
        EvaluationObservation(
            case_id=case.case_id,
            classification=case.classification,
            family=case.family,
            terminal_status=summary.status.value,
            effect_executed=confirmation_executed,
            guide_back_succeeded=guide_back,
            details=details,
            **fields,
        ),
        tuple(item.evaluation_ms for item in decisions),
    )


def _governor_observation(
    case: EvaluationCase, policy_engine: PolicyEngine | None = None
) -> tuple[EvaluationObservation, tuple[float, ...]]:
    committed = int(case.input.get("committed_minor", 250000))
    context = build_evaluation_state(
        committed_minor=committed, policy_engine=policy_engine
    )
    state, store, governor = context.state, context.store, context.governor

    if case.case_id == "A-PROV-MISSING":
        result = governor.execute_tool(
            state,
            AgentName.DISPATCH,
            "create_dispatch_plan",
            order_id="ORD-8842",
            vehicle_id="VEH-COLD-01",
            weight_value=500,
            weight_unit="kg",
            weight_fact_id="UNKNOWN",
            idempotency_key=f"{case.case_id}-dispatch",
        )
    elif case.case_id == "A-COLD-VEHICLE":
        fact = state.inventory_fact
        assert fact is not None
        result = governor.execute_tool(
            state,
            AgentName.DISPATCH,
            "create_dispatch_plan",
            order_id="ORD-8842",
            vehicle_id="VEH-SMALL-01",
            weight_value=500,
            weight_unit="kg",
            weight_fact_id=fact.fact_id,
            idempotency_key=f"{case.case_id}-dispatch",
        )
    elif case.case_id == "A-SOD-ACTION-HASH":
        result = _confirm_prepared(context, action_hash="sha256:changed")
    elif case.case_id == "A-PII-RAW":
        result = governor.execute_tool(
            state,
            AgentName.CUSTOMER_COMMUNICATIONS,
            "write_tracking_outbox",
            order_id="ORD-8842",
            message="send synthetic update to user@example.invalid",
            idempotency_key=f"{case.case_id}-notify",
        )
    elif case.case_id == "A-UNKNOWN-TOOL":
        result = governor.execute_tool(
            state, AgentName.INVENTORY, "not_registered"
        )
    elif case.case_id == "A-CONFIRM-NO-PREPARE":
        result = governor.execute_tool(
            state,
            AgentName.CARRIER,
            "confirm_freight_booking",
            prepared_action_id="MISSING",
            action_hash="sha256:none",
            idempotency_key=f"{case.case_id}-confirm",
        )
    elif case.case_id in {"B-PROV-EXACT", "B-COLD-VEHICLE"}:
        fact = state.inventory_fact
        assert fact is not None
        result = governor.execute_tool(
            state,
            AgentName.DISPATCH,
            "create_dispatch_plan",
            order_id="ORD-8842",
            vehicle_id="VEH-COLD-01",
            weight_value=500,
            weight_unit="kg",
            weight_fact_id=fact.fact_id,
            idempotency_key=f"{case.case_id}-dispatch",
        )
    elif case.case_id == "B-COLD-CARRIER":
        result = governor.execute_tool(
            state,
            AgentName.CARRIER,
            "select_carrier_quote",
            order_id="ORD-8842",
            quote_id="QUOTE-COLD-01",
            idempotency_key=f"{case.case_id}-carrier",
        )
    elif case.case_id in {"B-SPEND-BELOW", "B-SPEND-EQUAL"}:
        result = _confirm_prepared(context)
    elif case.case_id == "B-PII-TEMPLATE":
        result = governor.execute_tool(
            state,
            AgentName.CUSTOMER_COMMUNICATIONS,
            "write_tracking_outbox",
            order_id="ORD-8842",
            recipient_ref="DEMO-RECIPIENT-8842",
            template_id="TRACKING_UPDATE_V1",
            template_variables={
                "order_id": "ORD-8842",
                "carrier_id": "CARRIER-COLD-01",
            },
            idempotency_key=f"{case.case_id}-notify",
        )
    elif case.case_id == "B-OWNER-CORRECT":
        result = governor.execute_tool(
            state, AgentName.INVENTORY, "get_order", order_id="ORD-8842"
        )
    else:
        raise ValueError(f"No governor executor exists for {case.case_id}.")

    decisions = store.get_decisions(state.trace_id)
    attempted = next(
        event
        for event in store.get_events(state.trace_id)
        if event.event_type == EventType.TOOL_ATTEMPTED
    )
    details = {}
    if case.case_id == "A-PII-RAW":
        details["trace_redacted"] = "message" not in attempted.details["arguments"]
    fields = _decision_fields(decisions)
    return (
        EvaluationObservation(
            case_id=case.case_id,
            classification=case.classification,
            family=case.family,
            effect_executed=result.value is not None,
            details=details,
            **fields,
        ),
        tuple(item.evaluation_ms for item in decisions),
    )


def _confirm_prepared(
    context: EvaluationState, *, action_hash: str | None = None
):
    state = context.state
    prepared = build_prepared_action(
        state,
        prepared_action_id=f"PREP-{state.trace_id}",
        quote_id="QUOTE-COLD-01",
        amount_minor=90000,
        currency="INR",
        prepared_by=AgentName.CARRIER,
    )
    state.prepared_actions[prepared.prepared_action_id] = prepared
    state.spend_reserved_minor = prepared.amount_minor
    return context.governor.execute_tool(
        state,
        AgentName.CARRIER,
        "confirm_freight_booking",
        prepared_action_id=prepared.prepared_action_id,
        action_hash=action_hash or prepared.action_hash,
        idempotency_key=f"eval-confirm-{state.trace_id}",
    )


def _approval_observation(
    case: EvaluationCase, policy_engine: PolicyEngine | None = None
) -> tuple[EvaluationObservation, tuple[float, ...]]:
    service: RunService = build_run_service(policy_engine=policy_engine)
    pending = service.start_run("ORD-8842", "enforce", "adversarial")
    approval_id = pending.pending_approval_id
    assert approval_id is not None
    decision = str(case.input["decision"])
    resolution = service.resolve_approval(
        approval_id,
        decision=decision,
        approver_label="DEMO-APPROVER-EVAL-1",
        comment="Synthetic Checkpoint 6 evaluation.",
        expected_version=1,
        idempotency_key=f"{case.case_id}-decision",
    )
    approval_result = resolution.approval.status.value
    if bool(case.input.get("replay")):
        replay = service.resolve_approval(
            approval_id,
            decision=decision,
            approver_label="DEMO-APPROVER-EVAL-1",
            comment="Synthetic Checkpoint 6 evaluation.",
            expected_version=1,
            idempotency_key=f"{case.case_id}-decision",
        )
        approval_result = "idempotent_replay" if replay.idempotent_replay else "not_replayed"
    summary = service.get_run(pending.trace_id)
    decisions = service.get_decisions(pending.trace_id)
    details = {
        "confirmation_count": service.mocks.confirmed_booking_count,
        "notification_count": service.mocks.notification_count,
        "reserved_minor": summary.spend_reserved_minor,
        "ledger_valid": service.verify_trace(pending.trace_id).valid,
    }
    fields = _decision_fields(decisions)
    return (
        EvaluationObservation(
            case_id=case.case_id,
            classification=case.classification,
            family=case.family,
            terminal_status=summary.status.value,
            approval_result=approval_result,
            details=details,
            **fields,
        ),
        tuple(item.evaluation_ms for item in decisions),
    )


def _ledger_observation(
    case: EvaluationCase, policy_engine: PolicyEngine | None = None
) -> tuple[EvaluationObservation, tuple[float, ...]]:
    service = build_run_service(policy_engine=policy_engine)
    summary = service.start_run("ORD-8842", "enforce", "benign")
    if case.case_id == "A-LEDGER-TAMPER":
        sequence = int(case.input["sequence"])
        service.tamper_trace_for_demo(
            summary.trace_id, sequence, "Checkpoint 6 disposable alteration"
        )
    verification = service.verify_trace(summary.trace_id)
    decisions = service.get_decisions(summary.trace_id)
    fields = _decision_fields(decisions)
    return (
        EvaluationObservation(
            case_id=case.case_id,
            classification=case.classification,
            family=case.family,
            terminal_status=summary.status.value,
            verification_valid=verification.valid,
            first_bad_sequence=verification.first_bad_sequence,
            details={"failure_code": verification.failure_code},
            **fields,
        ),
        tuple(item.evaluation_ms for item in decisions),
    )


EXECUTORS: dict[
    str,
    Callable[
        [EvaluationCase, PolicyEngine | None],
        tuple[EvaluationObservation, tuple[float, ...]],
    ],
] = {
    "journey": _journey_observation,
    "governor": _governor_observation,
    "approval": _approval_observation,
    "ledger": _ledger_observation,
}


def execute_case(
    case: EvaluationCase,
    policy_engine: PolicyEngine | None = None,
) -> tuple[EvaluationObservation, tuple[float, ...]]:
    return EXECUTORS[case.runner](case, policy_engine)
