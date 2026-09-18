from dataclasses import replace

from apps.runtime.service import build_run_service
from packages.approvals import ApprovalCommand
from packages.domain.enums import (
    AgentName,
    ApprovalDecision,
    ApprovalStatus,
    CommitmentStatus,
    DecisionOutcome,
)


def approved_context():
    service = build_run_service()
    run = service.start_run("ORD-8842", "enforce", "adversarial")
    approval = service.get_approval(run.pending_approval_id)
    state = service.store.get_state_for_update(run.trace_id)
    command = ApprovalCommand(
        ApprovalDecision.APPROVE,
        "DEMO-APPROVER-OPS-1",
        None,
        1,
        "approval-policy-001",
    )
    service.approval_lifecycle.validate_pending(approval, state, command)
    approval = service.approval_lifecycle.resolve(approval, command)
    service.store.replace_approval(approval)
    state.prepared_actions[approval.prepared_action_id].status = CommitmentStatus.APPROVED
    state.approved_by = approval.approver_label
    return service, state, approval


def confirm(service, state, approval):
    prepared = state.prepared_actions[approval.prepared_action_id]
    return service.orchestrator.governor.execute_tool(
        state,
        AgentName.CARRIER,
        "confirm_freight_booking",
        prepared_action_id=prepared.prepared_action_id,
        action_hash=prepared.action_hash,
        idempotency_key=f"{state.trace_id}:policy-confirm",
    )


def test_exact_approved_exception_is_allowed_by_fresh_policy_evaluation():
    service, state, approval = approved_context()

    result = confirm(service, state, approval)

    assert result.decision.policy_outcome == DecisionOutcome.ALLOW
    assert result.decision.reason_code == "SPEND_EXCEPTION_APPROVED"
    assert result.value is not None


def test_tampered_approval_action_hash_fails_closed():
    service, state, approval = approved_context()
    service.store.replace_approval(replace(approval, action_hash="sha256:tampered"))

    result = confirm(service, state, approval)

    assert result.decision.policy_outcome == DecisionOutcome.BLOCK
    assert result.decision.reason_code == "APPROVAL_ACTION_MISMATCH"
    assert result.value is None


def test_expired_approval_fails_closed_during_policy_evaluation():
    service, state, approval = approved_context()
    service.store.replace_approval(replace(approval, status=ApprovalStatus.EXPIRED))

    result = confirm(service, state, approval)

    assert result.decision.policy_outcome == DecisionOutcome.BLOCK
    assert result.decision.reason_code == "APPROVAL_EXPIRED"
    assert result.value is None
