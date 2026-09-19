from datetime import datetime, timezone

import pytest

from packages.domain.enums import EventType
from packages.domain.models import TraceEvent, TrajectoryState
from packages.storage.models import StoredTrace, TraceTransition


def test_stored_trace_rejects_negative_revision():
    with pytest.raises(ValueError, match="negative"):
        StoredTrace(TrajectoryState("TR-1", "ORD-8842"), -1)


def test_transition_rejects_detached_state_and_records():
    with pytest.raises(ValueError, match="target trace"):
        TraceTransition(
            trace_id="TR-1",
            expected_revision=0,
            state=TrajectoryState("TR-2", "ORD-8842"),
        )

    event = TraceEvent(
        event_id="EVT-1",
        trace_id="TR-2",
        sequence=1,
        event_type=EventType.RUN_STARTED,
        summary="Started",
        occurred_at=datetime(2026, 9, 19, tzinfo=timezone.utc),
    )
    with pytest.raises(ValueError, match="Every transition record"):
        TraceTransition(
            trace_id="TR-1",
            expected_revision=0,
            state=TrajectoryState("TR-1", "ORD-8842"),
            events=(event,),
        )
