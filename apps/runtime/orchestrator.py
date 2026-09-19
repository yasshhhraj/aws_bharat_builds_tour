"""Bounded sequential orchestration for the four deterministic agents."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

from fixtures import FixtureLoader
from packages.domain.enums import AgentName, EventType, GovernanceMode, RunStatus, ScenarioName, WorkflowStage
from packages.domain.errors import ApprovalStateMismatchError, ManifestError, PolicyBlockedError
from packages.domain.models import ApprovalRecord, ScenarioConfig, ShipmentMandate, TrajectoryState
from packages.governor import ManifestGovernor
from packages.storage.protocol import TraceRepository

from .agents.base import BaseAgent


class ShipmentOrchestrator:
    def __init__(
        self,
        agents: Sequence[BaseAgent],
        governor: ManifestGovernor,
        store: TraceRepository,
        loader: FixtureLoader | None = None,
    ) -> None:
        self.agents = tuple(agents)
        self.governor = governor
        self.store = store
        self.loader = loader or FixtureLoader()

    def run(
        self,
        order_id: str,
        mode: GovernanceMode = GovernanceMode.SHADOW,
        scenario: ScenarioName = ScenarioName.BENIGN,
        *,
        mandate: ShipmentMandate | None = None,
        scenario_config: ScenarioConfig | None = None,
    ) -> TrajectoryState:
        order = self.loader.get_order(order_id)
        active_mandate = mandate or self.loader.get_mandate(order, mode)
        active_scenario = scenario_config or self.loader.get_scenario(order_id, scenario)
        state = TrajectoryState(
            trace_id=f"TR-{uuid4()}",
            order_id=order_id,
            status=RunStatus.RUNNING,
            mode=mode,
            scenario=scenario,
            scenario_config=active_scenario,
            mandate=active_mandate,
            policy_version=active_mandate.policy_version,
            spend_committed_minor=active_scenario.prior_committed_minor,
        )
        self.store.create_run(state)
        self.store.append_event(
            state,
            EventType.RUN_STARTED,
            f"Started {scenario.value} journey for {order_id} in {mode.value} mode.",
            details={
                "runtime_mode": "deterministic",
                "governor_mode": "policy_enforced",
                "mode": mode.value,
                "scenario": scenario.value,
                "mandate_id": active_mandate.mandate_id,
                "policy_version": state.policy_version,
            },
            idempotency_key=f"run:{state.trace_id}:started",
        )
        try:
            for agent in self.agents:
                if state.pending_approval_id:
                    break
                state.current_agent = agent.name
                self.store.append_event(state, EventType.AGENT_STARTED, f"{agent.name.value} agent started.", agent=agent.name)
                summary = agent.run(state, self.governor)
                if state.pending_approval_id:
                    state.workflow_stage = WorkflowStage.AWAITING_APPROVAL
                    self.store.append_event(state, EventType.AGENT_PAUSED, summary, agent=agent.name)
                else:
                    self._mark_agent_stage(state, agent.name)
                    self.store.append_event(state, EventType.AGENT_COMPLETED, summary, agent=agent.name)
            state.current_agent = None
            if state.pending_approval_id:
                state.status = RunStatus.PENDING_APPROVAL
                self.store.append_event(
                    state, EventType.RUN_PAUSED,
                    f"Run paused for approval {state.pending_approval_id}.",
                    details={"approval_id": state.pending_approval_id},
                    idempotency_key=f"run:{state.trace_id}:paused:{state.pending_approval_id}",
                )
            else:
                state.status = RunStatus.COMPLETED
                state.workflow_stage = WorkflowStage.COMPLETE
                self.store.append_event(
                    state,
                    EventType.RUN_COMPLETED,
                    f"Completed deterministic journey for {order_id}.",
                    idempotency_key=f"run:{state.trace_id}:completed",
                )
        except PolicyBlockedError as exc:
            state.status = RunStatus.BLOCKED
            state.workflow_stage = WorkflowStage.BLOCKED
            state.current_agent = None
            state.error = exc.message
            self.store.append_event(state, EventType.RUN_FAILED, exc.message, details={"error_code": exc.code, "terminal_status": "blocked"})
        except Exception as exc:
            state.status = RunStatus.FAILED
            state.workflow_stage = WorkflowStage.FAILED
            state.current_agent = None
            state.error = exc.message if isinstance(exc, ManifestError) else "Run failed unexpectedly."
            self.store.append_event(state, EventType.RUN_FAILED, state.error, details={"error_code": getattr(exc, "code", "UNEXPECTED_ERROR")})
        return state

    def resume_approved(
        self, state: TrajectoryState, approval: ApprovalRecord
    ) -> TrajectoryState:
        if state.status != RunStatus.PENDING_APPROVAL or state.workflow_stage != WorkflowStage.AWAITING_APPROVAL:
            raise ApprovalStateMismatchError("The run is not waiting for approval.")
        carrier = self._agent(AgentName.CARRIER)
        communications = self._agent(AgentName.CUSTOMER_COMMUNICATIONS)
        state.status = RunStatus.RUNNING
        state.current_agent = AgentName.CARRIER
        self.store.append_event(
            state,
            EventType.RUN_RESUMED,
            f"Run resumed after approval {approval.approval_id}.",
            details={"approval_id": approval.approval_id},
            idempotency_key=f"run:{state.trace_id}:resumed:{approval.approval_id}",
        )
        self.store.append_event(
            state,
            EventType.AGENT_RESUMED,
            "carrier agent resumed the prepared booking.",
            agent=AgentName.CARRIER,
        )
        try:
            summary = carrier.resume_booking(state, self.governor, approval)  # type: ignore[attr-defined]
            self.store.append_event(state, EventType.AGENT_COMPLETED, summary, agent=AgentName.CARRIER)
            state.current_agent = AgentName.CUSTOMER_COMMUNICATIONS
            self.store.append_event(
                state,
                EventType.AGENT_STARTED,
                "customer_communications agent started.",
                agent=AgentName.CUSTOMER_COMMUNICATIONS,
            )
            summary = communications.run(state, self.governor)
            state.workflow_stage = WorkflowStage.NOTIFICATION_SENT
            self.store.append_event(
                state,
                EventType.AGENT_COMPLETED,
                summary,
                agent=AgentName.CUSTOMER_COMMUNICATIONS,
            )
            state.current_agent = None
            state.status = RunStatus.COMPLETED
            state.workflow_stage = WorkflowStage.COMPLETE
            self.store.append_event(
                state,
                EventType.RUN_COMPLETED,
                f"Completed approved journey for {state.order_id}.",
                idempotency_key=f"run:{state.trace_id}:completed",
            )
        except PolicyBlockedError as exc:
            state.status = RunStatus.BLOCKED
            state.workflow_stage = WorkflowStage.BLOCKED
            state.current_agent = None
            state.error = exc.message
            self.store.append_event(
                state,
                EventType.RUN_FAILED,
                exc.message,
                details={"error_code": exc.code, "terminal_status": "blocked"},
            )
        except Exception as exc:
            state.status = RunStatus.FAILED
            state.workflow_stage = WorkflowStage.FAILED
            state.current_agent = None
            state.error = exc.message if isinstance(exc, ManifestError) else "Run failed unexpectedly."
            self.store.append_event(
                state,
                EventType.RUN_FAILED,
                state.error,
                details={"error_code": getattr(exc, "code", "UNEXPECTED_ERROR")},
            )
        return state

    def cancel_pending(
        self,
        state: TrajectoryState,
        approval: ApprovalRecord,
        reason_code: str,
    ) -> TrajectoryState:
        if state.status != RunStatus.PENDING_APPROVAL or state.workflow_stage != WorkflowStage.AWAITING_APPROVAL:
            raise ApprovalStateMismatchError("The run is not waiting for approval.")
        carrier = self._agent(AgentName.CARRIER)
        state.current_agent = AgentName.CARRIER
        self.store.append_event(
            state,
            EventType.AGENT_RESUMED,
            "carrier agent resumed to cancel the prepared booking.",
            agent=AgentName.CARRIER,
        )
        summary = carrier.cancel_booking(state, self.governor, approval, reason_code)  # type: ignore[attr-defined]
        self.store.append_event(state, EventType.AGENT_COMPLETED, summary, agent=AgentName.CARRIER)
        state.current_agent = None
        state.status = RunStatus.CANCELLED
        state.workflow_stage = WorkflowStage.CANCELLED
        state.terminal_reason = reason_code
        self.store.append_event(
            state,
            EventType.RUN_CANCELLED,
            "Run cancelled after the prepared booking was released.",
            details={"reason_code": reason_code, "approval_id": approval.approval_id},
            idempotency_key=f"run:{state.trace_id}:cancelled:{reason_code}",
        )
        return state

    def _agent(self, name: AgentName) -> BaseAgent:
        for agent in self.agents:
            if agent.name == name:
                return agent
        raise ApprovalStateMismatchError(f"Required agent {name.value} is unavailable.")

    @staticmethod
    def _mark_agent_stage(state: TrajectoryState, name: AgentName) -> None:
        if name == AgentName.INVENTORY:
            state.workflow_stage = WorkflowStage.INVENTORY_COMPLETE
        elif name == AgentName.DISPATCH:
            state.workflow_stage = WorkflowStage.DISPATCH_COMPLETE
        elif name == AgentName.CARRIER and state.confirmed_booking_id:
            state.workflow_stage = WorkflowStage.BOOKING_CONFIRMED
        elif name == AgentName.CUSTOMER_COMMUNICATIONS:
            state.workflow_stage = WorkflowStage.NOTIFICATION_SENT
