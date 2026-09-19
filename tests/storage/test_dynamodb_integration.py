from concurrent.futures import ThreadPoolExecutor
import os
from uuid import uuid4

import pytest

from apps.runtime.service import build_run_service
from packages.approvals import ApprovalCommand
from packages.domain.enums import ApprovalDecision
from packages.domain.enums import RunStatus
from packages.domain.enums import EventType
from packages.domain.errors import (
    ApprovalPersistenceConflictError,
    TraceNotFoundError,
    TraceRevisionConflictError,
)
from packages.storage.dynamodb import DynamoDBTraceStore
from packages.storage.models import TraceTransition
from packages.storage.keyspace import opaque_key_hash


pytestmark = pytest.mark.skipif(
    os.getenv("MANIFEST_DYNAMODB_TESTS") != "1",
    reason="DynamoDB Local integration tests are opt-in",
)


@pytest.fixture
def store():
    namespace = f"pytest-{uuid4().hex[:12]}"
    repository = DynamoDBTraceStore(namespace=namespace)
    repository.validate_startup()
    yield repository
    repository.reset_demo_namespace()


def test_benign_trace_survives_service_reconstruction(store):
    first = build_run_service(store=store)
    run = first.start_run("ORD-8842", "enforce", "benign")
    assert run.status == RunStatus.COMPLETED

    reconstructed = DynamoDBTraceStore(namespace=store.namespace)
    second = build_run_service(store=reconstructed)
    loaded = second.get_run(run.trace_id)

    assert loaded == run
    assert second.verify_trace(run.trace_id).valid
    assert [event.sequence for event in second.get_events(run.trace_id)] == list(
        range(1, len(second.get_events(run.trace_id)) + 1)
    )


def test_pending_approval_resumes_and_replays_across_restarts(store):
    first = build_run_service(store=store)
    pending = first.start_run("ORD-8842", "enforce", "adversarial")
    assert pending.status == RunStatus.PENDING_APPROVAL
    arguments = {
        "decision": "approve",
        "approver_label": "DEMO-APPROVER-OPS-1",
        "comment": "Restart recovery.",
        "expected_version": 1,
        "idempotency_key": "dynamodb-restart-approval-001",
    }

    second = build_run_service(
        store=DynamoDBTraceStore(namespace=store.namespace)
    )
    resolved = second.resolve_approval(pending.pending_approval_id, **arguments)
    assert resolved.run.status == RunStatus.COMPLETED
    assert resolved.run.confirmed_booking_id is not None
    assert resolved.run.notification_id == "NOTIFY-ORD-8842"

    third = build_run_service(
        store=DynamoDBTraceStore(namespace=store.namespace)
    )
    replay = third.resolve_approval(pending.pending_approval_id, **arguments)
    assert replay.idempotent_replay
    assert replay.run == resolved.run
    assert third.verify_trace(pending.trace_id).valid


def test_optimistic_revision_rejects_a_stale_snapshot(store):
    service = build_run_service(store=store)
    run = service.start_run("ORD-8842", "enforce", "benign")
    first = store.load_trace(run.trace_id)
    stale = store.load_trace(run.trace_id)

    committed = store.commit_transition(
        TraceTransition(run.trace_id, first.revision, first.state)
    )
    assert committed.revision == first.revision + 1
    with pytest.raises(TraceRevisionConflictError):
        store.commit_transition(
            TraceTransition(run.trace_id, stale.revision, stale.state)
        )


def test_two_service_instances_allow_only_one_approval_winner(store):
    starter = build_run_service(store=store)
    run = starter.start_run("ORD-8842", "enforce", "adversarial")

    def decide(decision: str):
        service = build_run_service(
            store=DynamoDBTraceStore(namespace=store.namespace)
        )
        try:
            return service.resolve_approval(
                run.pending_approval_id,
                decision=decision,
                approver_label="DEMO-APPROVER-OPS-1",
                comment="Distributed race.",
                expected_version=1,
                idempotency_key=f"dynamodb-race-{decision}",
            )
        except ApprovalPersistenceConflictError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(decide, ("approve", "reject")))

    assert sum(not isinstance(item, Exception) for item in results) == 1
    final = store.get_state(run.trace_id)
    assert final.status in {RunStatus.COMPLETED, RunStatus.CANCELLED}
    assert store.verify_trace(run.trace_id).valid


