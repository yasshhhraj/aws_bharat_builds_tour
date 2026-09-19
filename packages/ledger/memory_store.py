"""Thread-safe in-memory run, approval, and hash-chain ledger storage."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from threading import RLock
from typing import Any
from uuid import uuid4

from packages.domain.enums import AgentName, ApprovalStatus, EffectClass, EventType, RunStatus
from packages.domain.errors import (
    ApprovalNotFoundError,
    LedgerAppendError,
    LedgerIdempotencyConflictError,
    LedgerTamperValidationError,
    TraceNotFoundError,
    TraceSequenceError,
)
from packages.domain.models import (
    ApprovalRecord,
    Decision,
    LedgerHead,
    TamperResult,
    TraceEvent,
    TrajectoryState,
    VerificationResult,
    utc_now,
)

from .canonical import (
    GENESIS_HASH,
    LEDGER_SCHEMA_VERSION,
    calculate_event_hash,
    event_description_fingerprint,
)
from .verifier import verify_chain


class MemoryTraceStore:
    """Local store whose trace events form one hash chain per run."""

    def __init__(self) -> None:
        self._runs: dict[str, TrajectoryState] = {}
        self._approvals: dict[str, ApprovalRecord] = {}
        self._approval_replays: dict[tuple[str, str], str] = {}
        self._heads: dict[str, LedgerHead] = {}
        self._event_replays: dict[tuple[str, str], tuple[str, TraceEvent]] = {}
        self._lock = RLock()

    def create_run(self, state: TrajectoryState) -> None:
        with self._lock:
            if state.trace_id in self._runs:
                raise TraceSequenceError(f"Trace {state.trace_id} already exists.")
            if state.events or state.next_sequence != 1:
                raise TraceSequenceError(
                    f"Trace {state.trace_id} must start with an empty event list."
                )
            created_at = utc_now()
            self._runs[state.trace_id] = state
            self._heads[state.trace_id] = LedgerHead(
                trace_id=state.trace_id,
                sequence=0,
                event_count=0,
                event_hash=GENESIS_HASH,
                schema_version=LEDGER_SCHEMA_VERSION,
                updated_at=created_at,
            )

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
        idempotency_key: str | None = None,
    ) -> TraceEvent:
        with self._lock:
            stored = self._runs.get(state.trace_id)
            if stored is None:
                raise TraceNotFoundError(f"Trace {state.trace_id} was not found.")
            if stored is not state:
                raise TraceSequenceError(
                    f"Trace {state.trace_id} was updated with a detached state object."
                )
            safe_details = deepcopy(details or {})
            fingerprint: str | None = None
            if idempotency_key is not None:
                try:
                    fingerprint = event_description_fingerprint(
                        trace_id=state.trace_id,
                        event_type=event_type,
                        summary=summary,
                        details=safe_details,
                        agent=agent,
                        tool_name=tool_name,
                        effect_class=effect_class,
                        idempotency_key=idempotency_key,
                    )
                except (TypeError, ValueError) as exc:
                    raise LedgerAppendError(
                        f"Trace {state.trace_id} event could not be canonically hashed."
                    ) from exc
                replay = self._event_replays.get((state.trace_id, idempotency_key))
                if replay is not None:
                    previous_fingerprint, previous_event = replay
                    if previous_fingerprint != fingerprint:
                        raise LedgerIdempotencyConflictError(
                            f"Ledger idempotency key {idempotency_key} was reused "
                            "with different event fields."
                        )
                    return deepcopy(previous_event)

            head = self._heads.get(state.trace_id)
            if head is None:
                raise LedgerAppendError(
                    f"Trace {state.trace_id} has no initialized ledger head."
                )
            expected_sequence = head.sequence + 1
            if state.next_sequence != expected_sequence:
                raise TraceSequenceError(
                    f"Trace {state.trace_id} expected sequence {expected_sequence}, "
                    f"received {state.next_sequence}."
                )
            occurred_at = utc_now()
            unhashed = TraceEvent(
                event_id=f"EVT-{uuid4()}",
                trace_id=state.trace_id,
                sequence=expected_sequence,
                event_type=event_type,
                summary=summary,
                details=safe_details,
                agent=agent,
                tool_name=tool_name,
                effect_class=effect_class,
                occurred_at=occurred_at,
                schema_version=LEDGER_SCHEMA_VERSION,
                previous_hash=head.event_hash,
                event_hash="",
                idempotency_key=idempotency_key,
            )
            try:
                event = replace(unhashed, event_hash=calculate_event_hash(unhashed))
            except (TypeError, ValueError) as exc:
                raise LedgerAppendError(
                    f"Trace {state.trace_id} event could not be canonically hashed."
                ) from exc

            state.events.append(event)
            state.next_sequence = expected_sequence + 1
            self._heads[state.trace_id] = LedgerHead(
                trace_id=state.trace_id,
                sequence=event.sequence,
                event_count=len(state.events),
                event_hash=event.event_hash,
                schema_version=LEDGER_SCHEMA_VERSION,
                updated_at=occurred_at,
            )
            if idempotency_key is not None and fingerprint is not None:
                self._event_replays[(state.trace_id, idempotency_key)] = (
                    fingerprint,
                    event,
                )
            return deepcopy(event)

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

    def get_head(self, trace_id: str) -> LedgerHead:
        with self._lock:
            head = self._heads.get(trace_id)
            if head is None:
                if trace_id not in self._runs:
                    raise TraceNotFoundError(f"Trace {trace_id} was not found.")
                raise LedgerAppendError(f"Trace {trace_id} has no ledger head.")
            return deepcopy(head)

    def verify_trace(self, trace_id: str) -> VerificationResult:
        with self._lock:
            state = self._runs.get(trace_id)
            if state is None:
                raise TraceNotFoundError(f"Trace {trace_id} was not found.")
            head = self._heads.get(trace_id)
            if head is None:
                raise LedgerAppendError(f"Trace {trace_id} has no ledger head.")
            events = deepcopy(state.events)
            retained_head = deepcopy(head)
        return verify_chain(trace_id, events, retained_head)

    def tamper_event_summary_for_demo(
        self,
        trace_id: str,
        sequence: int,
        replacement_summary: str,
    ) -> TamperResult:
        """Alter one terminal trace event without repairing its hashes."""
        with self._lock:
            state = self._runs.get(trace_id)
            if state is None:
                raise TraceNotFoundError(f"Trace {trace_id} was not found.")
            if state.status not in {
                RunStatus.COMPLETED,
                RunStatus.CANCELLED,
                RunStatus.BLOCKED,
            }:
                raise LedgerTamperValidationError(
                    "Only a terminal disposable trace may be tampered with."
                )
            if not replacement_summary.strip():
                raise LedgerTamperValidationError(
                    "The replacement summary must not be empty."
                )
            if sequence < 1 or sequence > len(state.events):
                raise LedgerTamperValidationError(
                    f"Trace {trace_id} has no event at sequence {sequence}."
                )
            index = sequence - 1
            state.events[index] = replace(
                state.events[index], summary=replacement_summary
            )
            return TamperResult(trace_id=trace_id, sequence=sequence, field="summary")

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
            self._heads.clear()
            self._event_replays.clear()
            return removed

    def run_count(self) -> int:
        with self._lock:
            return len(self._runs)
