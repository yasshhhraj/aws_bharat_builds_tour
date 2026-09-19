from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor

import pytest

from packages.domain.enums import EventType, RunStatus
from packages.domain.errors import LedgerAppendError, LedgerIdempotencyConflictError
from packages.domain.models import TrajectoryState
from packages.ledger import GENESIS_HASH, MemoryTraceStore, calculate_event_hash, verify_chain


def build_store_with_events(trace_id="TR-CHAIN"):
    store = MemoryTraceStore()
    state = TrajectoryState(trace_id, "ORD-8842")
    store.create_run(state)
    first = store.append_event(state, EventType.RUN_STARTED, "Started")
    second = store.append_event(state, EventType.RUN_COMPLETED, "Completed")
    return store, state, first, second


def test_events_link_from_genesis_and_head_tracks_last_event():
    store, state, first, second = build_store_with_events()

    assert first.sequence == 1
    assert first.previous_hash == GENESIS_HASH
    assert first.event_hash == calculate_event_hash(first)
    assert second.sequence == 2
    assert second.previous_hash == first.event_hash
    assert second.event_hash == calculate_event_hash(second)
    assert state.next_sequence == 3

    head = store.get_head(state.trace_id)
    assert head.sequence == 2
    assert head.event_count == 2
    assert head.event_hash == second.event_hash
    assert store.verify_trace(state.trace_id).valid is True


def test_idempotent_append_returns_original_without_advancing_chain():
    store = MemoryTraceStore()
    state = TrajectoryState("TR-IDEMPOTENT", "ORD-8842")
    store.create_run(state)

    first = store.append_event(
        state,
        EventType.RUN_STARTED,
        "Started",
        details={"mode": "enforce"},
        idempotency_key="run:TR-IDEMPOTENT:started",
    )
    replay = store.append_event(
        state,
        EventType.RUN_STARTED,
        "Started",
        details={"mode": "enforce"},
        idempotency_key="run:TR-IDEMPOTENT:started",
    )

    assert replay == first
    assert len(store.get_events(state.trace_id)) == 1
    assert state.next_sequence == 2
    assert store.get_head(state.trace_id).event_hash == first.event_hash


def test_conflicting_idempotent_append_is_rejected():
    store = MemoryTraceStore()
    state = TrajectoryState("TR-CONFLICT", "ORD-8842")
    store.create_run(state)
    store.append_event(
        state,
        EventType.RUN_STARTED,
        "Started",
        idempotency_key="same-key",
    )

    with pytest.raises(LedgerIdempotencyConflictError):
        store.append_event(
            state,
            EventType.RUN_STARTED,
            "Different",
            idempotency_key="same-key",
        )


def test_same_idempotency_key_is_isolated_per_trace():
    store = MemoryTraceStore()
    first_state = TrajectoryState("TR-A", "ORD-8842")
    second_state = TrajectoryState("TR-B", "ORD-8842")
    store.create_run(first_state)
    store.create_run(second_state)

    first = store.append_event(
        first_state, EventType.RUN_STARTED, "A", idempotency_key="run:started"
    )
    second = store.append_event(
        second_state, EventType.RUN_STARTED, "B", idempotency_key="run:started"
    )

    assert first.trace_id != second.trace_id
    assert first.event_hash != second.event_hash


def test_verifier_reports_first_modified_event_without_repairing_it():
    store, state, _, _ = build_store_with_events()
    state.status = RunStatus.COMPLETED
    before_head = store.get_head(state.trace_id)
    store.tamper_event_summary_for_demo(state.trace_id, 2, "Altered")

    result = store.verify_trace(state.trace_id)
    assert result.valid is False
    assert result.first_bad_sequence == 2
    assert result.failure_code == "EVENT_HASH_MISMATCH"
    assert store.get_events(state.trace_id)[1].summary == "Altered"
    assert store.get_head(state.trace_id) == before_head


def test_verifier_detects_delete_reorder_duplicate_and_truncation():
    store, state, _, _ = build_store_with_events()
    events = store.get_events(state.trace_id)
    head = store.get_head(state.trace_id)

    deleted = verify_chain(state.trace_id, [events[1]], head)
    reordered = verify_chain(state.trace_id, list(reversed(events)), head)
    duplicated = verify_chain(state.trace_id, [events[0], events[0], events[1]], head)
    truncated = verify_chain(state.trace_id, events[:-1], head)

    assert deleted.failure_code == "SEQUENCE_MISMATCH"
    assert reordered.failure_code == "SEQUENCE_MISMATCH"
    assert duplicated.failure_code == "SEQUENCE_MISMATCH"
    assert truncated.failure_code == "EVENT_COUNT_MISMATCH"


def test_verifier_detects_changed_head():
    store, state, _, _ = build_store_with_events()
    events = store.get_events(state.trace_id)
    head = replace(store.get_head(state.trace_id), event_hash=GENESIS_HASH)

    result = verify_chain(state.trace_id, events, head)
    assert result.valid is False
    assert result.failure_code == "HEAD_HASH_MISMATCH"


def test_reset_clears_heads_and_event_replays():
    store = MemoryTraceStore()
    state = TrajectoryState("TR-RESET", "ORD-8842")
    store.create_run(state)
    store.append_event(
        state, EventType.RUN_STARTED, "Started", idempotency_key="reset-key"
    )
    assert store.reset() == 1

    fresh = TrajectoryState("TR-RESET", "ORD-8842")
    store.create_run(fresh)
    event = store.append_event(
        fresh, EventType.RUN_STARTED, "Fresh", idempotency_key="reset-key"
    )
    assert event.sequence == 1
    assert event.summary == "Fresh"


def test_concurrent_appends_produce_one_contiguous_valid_chain():
    store = MemoryTraceStore()
    state = TrajectoryState("TR-CONCURRENT", "ORD-8842")
    store.create_run(state)

    def append(number):
        return store.append_event(
            state,
            EventType.AGENT_STARTED,
            f"Event {number}",
            idempotency_key=f"concurrent:{number}",
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(append, range(40)))

    events = store.get_events(state.trace_id)
    assert [item.sequence for item in events] == list(range(1, 41))
    assert len({item.event_id for item in events}) == 40
    assert store.verify_trace(state.trace_id).valid is True


def test_unsupported_detail_fails_with_controlled_ledger_error():
    store = MemoryTraceStore()
    state = TrajectoryState("TR-BAD-DETAIL", "ORD-8842")
    store.create_run(state)

    with pytest.raises(LedgerAppendError):
        store.append_event(
            state,
            EventType.RUN_STARTED,
            "Started",
            details={"unsupported": {"unordered"}},
            idempotency_key="bad-detail",
        )

    assert store.get_events(state.trace_id) == []
    assert store.get_head(state.trace_id).sequence == 0
