"""BaseAgent-compatible adapters backed by the isolated Strands runtime."""

from __future__ import annotations

from packages.domain.enums import AgentName, ApprovalStatus, CommitmentStatus
from packages.domain.errors import ApprovalStateMismatchError
from packages.domain.models import ApprovalRecord, TrajectoryState
from packages.governor import ManifestGovernor

from .agent_runtime import AgentRunRequest, RolePhase, RoleRuntime
from .agents.base import BaseAgent


class StrandsRoleAgent(BaseAgent):
    def __init__(self, name: AgentName, runtime: RoleRuntime) -> None:
        self.name = name
        self.runtime = runtime

    def run(self, state: TrajectoryState, governor: ManifestGovernor) -> str:
        result = self.runtime.invoke(
            AgentRunRequest(self.name, RolePhase.RUN, state, governor)
        )
        return result.summary


class StrandsCarrierAgent(StrandsRoleAgent):
    def __init__(self, runtime: RoleRuntime) -> None:
        super().__init__(AgentName.CARRIER, runtime)

    def resume_booking(
        self,
        state: TrajectoryState,
        governor: ManifestGovernor,
        approval: ApprovalRecord,
    ) -> str:
        if approval.status != ApprovalStatus.APPROVED:
            raise ApprovalStateMismatchError(
                "Only an approved record can resume a booking."
            )
        prepared = state.prepared_actions.get(approval.prepared_action_id)
        if prepared is None or prepared.status != CommitmentStatus.APPROVED:
            raise ApprovalStateMismatchError(
                "The prepared action is not approved for confirmation."
            )
        return self.runtime.invoke(
            AgentRunRequest(
                self.name,
                RolePhase.RESUME_APPROVED,
                state,
                governor,
                approval=approval,
            )
        ).summary

    def cancel_booking(
        self,
        state: TrajectoryState,
        governor: ManifestGovernor,
        approval: ApprovalRecord,
        reason_code: str,
    ) -> str:
        prepared = state.prepared_actions.get(approval.prepared_action_id)
        if prepared is None:
            raise ApprovalStateMismatchError(
                "The prepared action to cancel was not found."
            )
        if approval.status == ApprovalStatus.REJECTED:
            prepared.status = CommitmentStatus.REJECTED
        elif approval.status == ApprovalStatus.EXPIRED:
            prepared.status = CommitmentStatus.EXPIRED
        else:
            raise ApprovalStateMismatchError(
                "Only rejected or expired actions can be cancelled."
            )
        return self.runtime.invoke(
            AgentRunRequest(
                self.name,
                RolePhase.CANCEL,
                state,
                governor,
                approval=approval,
                cancellation_reason_code=reason_code,
            )
        ).summary
