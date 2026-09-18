import pytest

from packages.domain.enums import EventType
from packages.domain.errors import TraceNotFoundError
from packages.domain.models import TrajectoryState
from packages.ledger import MemoryTraceStore


def test_events_are_monotonic_and_returns_are_copies():
    store = MemoryTraceStore()
    state = TrajectoryState("TR-1", "ORD-8842")
    store.create_run(state)
    store.append_event(state, EventType.RUN_STARTED, "Started")
    store.append_event(state, EventType.RUN_COMPLETED, "Completed")

    events = store.get_events("TR-1")
    assert [event.sequence for event in events] == [1, 2]
    events.clear()
    assert len(store.get_events("TR-1")) == 2


def test_unknown_trace_fails_clearly():
    with pytest.raises(TraceNotFoundError, match="missing"):
        MemoryTraceStore().get_state("missing")


def test_reset_reports_removed_runs():
    store = MemoryTraceStore()
    store.create_run(TrajectoryState("TR-1", "ORD-8842"))
    store.create_run(TrajectoryState("TR-2", "ORD-8842"))

    assert store.reset() == 2
    assert store.run_count() == 0
