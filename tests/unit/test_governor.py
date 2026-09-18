import pytest

from fixtures import FixtureLoader
from packages.domain.enums import AgentName, EventType
from packages.domain.errors import ToolOwnershipError
from packages.domain.models import TrajectoryState
from packages.governor import ObserverGovernor
from packages.ledger import MemoryTraceStore
from packages.tools import build_tool_registry


def build_governor():
    store = MemoryTraceStore()
    registry, _ = build_tool_registry(FixtureLoader())
    return ObserverGovernor(registry, store), store


def test_tool_call_records_attempt_observation_and_success():
    governor, store = build_governor()
    state = TrajectoryState("TR-1", "ORD-8842")
    store.create_run(state)

    result = governor.execute_tool(
        state, AgentName.INVENTORY, "get_order", order_id="ORD-8842"
    )

    assert result.order_id == "ORD-8842"
    assert [event.event_type for event in state.events] == [
        EventType.TOOL_ATTEMPTED,
        EventType.GOVERNANCE_OBSERVED,
        EventType.TOOL_SUCCEEDED,
    ]
    assert state.events[1].details["enforced"] is False


def test_agent_cannot_use_another_agents_tool():
    governor, store = build_governor()
    state = TrajectoryState("TR-1", "ORD-8842")
    store.create_run(state)

    with pytest.raises(ToolOwnershipError):
        governor.execute_tool(
            state, AgentName.CARRIER, "get_order", order_id="ORD-8842"
        )
