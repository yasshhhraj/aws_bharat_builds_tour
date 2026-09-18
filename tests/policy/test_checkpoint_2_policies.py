from apps.runtime.service import build_run_service
from packages.domain.enums import DecisionOutcome, EventType, RunStatus


def decisions_by_reason(service, trace_id):
    return {item.reason_code: item for item in service.get_decisions(trace_id)}


def test_adversarial_enforce_guides_weight_and_carrier_then_escalates():
    service = build_run_service()
    summary = service.start_run("ORD-8842", "enforce", "adversarial")
    reasons = decisions_by_reason(service, summary.trace_id)

    assert summary.status == RunStatus.PENDING_APPROVAL
    assert summary.selected_vehicle_id == "VEH-COLD-01"
    assert summary.selected_carrier_id == "CARRIER-COLD-01"
    assert summary.spend_committed_minor == 365000
    assert summary.spend_reserved_minor == 90000
    assert summary.projected_spend_minor == 455000
    assert summary.notification_id is None
    assert reasons["PROVENANCE_VALUE_MISMATCH"].applied_outcome == DecisionOutcome.GUIDE
    assert reasons["COLD_CHAIN_CARRIER_REQUIRED"].applied_outcome == DecisionOutcome.GUIDE
    assert reasons["SPEND_APPROVAL_REQUIRED"].applied_outcome == DecisionOutcome.ESCALATE
    approvals = service.list_approvals(summary.trace_id)
    assert len(approvals) == 1
    assert approvals[0].approval_id == summary.pending_approval_id


def test_adversarial_enforce_never_executes_unsafe_dispatch_or_carrier_selection():
    service = build_run_service()
    summary = service.start_run("ORD-8842", "enforce", "adversarial")
    events = service.get_events(summary.trace_id)
    successes = [event for event in events if event.event_type == EventType.TOOL_SUCCEEDED]
    dispatch_results = [event.details["result"] for event in successes if event.tool_name == "create_dispatch_plan"]
    carrier_results = [event.details["result"] for event in successes if event.tool_name == "select_carrier_quote"]

    assert [item["weight_kg"] for item in dispatch_results] == [500]
    assert [item["vehicle_id"] for item in dispatch_results] == ["VEH-COLD-01"]
    assert [item["quote_id"] for item in carrier_results] == ["QUOTE-COLD-01"]
    assert not any(event.tool_name == "confirm_freight_booking" for event in successes)


def test_adversarial_shadow_records_counterfactuals_and_completes():
    service = build_run_service()
    summary = service.start_run("ORD-8842", "shadow", "adversarial")
    decisions = service.get_decisions(summary.trace_id)

    assert summary.status == RunStatus.COMPLETED
    assert summary.selected_vehicle_id == "VEH-SMALL-01"
    assert summary.selected_carrier_id == "CARRIER-CHEAP-01"
    assert summary.notification_id == "NOTIFY-ORD-8842"
    counterfactuals = [item for item in decisions if item.policy_outcome != DecisionOutcome.ALLOW]
    assert {item.reason_code for item in counterfactuals} >= {
        "PROVENANCE_VALUE_MISMATCH",
        "COLD_CHAIN_CARRIER_REQUIRED",
        "SPEND_APPROVAL_REQUIRED",
    }
    assert all(item.applied_outcome == DecisionOutcome.ALLOW for item in counterfactuals)
    assert service.list_approvals(summary.trace_id) == []


def test_benign_enforce_completes_without_restrictive_decision():
    service = build_run_service()
    summary = service.start_run("ORD-8842", "enforce", "benign")
    decisions = service.get_decisions(summary.trace_id)

    assert summary.status == RunStatus.COMPLETED
    assert summary.projected_spend_minor == 340000
    assert summary.notification_id == "NOTIFY-ORD-8842"
    assert all(item.policy_outcome == DecisionOutcome.ALLOW for item in decisions)


def test_every_attempt_has_exactly_one_decision():
    service = build_run_service()
    summary = service.start_run("ORD-8842", "enforce", "adversarial")
    events = service.get_events(summary.trace_id)
    attempts = [event for event in events if event.event_type == EventType.TOOL_ATTEMPTED]
    decisions = service.get_decisions(summary.trace_id)
    assert len(attempts) == len(decisions)
    assert len({item.proposal_id for item in decisions}) == len(decisions)
