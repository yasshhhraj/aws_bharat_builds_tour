"""Observation-only governed tool boundary for Checkpoint 1."""

from __future__ import annotations

from typing import Any

from packages.domain.enums import AgentName, EventType
from packages.domain.errors import (
    ManifestError,
    ToolExecutionError,
    ToolOwnershipError,
)
from packages.domain.models import TrajectoryState, to_primitive
from packages.storage.protocol import TraceRepository
from packages.tools.registry import ToolRegistry


class ObserverGovernor:
    def __init__(
        self,
        registry: ToolRegistry,
        store: TraceRepository,
        *,
        max_tool_calls: int = 20,
    ) -> None:
        self.registry = registry
        self.store = store
        self.max_tool_calls = max_tool_calls

    def execute_tool(
        self,
        state: TrajectoryState,
        agent: AgentName,
        tool_name: str,
        **arguments: Any,
    ) -> Any:
        definition = self.registry.get_definition(tool_name)
        if definition.owner != agent:
            raise ToolOwnershipError(
                f"Agent {agent.value} does not own tool {tool_name}."
            )
        if state.tool_call_count >= self.max_tool_calls:
            raise ToolExecutionError(
                f"Trace {state.trace_id} exceeded the tool-call limit."
            )
        state.tool_call_count += 1
        safe_arguments = self._safe_arguments(tool_name, arguments)
        self.store.append_event(
            state,
            EventType.TOOL_ATTEMPTED,
            f"{agent.value} attempted {tool_name}.",
            agent=agent,
            tool_name=tool_name,
            effect_class=definition.effect_class,
            details={"arguments": safe_arguments},
        )
        self.store.append_event(
            state,
            EventType.GOVERNANCE_OBSERVED,
            f"Observed {tool_name}; Checkpoint 1 does not enforce business policy.",
            agent=agent,
            tool_name=tool_name,
            effect_class=definition.effect_class,
            details={
                "outcome": "ALLOW",
                "enforced": False,
                "reason_code": "CHECKPOINT_1_OBSERVE_ONLY",
            },
        )
        try:
            result = self.registry.execute(tool_name, arguments)
        except ManifestError as exc:
            self._record_failure(state, agent, tool_name, definition.effect_class, exc.message)
            raise
        except Exception as exc:
            message = f"Tool {tool_name} failed unexpectedly."
            self._record_failure(state, agent, tool_name, definition.effect_class, message)
            raise ToolExecutionError(message) from exc
        self.store.append_event(
            state,
            EventType.TOOL_SUCCEEDED,
            f"{tool_name} completed successfully.",
            agent=agent,
            tool_name=tool_name,
            effect_class=definition.effect_class,
            details={"result": to_primitive(result)},
        )
        return result

    def _record_failure(self, state, agent, tool_name, effect_class, message) -> None:
        self.store.append_event(
            state,
            EventType.TOOL_FAILED,
            message,
            agent=agent,
            tool_name=tool_name,
            effect_class=effect_class,
            details={"error": message},
        )

    @staticmethod
    def _safe_arguments(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        safe = to_primitive(arguments)
        if tool_name == "write_tracking_outbox" and "message" in safe:
            safe["message"] = "[synthetic tracking message]"
        return safe
