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
    ApprovalPersistenceConflictError,
    LedgerAppendError,
    LedgerIdempotencyConflictError,
    LedgerTamperValidationError,
    TraceNotFoundError,
    TraceRevisionConflictError,
    TraceSequenceError,
    EffectReceiptConflictError,
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
from packages.storage.models import (
    EffectReceipt,
    ReplayKind,
    StoredTrace,
    TraceTransition,
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

    name = "memory"

    def __init__(self) -> None:
        self._runs: dict[str, TrajectoryState] = {}
        self._approvals: dict[str, ApprovalRecord] = {}
        self._approval_replays: dict[tuple[str, str], str] = {}
        self._heads: dict[str, LedgerHead] = {}
        self._event_replays: dict[tuple[str, str], tuple[str, TraceEvent]] = {}
        self._effect_receipts: dict[tuple[str, str], EffectReceipt] = {}
        self._lock = RLock()

    def validate_startup(self) -> None:
        return None

    def create_run(self, state: TrajectoryState) -> StoredTrace:
        with self._lock:
            if state.trace_id in self._runs:
                raise TraceSequenceError(f"Trace {state.trace_id} already exists.")
            if state.events or state.next_sequence != 1:
                raise TraceSequenceError(
                    f"Trace {state.trace_id} must start with an empty event list."
                )
            created_at = utc_now()
            state.storage_revision = 0
            self._runs[state.trace_id] = deepcopy(state)
            self._heads[state.trace_id] = LedgerHead(
                trace_id=state.trace_id,
                sequence=0,
                event_count=0,
                event_hash=GENESIS_HASH,
                schema_version=LEDGER_SCHEMA_VERSION,
                updated_at=created_at,
            )
            return StoredTrace(deepcopy(state), state.storage_revision)

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
            self._assert_revision(state, stored)
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
            self._persist_state(state)
            return deepcopy(event)

    def get_state(self, trace_id: str) -> TrajectoryState:
        with self._lock:
            state = self._runs.get(trace_id)
            if state is None:
                raise TraceNotFoundError(f"Trace {trace_id} was not found.")
            return deepcopy(state)

    def get_state_for_update(self, trace_id: str) -> TrajectoryState:
        """Compatibility alias returning a detached optimistic snapshot."""
        return self.get_state(trace_id)

    def load_trace(
        self, trace_id: str, *, consistent: bool = True
    ) -> StoredTrace:
        del consistent
        state = self.get_state(trace_id)
        return StoredTrace(state, state.storage_revision)

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
            terminal_event = bool(state.events) and state.events[-1].event_type in {
                EventType.RUN_COMPLETED,
                EventType.RUN_CANCELLED,
                EventType.RUN_FAILED,
            }
            if state.status not in {
                RunStatus.COMPLETED,
                RunStatus.CANCELLED,
                RunStatus.BLOCKED,
            } and not terminal_event:
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
            state.storage_revision += 1
            return TamperResult(trace_id=trace_id, sequence=sequence, field="summary")

    def append_decision(self, state: TrajectoryState, decision: Decision) -> None:
        with self._lock:
            stored = self._runs.get(state.trace_id)
            if stored is None:
                raise TraceNotFoundError(f"Trace {state.trace_id} was not found.")
            self._assert_revision(state, stored)
            if any(item.decision_id == decision.decision_id for item in state.decisions):
                raise TraceSequenceError(f"Decision {decision.decision_id} already exists.")
            state.decisions.append(decision)
            self._persist_state(state)

    def get_decisions(self, trace_id: str) -> list[Decision]:
        return list(self.get_state(trace_id).decisions)

    def add_approval(
        self, state: TrajectoryState, approval: ApprovalRecord
    ) -> None:
        with self._lock:
            stored = self._runs.get(state.trace_id)
            if stored is None:
                raise TraceNotFoundError(f"Trace {state.trace_id} was not found.")
            self._assert_revision(state, stored)
            if approval.approval_id in self._approvals:
                raise TraceSequenceError(f"Approval {approval.approval_id} already exists.")
            self._approvals[approval.approval_id] = approval
            self._persist_state(state)

    def get_approval(self, approval_id: str) -> ApprovalRecord:
        with self._lock:
            approval = self._approvals.get(approval_id)
            if approval is None:
                raise ApprovalNotFoundError(f"Approval {approval_id} was not found.")
            return deepcopy(approval)

    def replace_approval(self, approval: ApprovalRecord) -> None:
        with self._lock:
            current = self._approvals.get(approval.approval_id)
            if current is None:
                raise ApprovalNotFoundError(f"Approval {approval.approval_id} was not found.")
            # Same-version replacement is retained as an in-memory test seam
            # for binding/expiry tamper tests. Real lifecycle transitions must
            # advance by one; DynamoDB always enforces that distributed CAS.
            if current.version not in {approval.version, approval.version - 1}:
                raise ApprovalPersistenceConflictError(
                    "Approval version changed concurrently."
                )
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

    def get_effect_receipt(
        self, trace_id: str, key_hash: str
    ) -> EffectReceipt | None:
        with self._lock:
            return deepcopy(self._effect_receipts.get((trace_id, key_hash)))

    def put_effect_receipt(self, receipt: EffectReceipt) -> EffectReceipt:
        with self._lock:
            key = (receipt.trace_id, receipt.key_hash)
            existing = self._effect_receipts.get(key)
            if existing is not None:
                if existing.fingerprint != receipt.fingerprint:
                    raise EffectReceiptConflictError(
                        "An effect idempotency key was reused with different arguments."
                    )
                return deepcopy(existing)
            if receipt.trace_id not in self._runs:
                raise TraceNotFoundError(
                    f"Trace {receipt.trace_id} was not found."
                )
            self._effect_receipts[key] = deepcopy(receipt)
            return deepcopy(receipt)

    def commit_transition(self, transition: TraceTransition) -> StoredTrace:
        """Apply one detached optimistic transition atomically in memory."""
        with self._lock:
            stored = self._runs.get(transition.trace_id)
            if stored is None:
                raise TraceNotFoundError(
                    f"Trace {transition.trace_id} was not found."
                )
            if stored.storage_revision != transition.expected_revision:
                raise TraceRevisionConflictError(
                    f"Trace {transition.trace_id} revision changed."
                )
            state = deepcopy(transition.state)
            state.storage_revision = transition.expected_revision
            state.events = deepcopy(stored.events)
            state.decisions = deepcopy(stored.decisions)
            head = self._heads[transition.trace_id]
            for event in transition.events:
                if event.sequence != head.sequence + 1:
                    raise TraceSequenceError(
                        f"Trace {transition.trace_id} received a stale event sequence."
                    )
                if event.previous_hash != head.event_hash:
                    raise TraceSequenceError(
                        f"Trace {transition.trace_id} received a stale previous hash."
                    )
                if calculate_event_hash(event) != event.event_hash:
                    raise LedgerAppendError("Transition event hash is invalid.")
                state.events.append(deepcopy(event))
                state.next_sequence = event.sequence + 1
                head = LedgerHead(
                    trace_id=transition.trace_id,
                    sequence=event.sequence,
                    event_count=len(state.events),
                    event_hash=event.event_hash,
                    schema_version=LEDGER_SCHEMA_VERSION,
                    updated_at=event.occurred_at,
                )
            for decision in transition.decisions:
                if any(
                    item.decision_id == decision.decision_id
                    for item in state.decisions
                ):
                    raise TraceSequenceError(
                        f"Decision {decision.decision_id} already exists."
                    )
                state.decisions.append(deepcopy(decision))
            for approval in transition.approval_upserts:
                self._approvals[approval.approval_id] = deepcopy(approval)
            for replay in transition.replay_records:
                if replay.kind == ReplayKind.APPROVAL:
                    self._approval_replays[
                        (replay.result_reference, replay.key_hash)
                    ] = replay.fingerprint
            for receipt in transition.effect_receipts:
                existing = self._effect_receipts.get(
                    (receipt.trace_id, receipt.key_hash)
                )
                if existing is not None and existing != receipt:
                    raise TraceSequenceError("Effect receipt already exists.")
                self._effect_receipts[
                    (receipt.trace_id, receipt.key_hash)
                ] = deepcopy(receipt)
            self._heads[transition.trace_id] = head
            self._persist_state(state)
            return StoredTrace(deepcopy(state), state.storage_revision)

    def reset(self) -> int:
        with self._lock:
            removed = len(self._runs)
            self._runs.clear()
            self._approvals.clear()
            self._approval_replays.clear()
            self._heads.clear()
            self._event_replays.clear()
            self._effect_receipts.clear()
            return removed

    def reset_demo_namespace(self) -> int:
        return self.reset()

    def run_count(self) -> int:
        with self._lock:
            return len(self._runs)

    def describe(self) -> dict[str, object]:
        return {
            "storage_backend": self.name,
            "storage_mode": "memory_hash_chain",
            "consistent_reads": True,
        }

    @staticmethod
    def _assert_revision(
        state: TrajectoryState, stored: TrajectoryState
    ) -> None:
        if state.storage_revision != stored.storage_revision:
            raise TraceRevisionConflictError(
                f"Trace {state.trace_id} revision changed."
            )

    def _persist_state(self, state: TrajectoryState) -> None:
        state.storage_revision += 1
        self._runs[state.trace_id] = deepcopy(state)
