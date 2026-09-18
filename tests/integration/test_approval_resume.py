from datetime import datetime, timezone

import pytest

from apps.runtime.service import build_run_service
from packages.domain.enums import ApprovalStatus, EventType, RunStatus, WorkflowStage
from packages.domain.errors import ApprovalExpiredError, ApprovalNotPendingError


def start_pending(service):
    run = service.start_run("ORD-8842", "enforce", "adversarial")
    assert run.status == RunStatus.PENDING_APPROVAL
    return run, service.get_approval(run.pending_approval_id)


def test_approve_resumes_same_trace_and_completes_exactly_once():
    service = build_run_service()
    run, approval = start_pending(service)

    result = service.resolve_approval(
        approval.approval_id,
        decision="approve",
        approver_label="DEMO-APPROVER-OPS-1",
        comment="Approve synthetic exception.",
        expected_version=1,
        idempotency_key="approval-integration-approve-001",
    )

    assert result.run.trace_id == run.trace_id
    assert result.approval.status == ApprovalStatus.APPROVED
    assert result.run.status == RunStatus.COMPLETED
    assert result.run.workflow_stage == WorkflowStage.COMPLETE
    assert result.run.spend_committed_minor == 455000
    assert result.run.spend_reserved_minor == 0
    assert result.run.confirmed_booking_id is not None
    assert result.run.notification_id == "NOTIFY-ORD-8842"
    assert service.mocks.confirmed_booking_count == 1
    assert service.mocks.notification_count == 1

    decisions = service.get_decisions(run.trace_id)
    assert decisions[-2].reason_code == "SPEND_EXCEPTION_APPROVED"
    events = service.get_events(run.trace_id)
    event_types = [item.event_type for item in events]
    assert event_types.index(EventType.APPROVAL_APPROVED) < event_types.index(EventType.RUN_RESUMED)
    confirm_success = next(
        index for index, item in enumerate(events)
        if item.event_type == EventType.TOOL_SUCCEEDED
        and item.tool_name == "confirm_freight_booking"
    )
    notification_attempt = next(
        index for index, item in enumerate(events)
        if item.event_type == EventType.TOOL_ATTEMPTED
        and item.tool_name == "write_tracking_outbox"
    )
    assert confirm_success < notification_attempt
    assert [item.sequence for item in events] == list(range(1, len(events) + 1))


def test_reject_cancels_and_releases_reserved_spend():
    service = build_run_service()
    run, approval = start_pending(service)

    result = service.resolve_approval(
        approval.approval_id,
        decision="reject",
        approver_label="DEMO-APPROVER-OPS-2",
        comment="Reject synthetic exception.",
        expected_version=1,
        idempotency_key="approval-integration-reject-001",
    )

    assert result.run.trace_id == run.trace_id
    assert result.approval.status == ApprovalStatus.REJECTED
    assert result.run.status == RunStatus.CANCELLED
    assert result.run.workflow_stage == WorkflowStage.CANCELLED
    assert result.run.spend_committed_minor == 365000
    assert result.run.spend_reserved_minor == 0
    assert result.run.confirmed_booking_id is None
    assert result.run.notification_id is None
    assert service.mocks.cancelled_booking_count == 1
    assert service.mocks.confirmed_booking_count == 0
    assert service.mocks.notification_count == 0


def test_same_approval_request_replays_without_second_effect():
    service = build_run_service()
    _, approval = start_pending(service)
    arguments = {
        "decision": "approve",
        "approver_label": "DEMO-APPROVER-OPS-1",
        "comment": "Approve once.",
        "expected_version": 1,
        "idempotency_key": "approval-integration-replay-001",
    }

    first = service.resolve_approval(approval.approval_id, **arguments)
    second = service.resolve_approval(approval.approval_id, **arguments)

    assert not first.idempotent_replay
    assert second.idempotent_replay
    assert service.mocks.confirmed_booking_count == 1
    assert service.mocks.notification_count == 1


def test_expired_approval_cancels_before_reporting_expiry():
    service = build_run_service(
        now_fn=lambda: datetime(2100, 1, 1, tzinfo=timezone.utc)
    )
    run, approval = start_pending(service)

    with pytest.raises(ApprovalExpiredError):
        service.resolve_approval(
            approval.approval_id,
            decision="approve",
            approver_label="DEMO-APPROVER-OPS-1",
            comment=None,
            expected_version=1,
            idempotency_key="approval-integration-expired-001",
        )

    assert service.get_approval(approval.approval_id).status == ApprovalStatus.EXPIRED
    final = service.get_run(run.trace_id)
    assert final.status == RunStatus.CANCELLED
    assert final.spend_reserved_minor == 0
    assert service.mocks.cancelled_booking_count == 1
    with pytest.raises(ApprovalExpiredError):
        service.resolve_approval(
            approval.approval_id,
            decision="approve",
            approver_label="DEMO-APPROVER-OPS-1",
            comment=None,
            expected_version=1,
            idempotency_key="approval-integration-expired-002",
        )


def test_expire_due_approvals_is_idempotent():
    service = build_run_service(
        now_fn=lambda: datetime(2100, 1, 1, tzinfo=timezone.utc)
    )
    run, approval = start_pending(service)

    first = service.expire_due_approvals()
    second = service.expire_due_approvals()

    assert [item.approval_id for item in first] == [approval.approval_id]
    assert second == []
    assert service.get_run(run.trace_id).status == RunStatus.CANCELLED
    assert service.mocks.cancelled_booking_count == 1
