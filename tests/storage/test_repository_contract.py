"""The same externally visible repository behavior for both storage adapters."""

import os
from uuid import uuid4

import pytest

from apps.runtime.service import build_run_service
from packages.domain.enums import RunStatus
from packages.ledger import MemoryTraceStore
from packages.storage.dynamodb import DynamoDBTraceStore


def _memory():
    return MemoryTraceStore()


def _dynamodb():
    if os.getenv("MANIFEST_DYNAMODB_TESTS") != "1":
        pytest.skip("DynamoDB Local integration tests are opt-in")
    return DynamoDBTraceStore(namespace=f"contract-{uuid4().hex[:12]}")


@pytest.mark.parametrize("repository_factory", [_memory, _dynamodb], ids=["memory", "dynamodb"])
def test_run_approval_replay_and_verification_contract(repository_factory):
    repository = repository_factory()
    repository.validate_startup()
    try:
        service = build_run_service(store=repository)
        pending = service.start_run("ORD-8842", "enforce", "adversarial")
        assert pending.status == RunStatus.PENDING_APPROVAL
        assert repository.load_trace(pending.trace_id).state == repository.get_state(
            pending.trace_id
        )
        arguments = {
            "decision": "approve",
            "approver_label": "DEMO-APPROVER-OPS-1",
            "comment": "Shared contract.",
            "expected_version": 1,
            "idempotency_key": "shared-repository-contract-approval",
        }
        first = service.resolve_approval(pending.pending_approval_id, **arguments)
        replay = service.resolve_approval(pending.pending_approval_id, **arguments)
        assert first.run.status == RunStatus.COMPLETED
        assert replay.idempotent_replay
        assert repository.verify_trace(pending.trace_id).valid
        assert len(repository.get_events(pending.trace_id)) > 0
        assert len(repository.get_decisions(pending.trace_id)) > 0
    finally:
        repository.reset_demo_namespace()
