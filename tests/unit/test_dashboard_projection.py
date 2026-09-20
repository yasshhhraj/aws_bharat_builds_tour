from datetime import datetime, timezone

import pytest

from apps.runtime.service import build_run_service
from packages.domain.errors import ApprovalExpiredError
from packages.projections import build_dashboard_projection


def projection_for(service, trace_id):
    return build_dashboard_projection(service.store.get_state(trace_id))


def test_benign_projection_has_zero_risk_and_exact_spend_points():
    service = build_run_service()
    run = service.start_run("ORD-8842", "enforce", "benign")

    projection = projection_for(service, run.trace_id)

    assert projection.risk_signal_score == 0
    assert projection.risk_points == ()
    assert projection.spend_points[0].label == "start"
    assert projection.spend_points[0].committed_minor == 250000
    assert projection.spend_points[-1].label == "confirmed"
    assert projection.spend_points[-1].committed_minor == 340000
    assert projection.spend_points[-1].reserved_minor == 0
    assert projection.booking_confirmation_count == 1
    assert projection.notification_count == 1
    assert projection.exact_once_status == "confirmed_once"
    assert projection.failure_code is None


def test_primary_projection_exposes_60_risk_and_weight_correction():
    service = build_run_service()
    run = service.start_run("ORD-8842", "enforce", "adversarial")

    projection = projection_for(service, run.trace_id)

    assert projection.risk_signal_score == 60
    assert [point.family for point in projection.risk_points] == [
        "provenance",
        "cold_chain",
        "spend",
    ]
    assert [point.total for point in projection.risk_points] == [20, 40, 60]
    provenance = projection.weight_provenance
    assert provenance is not None
    assert provenance.authoritative_value == 500
    assert [attempt.attempted_value for attempt in provenance.attempts] == [50, 500]
    assert [attempt.policy_outcome.value for attempt in provenance.attempts] == [
        "guide",
        "allow",
    ]
    assert provenance.final_value == 500
    assert projection.spend_points[0].committed_minor == 365000
    assert projection.spend_points[-1].label == "pending"
    assert projection.spend_points[-1].committed_minor == 365000
    assert projection.spend_points[-1].reserved_minor == 90000
    assert projection.spend_points[-1].projected_minor == 455000
    assert projection.spend_points[-1].ceiling_minor == 400000
    assert projection.booking_confirmation_count == 0
    assert projection.notification_count == 0
    assert projection.exact_once_status == "awaiting_approval"


def test_shadow_projection_uses_policy_outcomes_for_risk():
    service = build_run_service()
    run = service.start_run("ORD-8842", "shadow", "adversarial")

    projection = projection_for(service, run.trace_id)

    assert projection.risk_signal_score == 60
    assert {point.outcome.value for point in projection.risk_points} >= {
        "guide",
        "escalate",
    }


def test_approved_projection_moves_reserved_spend_to_committed():
    service = build_run_service()
    pending = service.start_run("ORD-8842", "enforce", "adversarial")
    service.resolve_approval(
        pending.pending_approval_id,
        decision="approve",
        approver_label="DEMO-APPROVER-OPS-1",
        comment=None,
        expected_version=1,
        idempotency_key="projection-approve-001",
    )

    projection = projection_for(service, pending.trace_id)

    assert projection.spend_points[-1].label == "confirmed"
    assert projection.spend_points[-1].committed_minor == 455000
    assert projection.spend_points[-1].reserved_minor == 0


def test_rejected_and_expired_projection_release_reserved_spend():
    rejected_service = build_run_service()
    rejected = rejected_service.start_run("ORD-8842", "enforce", "adversarial")
    rejected_service.resolve_approval(
        rejected.pending_approval_id,
        decision="reject",
        approver_label="DEMO-APPROVER-OPS-2",
        comment=None,
        expected_version=1,
        idempotency_key="projection-reject-001",
    )
    rejected_projection = projection_for(rejected_service, rejected.trace_id)
    assert rejected_projection.spend_points[-1].label == "cancelled"
    assert rejected_projection.spend_points[-1].committed_minor == 365000
    assert rejected_projection.spend_points[-1].reserved_minor == 0

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
            idempotency_key="projection-expire-001",
        )
    expired_projection = projection_for(expired_service, expired.trace_id)
    assert expired_projection.spend_points[-1].label == "cancelled"
    assert expired_projection.spend_points[-1].reserved_minor == 0
    assert rejected_projection.exact_once_status == "cancelled_without_confirmation"
    assert expired_projection.exact_once_status == "cancelled_without_confirmation"


def test_projection_is_read_only_for_events_and_ledger_head():
    service = build_run_service()
    run = service.start_run("ORD-8842", "enforce", "adversarial")
    before_events = service.get_events(run.trace_id)
    before_head = service.store.get_head(run.trace_id)

    projection_for(service, run.trace_id)

    assert service.get_events(run.trace_id) == before_events
    assert service.store.get_head(run.trace_id) == before_head
