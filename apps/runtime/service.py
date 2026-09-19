"""Application service shared by the CLI and HTTP API."""

from __future__ import annotations

from threading import RLock
from typing import Callable

from fixtures import FixtureLoader
from packages.approvals import ApprovalCommand, ApprovalLifecycle
from packages.domain.enums import ApprovalDecision, ApprovalStatus, CommitmentStatus, EventType, GovernanceMode, RunStatus, ScenarioName
from packages.domain.errors import (
    ApprovalExpiredError,
    ApprovalIdempotencyConflictError,
    ApprovalNotPendingError,
    UnsupportedModeError,
    UnsupportedScenarioError,
)
from packages.domain.models import (
    ApprovalRecord,
    ApprovalResolution,
    DashboardProjection,
    Decision,
    OrderSummary,
    ResetResult,
    RunSummary,
    TamperResult,
    TraceEvent,
    VerificationResult,
    utc_now,
)
from packages.governor import ManifestGovernor
from packages.policy import PolicyEngine, build_policy_engine_from_env
from packages.projections import build_dashboard_projection
from packages.storage.protocol import TraceRepository
from packages.storage.factory import build_trace_repository_from_env
from packages.tools import MockLogisticsTools, build_tool_registry

from .agents import CarrierAgent, CustomerCommunicationsAgent, DispatchAgent, InventoryAgent
from .orchestrator import ShipmentOrchestrator


