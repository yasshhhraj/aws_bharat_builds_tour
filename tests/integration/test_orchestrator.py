import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from apps.runtime.agents import InventoryAgent
from apps.runtime.agents.base import BaseAgent
from apps.runtime.orchestrator import ShipmentOrchestrator
from apps.runtime.service import build_run_service
from fixtures import FixtureLoader
from packages.domain.enums import AgentName, EventType, RunStatus
from packages.domain.errors import NoSuitableVehicleError
from packages.domain.models import TrajectoryState
from packages.governor import ManifestGovernor
from packages.ledger import MemoryTraceStore
from packages.policy import PythonReferencePolicyEngine
from packages.tools import build_tool_registry


EXPECTED_PATH = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "expected"
    / "ORD-8842-events.json"
)


def test_complete_benign_journey_matches_expected_contract():
    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    service = build_run_service()

    summary = service.start_run("ORD-8842")
    events = service.get_events(summary.trace_id)

    assert summary.status == RunStatus.COMPLETED
    assert summary.selected_vehicle_id == expected["selected_vehicle_id"]
    assert summary.selected_carrier_id == expected["selected_carrier_id"]
    assert summary.selected_amount_minor == expected["selected_amount_minor"]
    assert summary.notification_id == "NOTIFY-ORD-8842"

    completed_agents = [
        event.agent.value
        for event in events
        if event.event_type == EventType.AGENT_COMPLETED
    ]
    attempted_tools = [
        event.tool_name
        for event in events
        if event.event_type == EventType.TOOL_ATTEMPTED
    ]
    assert completed_agents == expected["agent_order"]
    assert attempted_tools == expected["tool_order"]
    assert [event.sequence for event in events] == list(range(1, len(events) + 1))


def test_every_attempt_has_decision_and_success():
    service = build_run_service()
    summary = service.start_run("ORD-8842")
    events = service.get_events(summary.trace_id)

    attempts = [event for event in events if event.event_type == EventType.TOOL_ATTEMPTED]
    observed = [event for event in events if event.event_type == EventType.POLICY_DECIDED]
    successes = [event for event in events if event.event_type == EventType.TOOL_SUCCEEDED]
    assert len(attempts) == len(observed) == len(successes) == 9


def test_two_runs_do_not_share_state_or_events():
    service = build_run_service()
    first = service.start_run("ORD-8842")
    second = service.start_run("ORD-8842")

    assert first.trace_id != second.trace_id
    first_events = service.get_events(first.trace_id)
    second_events = service.get_events(second.trace_id)
    assert all(event.trace_id == first.trace_id for event in first_events)
    assert all(event.trace_id == second.trace_id for event in second_events)
    assert first_events is not second_events


def test_two_concurrent_runs_do_not_share_state_or_events():
    service = build_run_service()
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(service.start_run, "ORD-8842") for _ in range(2)]
    summaries = [future.result() for future in futures]

    assert summaries[0].trace_id != summaries[1].trace_id
    for summary in summaries:
        events = service.get_events(summary.trace_id)
        assert summary.status == RunStatus.COMPLETED
        assert all(event.trace_id == summary.trace_id for event in events)


class FailingDispatchAgent(BaseAgent):
    name = AgentName.DISPATCH

    def run(self, state: TrajectoryState, governor: ManifestGovernor) -> str:
        raise NoSuitableVehicleError("No suitable vehicle is available.")


def test_failed_run_preserves_prior_events_and_stops_later_agents():
    loader = FixtureLoader()
    store = MemoryTraceStore()
    registry, _ = build_tool_registry(loader)
    governor = ManifestGovernor(registry, store, PythonReferencePolicyEngine(), loader)
    orchestrator = ShipmentOrchestrator(
        [InventoryAgent(), FailingDispatchAgent()], governor, store
    )

    state = orchestrator.run("ORD-8842")
    event_types = [event.event_type for event in state.events]

    assert state.status == RunStatus.FAILED
    assert state.error == "No suitable vehicle is available."
    assert EventType.AGENT_COMPLETED in event_types
    assert event_types[-1] == EventType.RUN_FAILED
