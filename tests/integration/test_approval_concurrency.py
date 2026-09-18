from concurrent.futures import ThreadPoolExecutor

from apps.runtime.service import build_run_service
from packages.domain.errors import ApprovalNotPendingError


def test_concurrent_identical_approvals_create_one_effect():
    service = build_run_service()
    run = service.start_run("ORD-8842", "enforce", "adversarial")
    approval_id = run.pending_approval_id
    arguments = {
        "decision": "approve",
        "approver_label": "DEMO-APPROVER-OPS-1",
        "comment": "Concurrent replay.",
        "expected_version": 1,
        "idempotency_key": "approval-concurrent-same-001",
    }

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda _index: service.resolve_approval(approval_id, **arguments),
                range(2),
            )
        )

    assert sorted(item.idempotent_replay for item in results) == [False, True]
    assert service.mocks.confirmed_booking_count == 1
    assert service.mocks.notification_count == 1
    events = service.get_events(run.trace_id)
    assert [item.sequence for item in events] == list(range(1, len(events) + 1))


def test_concurrent_approve_and_reject_have_one_winner():
    service = build_run_service()
    run = service.start_run("ORD-8842", "enforce", "adversarial")
    approval_id = run.pending_approval_id

    def decide(decision):
        try:
            return service.resolve_approval(
                approval_id,
                decision=decision,
                approver_label="DEMO-APPROVER-OPS-1",
                comment="Race test.",
                expected_version=1,
                idempotency_key=f"approval-race-{decision}-001",
            )
        except ApprovalNotPendingError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(decide, ("approve", "reject")))

    assert sum(not isinstance(item, Exception) for item in results) == 1
    assert service.mocks.confirmed_booking_count + service.mocks.cancelled_booking_count == 1
    assert service.get_run(run.trace_id).spend_reserved_minor == 0
    events = service.get_events(run.trace_id)
    assert [item.sequence for item in events] == list(range(1, len(events) + 1))
