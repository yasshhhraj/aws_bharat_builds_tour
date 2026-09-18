from dataclasses import replace
from datetime import datetime, timezone

import pytest

from apps.runtime.service import build_run_service
from packages.approvals import ApprovalCommand, ApprovalLifecycle
from packages.domain.enums import ApprovalDecision, ApprovalStatus
from packages.domain.errors import (
    ApprovalActionMismatchError,
    ApprovalExpiredError,
    ApprovalVersionConflictError,
    ApproverConflictError,
)


def pending_context():
    service = build_run_service()
    run = service.start_run("ORD-8842", "enforce", "adversarial")
    approval = service.get_approval(run.pending_approval_id)
    state = service.store.get_state_for_update(run.trace_id)
    command = ApprovalCommand(
        ApprovalDecision.APPROVE,
        "DEMO-APPROVER-OPS-1",
        "Approved for a synthetic test.",
        1,
        "approval-unit-001",
    )
    return service, approval, state, command


def test_pending_approval_validates_and_resolves_immutably():
    service, approval, state, command = pending_context()

    service.approval_lifecycle.validate_pending(approval, state, command)
    resolved = service.approval_lifecycle.resolve(approval, command)

    assert approval.status == ApprovalStatus.PENDING_APPROVAL
    assert resolved.status == ApprovalStatus.APPROVED
    assert resolved.version == 2
    assert resolved.decision == ApprovalDecision.APPROVE


def test_stale_version_is_rejected():
    service, approval, state, command = pending_context()
    stale = replace(command, expected_version=99)

    with pytest.raises(ApprovalVersionConflictError):
        service.approval_lifecycle.validate_pending(approval, state, stale)


def test_changed_action_binding_is_rejected():
    service, approval, state, command = pending_context()
    prepared = state.prepared_actions[approval.prepared_action_id]
    prepared.arguments["amount_minor"] = 1

    with pytest.raises(ApprovalActionMismatchError):
        service.approval_lifecycle.validate_pending(approval, state, command)


def test_preparer_cannot_approve_own_action():
    service, approval, state, command = pending_context()
    same_actor = replace(command, approver_label="carrier")

    with pytest.raises(ApproverConflictError):
        service.approval_lifecycle.validate_pending(approval, state, same_actor)


def test_injected_clock_makes_expiry_deterministic():
    _, approval, state, command = pending_context()
    lifecycle = ApprovalLifecycle(
        lambda: datetime(2100, 1, 1, tzinfo=timezone.utc)
    )

    with pytest.raises(ApprovalExpiredError):
        lifecycle.validate_pending(approval, state, command)