class RunService:
    def __init__(self, loader, store, mocks, orchestrator, policy_engine, approval_lifecycle) -> None:
        self.loader: FixtureLoader = loader
        self.store: TraceRepository = store
        self.mocks: MockLogisticsTools = mocks
        self.orchestrator: ShipmentOrchestrator = orchestrator
        self.policy_engine = policy_engine
        self.approval_lifecycle: ApprovalLifecycle = approval_lifecycle
        self._approval_resolution_lock = RLock()

    def start_run(
        self,
        order_id: str,
        mode: str = "enforce",
        scenario: str = "benign",
    ) -> RunSummary:
        try:
            governance_mode = GovernanceMode(mode)
        except ValueError as exc:
            raise UnsupportedModeError(f"Mode {mode} is not supported.") from exc
        try:
            scenario_name = ScenarioName(scenario)
        except ValueError as exc:
            raise UnsupportedScenarioError(f"Scenario {scenario} is not supported.") from exc
        order = self.loader.get_order(order_id)
        mandate = self.loader.get_mandate(order, governance_mode)
        scenario_config = self.loader.get_scenario(order_id, scenario_name)
        state = self.orchestrator.run(
            order_id,
            governance_mode,
            scenario_name,
            mandate=mandate,
            scenario_config=scenario_config,
        )
        return RunSummary.from_state(state, self.policy_engine.name)

    def get_run(self, trace_id: str) -> RunSummary:
        return RunSummary.from_state(self.store.get_state(trace_id), self.policy_engine.name)

    def get_events(self, trace_id: str) -> list[TraceEvent]:
        return self.store.get_events(trace_id)

    def get_decisions(self, trace_id: str) -> list[Decision]:
        return self.store.get_decisions(trace_id)

    def verify_trace(self, trace_id: str) -> VerificationResult:
        return self.store.verify_trace(trace_id)

    def get_dashboard_projection(self, trace_id: str) -> DashboardProjection:
        return build_dashboard_projection(self.store.get_state(trace_id))

    def tamper_trace_for_demo(
        self,
        trace_id: str,
        sequence: int,
        replacement_summary: str,
    ) -> TamperResult:
        return self.store.tamper_event_summary_for_demo(
            trace_id, sequence, replacement_summary
        )

    def get_approval(self, approval_id: str) -> ApprovalRecord:
        return self.store.get_approval(approval_id)

    def list_approvals(
        self,
        trace_id: str | None = None,
        status: str | None = None,
    ) -> list[ApprovalRecord]:
        if trace_id is not None:
            self.store.get_state(trace_id)
        approval_status = ApprovalStatus(status) if status is not None else None
        return self.store.list_approvals(trace_id, approval_status)

    def resolve_approval(
        self,
        approval_id: str,
        *,
        decision: str,
        approver_label: str,
        comment: str | None,
        expected_version: int,
        idempotency_key: str,
    ) -> ApprovalResolution:
        command = ApprovalCommand(
            decision=ApprovalDecision(decision),
            approver_label=approver_label,
            comment=comment,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
        )
        fingerprint = command.fingerprint()
        with self._approval_resolution_lock:
            previous = self.store.get_approval_replay_fingerprint(approval_id, idempotency_key)
            if previous is not None:
                if previous != fingerprint:
                    raise ApprovalIdempotencyConflictError(
                        f"Idempotency key {idempotency_key} was reused with different approval fields."
                    )
                approval = self.store.get_approval(approval_id)
                state = self.store.get_state(approval.trace_id)
                return ApprovalResolution(
                    approval=approval,
                    run=RunSummary.from_state(state, self.policy_engine.name),
                    idempotent_replay=True,
                )

            approval = self.store.get_approval(approval_id)
            if approval.status == ApprovalStatus.EXPIRED:
                raise ApprovalExpiredError(f"Approval {approval_id} has expired.")
            if approval.status != ApprovalStatus.PENDING_APPROVAL:
                if self._matches_claimed_command(approval, command):
                    state = self.store.load_trace(approval.trace_id).state
                    if state.status == RunStatus.PENDING_APPROVAL:
                        self._continue_resolved_approval(state, approval)
                    self.store.record_approval_replay(
                        approval_id, idempotency_key, fingerprint
                    )
                    return ApprovalResolution(
                        approval=self.store.get_approval(approval_id),
                        run=RunSummary.from_state(state, self.policy_engine.name),
                        idempotent_replay=True,
                    )
                raise ApprovalNotPendingError(
                    f"Approval {approval_id} is already {approval.status.value}."
                )
            state = self.store.load_trace(approval.trace_id).state
            try:
                self.approval_lifecycle.validate_pending(approval, state, command)
            except ApprovalExpiredError:
                self._expire_locked(approval, state)
                raise

            resolved = self.approval_lifecycle.resolve(approval, command)
            self.store.replace_approval(resolved)
            self._continue_resolved_approval(state, resolved)
            self.store.record_approval_replay(approval_id, idempotency_key, fingerprint)
            return ApprovalResolution(
                approval=self.store.get_approval(approval_id),
                run=RunSummary.from_state(state, self.policy_engine.name),
            )

    @staticmethod
    def _matches_claimed_command(
        approval: ApprovalRecord, command: ApprovalCommand
    ) -> bool:
        expected_status = (
            ApprovalStatus.APPROVED
            if command.decision == ApprovalDecision.APPROVE
            else ApprovalStatus.REJECTED
        )
        return (
            approval.status == expected_status
            and approval.version == command.expected_version + 1
            and approval.decision == command.decision
            and approval.approver_label == command.approver_label
            and approval.comment == command.comment
            and approval.decision_idempotency_key == command.idempotency_key
        )

    def _continue_resolved_approval(
        self, state, resolved: ApprovalRecord
    ) -> None:
        if resolved.status == ApprovalStatus.APPROVED:
            prepared = state.prepared_actions[resolved.prepared_action_id]
            prepared.status = CommitmentStatus.APPROVED
            state.approved_by = resolved.approver_label
            self.store.append_event(
                state,
                EventType.APPROVAL_APPROVED,
                "The prepared commitment was approved.",
                details={
                    "approval_id": resolved.approval_id,
                    "approver_label": resolved.approver_label,
                    "version": resolved.version,
                },
                idempotency_key=(
                    f"approval:{resolved.approval_id}:approved:v{resolved.version}"
                ),
            )
            self.orchestrator.resume_approved(state, resolved)
        else:
            self.store.append_event(
                state,
                EventType.APPROVAL_REJECTED,
                "The prepared commitment was rejected.",
                details={
                    "approval_id": resolved.approval_id,
                    "approver_label": resolved.approver_label,
                    "version": resolved.version,
                },
                idempotency_key=(
                    f"approval:{resolved.approval_id}:rejected:v{resolved.version}"
                ),
            )
            self.orchestrator.cancel_pending(
                state, resolved, "APPROVAL_REJECTED"
            )

    def expire_due_approvals(self) -> list[ApprovalRecord]:
        expired: list[ApprovalRecord] = []
        with self._approval_resolution_lock:
            now = self.approval_lifecycle.now_fn()
            for approval in self.store.list_approvals(status=ApprovalStatus.PENDING_APPROVAL):
                if now >= approval.expires_at:
                    state = self.store.load_trace(approval.trace_id).state
                    expired.append(self._expire_locked(approval, state))
        return expired

    def _expire_locked(self, approval: ApprovalRecord, state) -> ApprovalRecord:
        expired = self.approval_lifecycle.expire(approval)
        self.store.replace_approval(expired)
        self.store.append_event(
            state,
            EventType.APPROVAL_EXPIRED,
            "The prepared commitment approval expired.",
            details={"approval_id": expired.approval_id, "version": expired.version},
            idempotency_key=(
                f"approval:{expired.approval_id}:expired:v{expired.version}"
            ),
        )
        self.orchestrator.cancel_pending(state, expired, "APPROVAL_EXPIRED")
        return expired

    def list_orders(self) -> list[OrderSummary]:
        return [
            OrderSummary(order.order_id, order.cargo_class, self.loader.get_inventory_fact(order).shipment_weight_kg, order.currency)
            for order in self.loader.list_orders()
        ]

    def reset_demo(self) -> ResetResult:
        removed = self.store.reset_demo_namespace()
        self.mocks.reset()
        return ResetResult(status="reset", removed_run_count=removed)


def build_run_service(
    now_fn: Callable | None = None,
    *,
    policy_engine: PolicyEngine | None = None,
    store: TraceRepository | None = None,
) -> RunService:
    loader = FixtureLoader()
    loader.validate_all()
    active_store = store or build_trace_repository_from_env()
    registry, mocks = build_tool_registry(loader)
    active_policy_engine = policy_engine or build_policy_engine_from_env()
    active_policy_engine.validate_startup()
    governor = ManifestGovernor(registry, active_store, active_policy_engine, loader)
    agents = [InventoryAgent(), DispatchAgent(), CarrierAgent(), CustomerCommunicationsAgent()]
    orchestrator = ShipmentOrchestrator(
        agents, governor, active_store, loader
    )
    approval_lifecycle = ApprovalLifecycle(now_fn or utc_now)
    return RunService(
        loader,
        active_store,
        mocks,
        orchestrator,
        active_policy_engine,
        approval_lifecycle,
    )
