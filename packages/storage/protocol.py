"""Database-independent storage ports used by the Manifest runtime."""

from __future__ import annotations

from typing import Any, Protocol

from packages.domain.enums import (
    AgentName,
    ApprovalStatus,
    EffectClass,
    EventType,
)
from packages.domain.models import (
    ApprovalRecord,
    Decision,
    LedgerHead,
    TamperResult,
    TraceEvent,
    TrajectoryState,
    VerificationResult,
)

from .models import EffectReceipt, StoredTrace, TraceTransition


class TraceRepository(Protocol):
    name: str

    def validate_startup(self) -> None: ...

    def create_run(self, state: TrajectoryState) -> StoredTrace: ...

    def load_trace(
        self, trace_id: str, *, consistent: bool = True
    ) -> StoredTrace: ...

    def commit_transition(self, transition: TraceTransition) -> StoredTrace: ...

    def get_state(self, trace_id: str) -> TrajectoryState: ...

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
    ) -> TraceEvent: ...

    def append_decision(
        self, state: TrajectoryState, decision: Decision
    ) -> None: ...

    def get_events(self, trace_id: str) -> list[TraceEvent]: ...

    def get_decisions(self, trace_id: str) -> list[Decision]: ...

    def get_head(self, trace_id: str) -> LedgerHead: ...

    def verify_trace(self, trace_id: str) -> VerificationResult: ...

    def get_approval(self, approval_id: str) -> ApprovalRecord: ...

    def add_approval(
        self, state: TrajectoryState, approval: ApprovalRecord
    ) -> None: ...

    def replace_approval(self, approval: ApprovalRecord) -> None: ...

    def list_approvals(
        self,
        trace_id: str | None = None,
        status: ApprovalStatus | None = None,
    ) -> list[ApprovalRecord]: ...

    def get_approval_replay_fingerprint(
        self, approval_id: str, idempotency_key: str
    ) -> str | None: ...

    def record_approval_replay(
        self, approval_id: str, idempotency_key: str, fingerprint: str
    ) -> None: ...

    def get_effect_receipt(
        self, trace_id: str, key_hash: str
    ) -> EffectReceipt | None: ...

    def put_effect_receipt(self, receipt: EffectReceipt) -> EffectReceipt: ...

    def tamper_event_summary_for_demo(
        self, trace_id: str, sequence: int, replacement_summary: str
    ) -> TamperResult: ...

    def reset_demo_namespace(self) -> int: ...

    def describe(self) -> dict[str, object]: ...