def test_event_replay_and_durable_effect_receipts_are_stable(store):
    service = build_run_service(store=store)
    run = service.start_run("ORD-8842", "enforce", "benign")
    state = store.get_state(run.trace_id)
    first = store.append_event(
        state,
        EventType.AGENT_COMPLETED,
        "Durable replay contract event.",
        idempotency_key="dynamodb-event-replay-001",
    )
    revision = state.storage_revision
    replay = store.append_event(
        state,
        EventType.AGENT_COMPLETED,
        "Durable replay contract event.",
        idempotency_key="dynamodb-event-replay-001",
    )
    assert replay == first
    assert state.storage_revision == revision
    confirm_key = f"{run.trace_id}:confirm:PREP-ORD-8842-QUOTE-COLD-01"
    receipt = store.get_effect_receipt(run.trace_id, opaque_key_hash(confirm_key))
    assert receipt is not None
    assert receipt.result["confirmation_id"] == run.confirmed_booking_id


def test_tamper_detection_and_trace_isolation(store):
    service = build_run_service(store=store)
    first = service.start_run("ORD-8842", "enforce", "benign")
    second = service.start_run("ORD-8842", "enforce", "benign")
    service.tamper_trace_for_demo(first.trace_id, 5, "Disposable database alteration")
    invalid = service.verify_trace(first.trace_id)
    assert not invalid.valid
    assert invalid.first_bad_sequence == 5
    assert service.verify_trace(second.trace_id).valid


def test_reject_after_restart_cancels_once(store):
    first = build_run_service(store=store)
    pending = first.start_run("ORD-8842", "enforce", "adversarial")
    restarted = build_run_service(
        store=DynamoDBTraceStore(namespace=store.namespace)
    )
    result = restarted.resolve_approval(
        pending.pending_approval_id,
        decision="reject",
        approver_label="DEMO-APPROVER-OPS-2",
        comment="Reject after restart.",
        expected_version=1,
        idempotency_key="dynamodb-restart-reject-001",
    )
    assert result.run.status == RunStatus.CANCELLED
    assert result.run.spend_reserved_minor == 0
    assert restarted.verify_trace(pending.trace_id).valid


def test_namespace_reset_cannot_delete_another_namespace(store):
    other = DynamoDBTraceStore(namespace=f"other-{uuid4().hex[:12]}")
    first = build_run_service(store=store).start_run(
        "ORD-8842", "enforce", "benign"
    )
    second = build_run_service(store=other).start_run(
        "ORD-8842", "enforce", "benign"
    )
    assert store.reset_demo_namespace() >= 1
    with pytest.raises(TraceNotFoundError):
        store.get_state(first.trace_id)
    assert other.get_state(second.trace_id).status == RunStatus.COMPLETED
    other.reset_demo_namespace()


def test_restart_recovers_after_approval_claim_before_resume(store):
    first = build_run_service(store=store)
    pending = first.start_run("ORD-8842", "enforce", "adversarial")
    approval = store.get_approval(pending.pending_approval_id)
    command = ApprovalCommand(
        decision=ApprovalDecision.APPROVE,
        approver_label="DEMO-APPROVER-OPS-1",
        comment="Recover claimed approval.",
        expected_version=1,
        idempotency_key="dynamodb-claimed-before-resume-001",
    )
    # Simulate a crash immediately after the durable conditional approval claim.
    store.replace_approval(first.approval_lifecycle.resolve(approval, command))

    restarted = build_run_service(
        store=DynamoDBTraceStore(namespace=store.namespace)
    )
    recovered = restarted.resolve_approval(
        approval.approval_id,
        decision="approve",
        approver_label=command.approver_label,
        comment=command.comment,
        expected_version=command.expected_version,
        idempotency_key=command.idempotency_key,
    )
    assert recovered.idempotent_replay
    assert recovered.run.status == RunStatus.COMPLETED
    assert recovered.run.confirmed_booking_id is not None
    assert restarted.verify_trace(pending.trace_id).valid
