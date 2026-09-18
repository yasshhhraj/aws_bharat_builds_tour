"""Thread-safe in-memory run and ordered event storage."""

from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Any

from packages.domain.enums import AgentName, ApprovalStatus, EffectClass, EventType
from packages.domain.errors import ApprovalNotFoundError, TraceNotFoundError, TraceSequenceError
from packages.domain.models import ApprovalRecord, Decision, TraceEvent, TrajectoryState


class MemoryTraceStore:
    """Checkpoint 2 storage port; later replaced by a hash-chain ledger."""

    def __init__(self) -> None:
        self._runs: dict[str, TrajectoryState] = {}
        self._approvals: dict[str, ApprovalRecord] = {}
        self._approval_replays: dict[tuple[str, str], str] = {}
        self._lock = RLock()

    def create_run(self, state: TrajectoryState) -> None:
        with self._lock:
            if state.trace_id in self._runs:
                raise TraceSequenceError(f"Trace {state.trace_id} already exists.")
            self._runs[state.trace_id] = state

    def append_event(
        self,
        state: TrajectoryState,
        event_type: EventType,
        summary: str,
        *,
        details: dict[str, Any] | None = None,
        agent: AgentName | None = None,
        tool_name: str | None = None,
        effect_class: EffectClass | None = None,
    ) -> TraceEvent:
        with self._lock:
            stored = self._runs.get(state.trace_id)
            if stored is None:
                raise TraceNotFoundError(f"Trace {state.trace_id} was not found.")
            if stored is not state:
                raise TraceSequenceError(
                    f"Trace {state.trace_id} was updated with a detached state object."
                )
            event = TraceEvent(
                trace_id=state.trace_id,
                sequence=state.next_sequence,
                event_type=event_type,
                summary=summary,
                details=details or {},
                agent=agent,
                tool_name=tool_name,
                effect_class=effect_class,
            )
            if state.events and event.sequence != state.events[-1].sequence + 1:
                raise TraceSequenceError(
                    f"Trace {state.trace_id} expected sequence "
                    f"{state.events[-1].sequence + 1}, received {event.sequence}."
                )
            state.events.append(event)
            state.next_sequence += 1
            return event

    def get_state(self, trace_id: str) -> TrajectoryState:
        with self._lock:
            state = self._runs.get(trace_id)
            if state is None:
                raise TraceNotFoundError(f"Trace {trace_id} was not found.")
            return deepcopy(state)

    def get_state_for_update(self, trace_id: str) -> TrajectoryState:
        """Return the live state for RunService while its resolution lock is held."""
        with self._lock:
            state = self._runs.get(trace_id)
            if state is None:
                raise TraceNotFoundError(f"Trace {trace_id} was not found.")
            return state

    def get_events(self, trace_id: str) -> list[TraceEvent]:
        return list(self.get_state(trace_id).events)

    def append_decision(self, state: TrajectoryState, decision: Decision) -> None:
        with self._lock:
            if self._runs.get(state.trace_id) is not state:
                raise TraceSequenceError(f"Trace {state.trace_id} cannot accept a detached decision.")
            if any(item.decision_id == decision.decision_id for item in state.decisions):
                raise TraceSequenceError(f"Decision {decision.decision_id} already exists.")
            state.decisions.append(decision)

    def get_decisions(self, trace_id: str) -> list[Decision]:
        return list(self.get_state(trace_id).decisions)

    def add_approval(self, approval: ApprovalRecord) -> None:
        with self._lock:
            if approval.approval_id in self._approvals:
                raise TraceSequenceError(f"Approval {approval.approval_id} already exists.")
            self._approvals[approval.approval_id] = approval

    def get_approval(self, approval_id: str) -> ApprovalRecord:
        with self._lock:
            approval = self._approvals.get(approval_id)
            if approval is None:
                raise ApprovalNotFoundError(f"Approval {approval_id} was not found.")
            return deepcopy(approval)

    def replace_approval(self, approval: ApprovalRecord) -> None:
        with self._lock:
            if approval.approval_id not in self._approvals:
                raise ApprovalNotFoundError(f"Approval {approval.approval_id} was not found.")
            self._approvals[approval.approval_id] = approval

    def list_approvals(
        self,
        trace_id: str | None = None,
        status: ApprovalStatus | None = None,
    ) -> list[ApprovalRecord]:
        with self._lock:
            items = self._approvals.values()
            if trace_id is not None:
                items = (item for item in items if item.trace_id == trace_id)
            if status is not None:
                items = (item for item in items if item.status == status)
            return deepcopy(sorted(items, key=lambda item: (item.created_at, item.approval_id)))

    def get_approval_replay_fingerprint(
        self, approval_id: str, idempotency_key: str
    ) -> str | None:
        with self._lock:
            return self._approval_replays.get((approval_id, idempotency_key))

    def record_approval_replay(
        self, approval_id: str, idempotency_key: str, fingerprint: str
    ) -> None:
        with self._lock:
            self._approval_replays[(approval_id, idempotency_key)] = fingerprint

    def reset(self) -> int:
        with self._lock:
            removed = len(self._runs)
            self._runs.clear()
            self._approvals.clear()
            self._approval_replays.clear()
            return removed

    def run_count(self) -> int:
        with self._lock:
            return len(self._runs)
