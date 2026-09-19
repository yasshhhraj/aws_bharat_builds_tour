from dataclasses import replace
from datetime import datetime, timezone

import pytest

from packages.domain.enums import EventType, RunStatus
from packages.domain.errors import TraceRevisionConflictError
from packages.domain.models import TraceEvent, TrajectoryState
from packages.ledger import GENESIS_HASH, MemoryTraceStore, calculate_event_hash
from packages.storage.models import TraceTransition


def test_memory_store_owns_a_copy_instead_of_the_callers_live_object():
    store = MemoryTraceStore()
    state = TrajectoryState("TR-COPY", "ORD-8842")
    store.create_run(state)

    state.status = RunStatus.COMPLETED

    assert store.get_state(state.trace_id).status == RunStatus.PENDING


def test_two_detached_snapshots_use_optimistic_revision_checks():
    store = MemoryTraceStore()
    store.create_run(TrajectoryState("TR-REVISION", "ORD-8842"))
    first = store.load_trace("TR-REVISION")
    stale = store.load_trace("TR-REVISION")

    store.append_event(first.state, EventType.RUN_STARTED, "Started")

    with pytest.raises(TraceRevisionConflictError, match="revision changed"):
        store.append_event(stale.state, EventType.RUN_STARTED, "Stale")


def test_explicit_transition_commits_event_head_and_state_once():
    store = MemoryTraceStore()
    stored = store.create_run(TrajectoryState("TR-TRANSITION", "ORD-8842"))
    occurred_at = datetime(2026, 9, 19, tzinfo=timezone.utc)
    unhashed = TraceEvent(
        event_id="EVT-TRANSITION-1",
        trace_id=stored.state.trace_id,
        sequence=1,
        event_type=EventType.RUN_STARTED,
        summary="Started",
        occurred_at=occurred_at,
        previous_hash=GENESIS_HASH,
    )
    event = replace(unhashed, event_hash=calculate_event_hash(unhashed))
    state = stored.state
    state.status = RunStatus.RUNNING

    committed = store.commit_transition(
        TraceTransition(
            trace_id=state.trace_id,
            expected_revision=stored.revision,
            state=state,
            events=(event,),
        )
    )

    assert committed.revision == 1
    assert committed.state.status == RunStatus.RUNNING
    assert committed.state.events == [event]
    assert store.get_head(state.trace_id).event_hash == event.event_hash
    assert store.verify_trace(state.trace_id).valid is True
