from datetime import datetime, timezone

import pytest

from apps.runtime.service import build_run_service
from packages.domain.errors import ApprovalExpiredError


def test_all_completed_checkpoint_2_journeys_have_valid_chains():
    for mode, scenario in (
        ("enforce", "benign"),
        ("shadow", "adversarial"),
    ):
        service = build_run_service()
        run = service.start_run("ORD-8842", mode, scenario)
        result = service.verify_trace(run.trace_id)

        assert result.valid is True
        assert result.checked_event_count == run.event_count
        assert result.stored_head_sequence == run.event_count
        assert result.stored_head_hash == result.computed_head_hash


def test_approval_resume_extends_the_original_valid_chain():
    service = build_run_service()
    pending = service.start_run("ORD-8842", "enforce", "adversarial")
    approval = service.get_approval(pending.pending_approval_id)
    pending_events = service.get_events(pending.trace_id)
    pending_head = service.store.get_head(pending.trace_id)

    assert service.verify_trace(pending.trace_id).valid is True

    resolved = service.resolve_approval(
        approval.approval_id,
        decision="approve",
        approver_label="DEMO-APPROVER-OPS-1",
        comment="Approve the synthetic exception.",
        expected_version=1,
        idempotency_key="checkpoint-4-approval-resume",
    )

    completed_events = service.get_events(pending.trace_id)
    completed_head = service.store.get_head(pending.trace_id)
    verification = service.verify_trace(pending.trace_id)

    assert resolved.run.trace_id == pending.trace_id
    assert verification.valid is True
    assert completed_head.sequence > pending_head.sequence
    assert completed_events[pending_head.sequence].previous_hash == pending_head.event_hash
    assert [item.event_id for item in completed_events[: pending_head.sequence]] == [
        item.event_id for item in pending_events
    ]
    assert [item.event_hash for item in completed_events[: pending_head.sequence]] == [
        item.event_hash for item in pending_events
    ]


def test_rejected_and_expired_runs_remain_verifiable():
    rejected_service = build_run_service()
    rejected = rejected_service.start_run("ORD-8842", "enforce", "adversarial")
    rejected_service.resolve_approval(
        rejected.pending_approval_id,
        decision="reject",
        approver_label="DEMO-APPROVER-OPS-2",
        comment=None,
        expected_version=1,
        idempotency_key="checkpoint-4-reject",
    )
    assert rejected_service.verify_trace(rejected.trace_id).valid is True

    expired_service = build_run_service(
        now_fn=lambda: datetime(2100, 1, 1, tzinfo=timezone.utc)
    )
    expired = expired_service.start_run("ORD-8842", "enforce", "adversarial")
    with pytest.raises(ApprovalExpiredError):
        expired_service.resolve_approval(
            expired.pending_approval_id,
            decision="approve",
            approver_label="DEMO-APPROVER-OPS-1",
            comment=None,
            expected_version=1,
            idempotency_key="checkpoint-4-expire",
        )
    assert expired_service.verify_trace(expired.trace_id).valid is True


def test_idempotent_approval_replay_does_not_extend_chain_twice():
    service = build_run_service()
    pending = service.start_run("ORD-8842", "enforce", "adversarial")
    arguments = {
        "decision": "approve",
        "approver_label": "DEMO-APPROVER-OPS-1",
        "comment": None,
        "expected_version": 1,
        "idempotency_key": "checkpoint-4-approval-replay",
    }

    first = service.resolve_approval(pending.pending_approval_id, **arguments)
    first_head = service.store.get_head(pending.trace_id)
    second = service.resolve_approval(pending.pending_approval_id, **arguments)
    second_head = service.store.get_head(pending.trace_id)

    assert first.idempotent_replay is False
    assert second.idempotent_replay is True
    assert first_head == second_head
    assert service.verify_trace(pending.trace_id).valid is True
    assert service.mocks.confirmed_booking_count == 1
    assert service.mocks.notification_count == 1
