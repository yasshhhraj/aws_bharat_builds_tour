"""Thread-safe in-memory run and ordered event storage."""

from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Any

from packages.domain.enums import AgentName, EffectClass, EventType
from packages.domain.errors import TraceNotFoundError, TraceSequenceError
from packages.domain.models import TraceEvent, TrajectoryState


class MemoryTraceStore:
    """Checkpoint 1 storage port; later replaced by a hash-chain ledger."""

    def __init__(self) -> None:
        self._runs: dict[str, TrajectoryState] = {}
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

    def get_events(self, trace_id: str) -> list[TraceEvent]:
        return list(self.get_state(trace_id).events)

    def reset(self) -> int:
        with self._lock:
            removed = len(self._runs)
            self._runs.clear()
            return removed

    def run_count(self) -> int:
        with self._lock:
            return len(self._runs)
