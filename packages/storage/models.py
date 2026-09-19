"""Storage-layer contracts that do not depend on any database SDK."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from packages.domain.models import (
    ApprovalRecord,
    Decision,
    TraceEvent,
    TrajectoryState,
    utc_now,
)


STATE_SCHEMA_VERSION = "trace-state-v1"
STORAGE_SCHEMA_VERSION = "manifest-storage-v1"
MAX_PERSISTED_ITEM_BYTES = 350_000


class ReplayKind(str, Enum):
    EVENT = "event"
    APPROVAL = "approval"


@dataclass(frozen=True, slots=True)
class StoredTrace:
    """A detached state snapshot and its optimistic storage revision."""

    state: TrajectoryState
    revision: int

    def __post_init__(self) -> None:
        if self.revision < 0:
            raise ValueError("A stored trace revision cannot be negative.")


@dataclass(frozen=True, slots=True)
class ReplayRecord:
    trace_id: str
    kind: ReplayKind
    key_hash: str
    fingerprint: str
    result_reference: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.trace_id or not self.key_hash or not self.fingerprint:
            raise ValueError("A replay record requires trace, key, and fingerprint values.")


@dataclass(frozen=True, slots=True)
class EffectReceipt:
    trace_id: str
    tool_name: str
    key_hash: str
    fingerprint: str
    result: dict[str, Any]
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.trace_id or not self.tool_name or not self.key_hash:
            raise ValueError("An effect receipt requires trace, tool, and key values.")


@dataclass(frozen=True, slots=True)
class TraceTransition:
    """All records that must commit with one optimistic state transition."""

    trace_id: str
    expected_revision: int
    state: TrajectoryState
    events: tuple[TraceEvent, ...] = ()
    decisions: tuple[Decision, ...] = ()
    approval_upserts: tuple[ApprovalRecord, ...] = ()
    replay_records: tuple[ReplayRecord, ...] = ()
    effect_receipts: tuple[EffectReceipt, ...] = ()

    def __post_init__(self) -> None:
        if self.expected_revision < 0:
            raise ValueError("An expected trace revision cannot be negative.")
        if self.state.trace_id != self.trace_id:
            raise ValueError("Transition state does not belong to the target trace.")
        records = (
            *self.events,
            *self.decisions,
            *self.approval_upserts,
            *self.replay_records,
            *self.effect_receipts,
        )
        if any(item.trace_id != self.trace_id for item in records):
            raise ValueError("Every transition record must belong to the target trace.")
