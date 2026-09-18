"""Validation and immutable transitions for demo approval records."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Callable

from packages.commitments import prepared_action_hash, prepared_state_hash
from packages.domain.enums import (
    ApprovalDecision,
    ApprovalStatus,
    CommitmentStatus,
    RunStatus,
    WorkflowStage,
)
from packages.domain.errors import (
    ApprovalActionMismatchError,
    ApprovalExpiredError,
    ApprovalNotPendingError,
    ApprovalPolicyMismatchError,
    ApprovalStateMismatchError,
    ApprovalVersionConflictError,
    ApproverConflictError,
)
from packages.domain.models import ApprovalRecord, TrajectoryState, utc_now


@dataclass(frozen=True, slots=True)
class ApprovalCommand:
    decision: ApprovalDecision
    approver_label: str
    comment: str | None
    expected_version: int
    idempotency_key: str

    def fingerprint(self) -> str:
        payload = json.dumps(
            {
                "decision": self.decision.value,
                "approver_label": self.approver_label,
                "comment": self.comment,
                "expected_version": self.expected_version,
                "idempotency_key": self.idempotency_key,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ApprovalLifecycle:
    def __init__(self, now_fn: Callable[[], datetime] = utc_now) -> None:
        self.now_fn = now_fn

    def validate_pending(
        self,
        approval: ApprovalRecord,
        state: TrajectoryState,
        command: ApprovalCommand,
    ) -> None:
        if approval.status != ApprovalStatus.PENDING_APPROVAL:
            raise ApprovalNotPendingError(
                f"Approval {approval.approval_id} is already {approval.status.value}."
            )
        if command.expected_version != approval.version:
            raise ApprovalVersionConflictError(
                f"Approval {approval.approval_id} is no longer at version {command.expected_version}."
            )
        if self.now_fn() >= approval.expires_at:
            raise ApprovalExpiredError(f"Approval {approval.approval_id} has expired.")
        if state.status != RunStatus.PENDING_APPROVAL or state.workflow_stage != WorkflowStage.AWAITING_APPROVAL:
            raise ApprovalStateMismatchError("The run is not waiting at the expected approval stage.")
        if state.pending_approval_id != approval.approval_id or state.trace_id != approval.trace_id:
            raise ApprovalStateMismatchError("The approval is not bound to this pending trace.")
        prepared = state.prepared_actions.get(approval.prepared_action_id)
        if prepared is None or prepared.trace_id != state.trace_id:
            raise ApprovalActionMismatchError("The approval's prepared action was not found in this trace.")
        if prepared.status != CommitmentStatus.PENDING_APPROVAL:
            raise ApprovalStateMismatchError("The prepared action is not pending approval.")
        if prepared_action_hash(prepared) != prepared.action_hash or approval.action_hash != prepared.action_hash:
            raise ApprovalActionMismatchError("The prepared action no longer matches the approval.")
        if prepared_state_hash(state, prepared) != prepared.state_hash or approval.state_hash != prepared.state_hash:
            raise ApprovalStateMismatchError("The prepared state no longer matches the approval.")
        if state.mandate is None or (
            approval.policy_version != state.policy_version
            or prepared.policy_version != state.policy_version
            or prepared.mandate_id != state.mandate.mandate_id
        ):
            raise ApprovalPolicyMismatchError("The active mandate or policy version changed after preparation.")
        if (
            state.spend_committed_minor != prepared.spend_committed_at_prepare_minor
            or state.spend_reserved_minor != prepared.spend_reserved_after_minor
        ):
            raise ApprovalStateMismatchError("Spend state changed after the action was prepared.")
        if state.selected_quote is None or (
            state.selected_quote.quote_id != prepared.resource_id
            or state.selected_quote.amount_minor != prepared.amount_minor
            or state.selected_quote.currency != prepared.currency
        ):
            raise ApprovalActionMismatchError("The selected quote changed after preparation.")
        if command.approver_label.casefold() == prepared.prepared_by.value.casefold():
            raise ApproverConflictError("The action preparer cannot approve the same commitment.")

    def resolve(
        self,
        approval: ApprovalRecord,
        command: ApprovalCommand,
    ) -> ApprovalRecord:
        status = (
            ApprovalStatus.APPROVED
            if command.decision == ApprovalDecision.APPROVE
            else ApprovalStatus.REJECTED
        )
        return replace(
            approval,
            status=status,
            version=approval.version + 1,
            decided_at=self.now_fn(),
            decision=command.decision,
            approver_label=command.approver_label,
            comment=command.comment,
            decision_idempotency_key=command.idempotency_key,
        )

    def expire(self, approval: ApprovalRecord) -> ApprovalRecord:
        if approval.status != ApprovalStatus.PENDING_APPROVAL:
            raise ApprovalNotPendingError(
                f"Approval {approval.approval_id} is already {approval.status.value}."
            )
        return replace(
            approval,
            status=ApprovalStatus.EXPIRED,
            version=approval.version + 1,
            decided_at=self.now_fn(),
        )
