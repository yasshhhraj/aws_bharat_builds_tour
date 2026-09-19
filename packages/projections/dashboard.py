"""Pure read-model builders for the Checkpoint 5 dashboard."""

from __future__ import annotations

from packages.domain.enums import DecisionOutcome, EventType, RunStatus
from packages.domain.models import (
    DashboardProjection,
    RiskSignalPoint,
    SpendPoint,
    TrajectoryState,
    WeightAttempt,
    WeightProvenanceProjection,
)


RISK_SIGNAL_METHOD = "20_per_unique_non_allow_policy_family_capped_100"


def build_dashboard_projection(state: TrajectoryState) -> DashboardProjection:
    risk_points = _build_risk_points(state)
    return DashboardProjection(
        trace_id=state.trace_id,
        risk_signal_score=risk_points[-1].total if risk_points else 0,
        risk_signal_method=RISK_SIGNAL_METHOD,
        risk_points=tuple(risk_points),
        spend_points=tuple(_build_spend_points(state)),
        weight_provenance=_build_weight_provenance(state),
    )


def _decision_sequences(state: TrajectoryState) -> dict[str, int]:
    values: dict[str, int] = {}
    for event in state.events:
        if event.event_type != EventType.POLICY_DECIDED:
            continue
        decision_id = event.details.get("decision_id")
        if isinstance(decision_id, str):
            values[decision_id] = event.sequence
    return values


def _build_risk_points(state: TrajectoryState) -> list[RiskSignalPoint]:
    sequences = _decision_sequences(state)
    seen_families: set[str] = set()
    total = 0
    points: list[RiskSignalPoint] = []
    for decision in state.decisions:
        sequence = sequences.get(decision.decision_id)
        if sequence is None:
            continue
        for policy_signal in decision.reasons:
            if policy_signal.outcome == DecisionOutcome.ALLOW:
                continue
            if policy_signal.family in seen_families:
                continue
            seen_families.add(policy_signal.family)
            previous = total
            total = min(100, total + 20)
            points.append(
                RiskSignalPoint(
                    sequence=sequence,
                    decision_id=decision.decision_id,
                    family=policy_signal.family,
                    reason_code=policy_signal.reason_code,
                    outcome=policy_signal.outcome,
                    delta=total - previous,
                    total=total,
                )
            )
    return points


def _build_spend_points(state: TrajectoryState) -> list[SpendPoint]:
    if state.mandate is None:
        return []
    ceiling = state.mandate.spend_ceiling_minor
    initial = state.scenario_config.prior_committed_minor if state.scenario_config else 0
    points = [
        SpendPoint(
            sequence=1,
            label="start",
            committed_minor=initial,
            reserved_minor=0,
            projected_minor=initial,
            ceiling_minor=ceiling,
        )
    ]
    prepare_sequences: dict[str, int] = {}
    for event in state.events:
        if event.event_type != EventType.TOOL_SUCCEEDED:
            continue
        if event.tool_name != "prepare_freight_booking":
            continue
        result = event.details.get("result", {})
        prepared_id = result.get("prepared_action_id") if isinstance(result, dict) else None
        if isinstance(prepared_id, str):
            prepare_sequences[prepared_id] = event.sequence
    prepared_items = sorted(
        state.prepared_actions.values(),
        key=lambda item: (prepare_sequences.get(item.prepared_action_id, 10**9), item.prepared_action_id),
    )
    for prepared in prepared_items:
        sequence = prepare_sequences.get(prepared.prepared_action_id)
        if sequence is None:
            continue
        points.append(
            SpendPoint(
                sequence=sequence,
                label="prepared",
                committed_minor=prepared.spend_committed_at_prepare_minor,
                reserved_minor=prepared.spend_reserved_after_minor,
                projected_minor=(
                    prepared.spend_committed_at_prepare_minor
                    + prepared.spend_reserved_after_minor
                ),
                ceiling_minor=ceiling,
            )
        )
    if state.status == RunStatus.PENDING_APPROVAL:
        label = "pending"
    elif state.status == RunStatus.CANCELLED:
        label = "cancelled"
    elif state.confirmed_booking_id:
        label = "confirmed"
    else:
        label = "current"
    final_sequence = state.events[-1].sequence if state.events else 1
    final_point = SpendPoint(
        sequence=final_sequence,
        label=label,
        committed_minor=state.spend_committed_minor,
        reserved_minor=state.spend_reserved_minor,
        projected_minor=state.spend_committed_minor + state.spend_reserved_minor,
        ceiling_minor=ceiling,
    )
    if points[-1] != final_point:
        points.append(final_point)
    return points


def _build_weight_provenance(
    state: TrajectoryState,
) -> WeightProvenanceProjection | None:
    fact = next(
        (item for item in state.facts.values() if item.name == "shipment_weight"),
        None,
    )
    if fact is None:
        return None
    decisions_by_proposal = {item.proposal_id: item for item in state.decisions}
    attempts: list[WeightAttempt] = []
    final_value: int | None = None
    for event in state.events:
        if event.tool_name != "create_dispatch_plan":
            continue
        if event.event_type == EventType.TOOL_ATTEMPTED:
            proposal_id = event.details.get("proposal_id")
            arguments = event.details.get("arguments", {})
            if not isinstance(proposal_id, str) or not isinstance(arguments, dict):
                continue
            attempted = arguments.get("weight_value")
            if isinstance(attempted, bool) or not isinstance(attempted, int):
                continue
            decision = decisions_by_proposal.get(proposal_id)
            if decision is None:
                continue
            attempts.append(
                WeightAttempt(
                    sequence=event.sequence,
                    proposal_id=proposal_id,
                    attempted_value=attempted,
                    unit=str(arguments.get("weight_unit", "")),
                    fact_id=str(arguments.get("weight_fact_id", "")),
                    policy_outcome=decision.policy_outcome,
                    reason_code=decision.reason_code,
                )
            )
        elif event.event_type == EventType.TOOL_SUCCEEDED:
            result = event.details.get("result", {})
            if isinstance(result, dict):
                value = result.get("weight_kg")
                if isinstance(value, int) and not isinstance(value, bool):
                    final_value = value
    return WeightProvenanceProjection(
        fact_id=fact.fact_id,
        authoritative_value=fact.value,
        unit=fact.unit,
        source_id=fact.source_id,
        source_hash=fact.source_hash,
        attempts=tuple(attempts),
        final_value=final_value,
    )
