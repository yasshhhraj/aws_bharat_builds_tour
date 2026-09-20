from datetime import datetime, timezone

import pytest

from apps.runtime.runtime_settings import RuntimeSettings
from apps.runtime.service import build_run_service
from packages.domain.enums import ApprovalStatus, EventType, RunStatus, WorkflowStage
from packages.domain.errors import ApprovalExpiredError


STRANDS_RECORDED = RuntimeSettings(
    runtime_mode="strands",
    model_provider="recorded",
    model_id="manifest-recorded-v1",
    max_turns=8,
    timeout_seconds=15,
)


def build_strands_service(**kwargs):
    return build_run_service(runtime_settings=STRANDS_RECORDED, **kwargs)


def test_recorded_strands_benign_journey_uses_all_four_roles():
    service = build_strands_service()

    summary = service.start_run("ORD-8842", "enforce", "benign")

    assert summary.status == RunStatus.COMPLETED
    assert summary.selected_vehicle_id == "VEH-COLD-01"
    assert summary.selected_carrier_id == "CARRIER-COLD-01"
    assert summary.confirmed_booking_id is not None
    assert summary.notification_id == "NOTIFY-ORD-8842"
    events = service.get_events(summary.trace_id)
    started = next(item for item in events if item.event_type == EventType.RUN_STARTED)
    assert started.details["runtime_mode"] == "strands"
    assert started.details["model_provider"] == "recorded"
    assert started.details["model_id"] == "manifest-recorded-v1"
    attempts = [
        item.tool_name for item in events if item.event_type == EventType.TOOL_ATTEMPTED
    ]
    assert attempts == [
        "get_order",
        "check_inventory",
        "list_available_vehicles",
        "create_dispatch_plan",
        "list_carrier_quotes",
        "select_carrier_quote",
        "prepare_freight_booking",
        "confirm_freight_booking",
        "write_tracking_outbox",
    ]


def test_recorded_strands_guide_back_and_approval_resume():
    service = build_strands_service()
    pending = service.start_run("ORD-8842", "enforce", "adversarial")

    assert pending.status == RunStatus.PENDING_APPROVAL
    assert pending.workflow_stage == WorkflowStage.AWAITING_APPROVAL
    assert pending.selected_vehicle_id == "VEH-COLD-01"
    assert pending.selected_carrier_id == "CARRIER-COLD-01"
    approval = service.get_approval(pending.pending_approval_id)
    resolved = service.resolve_approval(
        approval.approval_id,
        decision="approve",
        approver_label="DEMO-APPROVER-STRANDS",
        comment="Approve the synthetic exception.",
        expected_version=1,
        idempotency_key="strands-approval-approve-1",
    )

    assert resolved.approval.status == ApprovalStatus.APPROVED
    assert resolved.run.status == RunStatus.COMPLETED
    assert resolved.run.spend_committed_minor == 455000
    assert service.mocks.confirmed_booking_count == 1
    assert service.mocks.notification_count == 1


def test_recorded_strands_rejection_cancels_without_confirmation():
    service = build_strands_service()
    pending = service.start_run("ORD-8842", "enforce", "adversarial")
    approval = service.get_approval(pending.pending_approval_id)

    resolved = service.resolve_approval(
        approval.approval_id,
        decision="reject",
        approver_label="DEMO-APPROVER-STRANDS",
        comment="Reject the synthetic exception.",
        expected_version=1,
        idempotency_key="strands-approval-reject-1",
    )

    assert resolved.run.status == RunStatus.CANCELLED
    assert resolved.run.spend_reserved_minor == 0
    assert service.mocks.cancelled_booking_count == 1
    assert service.mocks.confirmed_booking_count == 0


def test_recorded_strands_shadow_preserves_observed_but_unenforced_choices():
    service = build_strands_service()

    summary = service.start_run("ORD-8842", "shadow", "adversarial")

    assert summary.status == RunStatus.COMPLETED
    assert summary.selected_vehicle_id == "VEH-SMALL-01"
    assert summary.selected_carrier_id == "CARRIER-CHEAP-01"
    assert summary.spend_committed_minor == 435000


def test_recorded_strands_expiry_uses_governed_cancel_path():
    service = build_strands_service(
        now_fn=lambda: datetime(2100, 1, 1, tzinfo=timezone.utc)
    )
    pending = service.start_run("ORD-8842", "enforce", "adversarial")
    approval = service.get_approval(pending.pending_approval_id)

    with pytest.raises(ApprovalExpiredError):
        service.resolve_approval(
            approval.approval_id,
            decision="approve",
            approver_label="DEMO-APPROVER-STRANDS",
            comment=None,
            expected_version=1,
            idempotency_key="strands-approval-expired-1",
        )

    assert service.get_run(pending.trace_id).status == RunStatus.CANCELLED
    assert service.mocks.cancelled_booking_count == 1


def test_turn_limit_fails_closed_before_an_effectful_stage():
    settings = RuntimeSettings(
        "strands", "recorded", "manifest-recorded-v1", max_turns=1
    )
    service = build_run_service(runtime_settings=settings)

    summary = service.start_run("ORD-8842", "enforce", "benign")

    assert summary.status == RunStatus.FAILED
    assert "limit_turns" in (summary.error or "")
    assert summary.confirmed_booking_id is None
    assert service.mocks.confirmed_booking_count == 0


@pytest.mark.parametrize(
    ("mode", "scenario", "approval"),
    (
        ("enforce", "benign", None),
        ("enforce", "adversarial", "approve"),
        ("enforce", "adversarial", "reject"),
        ("shadow", "adversarial", None),
    ),
)
def test_recorded_strands_matches_legacy_governed_outcomes(mode, scenario, approval):
    legacy = build_run_service()
    strands = build_strands_service()

    legacy_summary = _run_journey(legacy, mode, scenario, approval)
    strands_summary = _run_journey(strands, mode, scenario, approval)

    assert _functional_summary(strands_summary) == _functional_summary(legacy_summary)
    assert _decision_projection(strands, strands_summary.trace_id) == _decision_projection(
        legacy, legacy_summary.trace_id
    )
    assert strands.mocks.confirmed_booking_count == legacy.mocks.confirmed_booking_count
    assert strands.mocks.cancelled_booking_count == legacy.mocks.cancelled_booking_count
    assert strands.mocks.notification_count == legacy.mocks.notification_count


def _run_journey(service, mode, scenario, approval):
    summary = service.start_run("ORD-8842", mode, scenario)
    if approval is None:
        return summary
    return service.resolve_approval(
        summary.pending_approval_id,
        decision=approval,
        approver_label="PARITY-APPROVER",
        comment="Resolve parity journey.",
        expected_version=1,
        idempotency_key=f"parity:{mode}:{scenario}:{approval}",
    ).run


def _functional_summary(summary):
    return {
        "status": summary.status,
        "workflow_stage": summary.workflow_stage,
        "selected_vehicle_id": summary.selected_vehicle_id,
        "selected_carrier_id": summary.selected_carrier_id,
        "selected_amount_minor": summary.selected_amount_minor,
        "notification_present": summary.notification_id is not None,
        "confirmation_present": summary.confirmed_booking_id is not None,
        "spend_committed_minor": summary.spend_committed_minor,
        "spend_reserved_minor": summary.spend_reserved_minor,
        "terminal_reason": summary.terminal_reason,
    }


def _decision_projection(service, trace_id):
    return [
        (
            decision.agent,
            decision.tool_name,
            decision.policy_outcome,
            decision.applied_outcome,
            decision.enforced,
            decision.reason_code,
        )
        for decision in service.get_decisions(trace_id)
    ]
