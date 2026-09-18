"""Bounded sequential orchestration for the four deterministic agents."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

from packages.domain.enums import EventType, RunStatus
from packages.domain.errors import ManifestError
from packages.domain.models import TrajectoryState
from packages.governor import ObserverGovernor
from packages.ledger import MemoryTraceStore

from .agents.base import BaseAgent


class ShipmentOrchestrator:
    def __init__(
        self,
        agents: Sequence[BaseAgent],
        governor: ObserverGovernor,
        store: MemoryTraceStore,
    ) -> None:
        self.agents = tuple(agents)
        self.governor = governor
        self.store = store

    def run(self, order_id: str) -> TrajectoryState:
        state = TrajectoryState(
            trace_id=f"TR-{uuid4()}",
            order_id=order_id,
            status=RunStatus.RUNNING,
        )
        self.store.create_run(state)
        self.store.append_event(
            state,
            EventType.RUN_STARTED,
            f"Started deterministic journey for {order_id}.",
            details={"runtime_mode": "deterministic", "governor_mode": "observe_only"},
        )
        try:
            for agent in self.agents:
                state.current_agent = agent.name
                self.store.append_event(
                    state,
                    EventType.AGENT_STARTED,
                    f"{agent.name.value} agent started.",
                    agent=agent.name,
                )
                summary = agent.run(state, self.governor)
                self.store.append_event(
                    state,
                    EventType.AGENT_COMPLETED,
                    summary,
                    agent=agent.name,
                )
            state.status = RunStatus.COMPLETED
            state.current_agent = None
            self.store.append_event(
                state,
                EventType.RUN_COMPLETED,
                f"Completed deterministic journey for {order_id}.",
            )
        except Exception as exc:
            state.status = RunStatus.FAILED
            state.current_agent = None
            state.error = (
                exc.message if isinstance(exc, ManifestError) else "Run failed unexpectedly."
            )
            self.store.append_event(
                state,
                EventType.RUN_FAILED,
                state.error,
                details={"error_code": getattr(exc, "code", "UNEXPECTED_ERROR")},
            )
        return state
