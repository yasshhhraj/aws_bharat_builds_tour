from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json

import pytest

from apps.runtime.service import build_run_service
from packages.domain.errors import (
    ItemSizeLimitError,
    SerializationVersionError,
    TracePersistenceError,
)
from packages.ledger.canonical import calculate_event_hash
from packages.storage.codec import (
    assert_item_size,
    decode_approval_json,
    decode_decision_json,
    decode_effect_json,
    decode_event_json,
    decode_head_json,
    decode_replay_json,
    decode_state_json,
    encode_approval_json,
    encode_decision_json,
    encode_effect_json,
    encode_event_json,
    encode_head_json,
    encode_replay_json,
    encode_state_json,
)
from packages.storage.keyspace import opaque_key_hash
from packages.storage.models import EffectReceipt, ReplayKind, ReplayRecord


def pending_fixture():
    service = build_run_service()
    run = service.start_run("ORD-8842", "enforce", "adversarial")
    state = service.store.get_state(run.trace_id)
    approval = service.get_approval(run.pending_approval_id)
    head = service.store.get_head(run.trace_id)
    return state, approval, head


def test_complex_trace_state_round_trips_without_embedding_history():
    state, _, _ = pending_fixture()
    document = encode_state_json(state)

    payload = json.loads(document)["payload"]
    assert "events" not in payload
    assert "decisions" not in payload
    assert payload["mandate"]["allowed_effect_classes"] == sorted(
        payload["mandate"]["allowed_effect_classes"]
    )

    restored = decode_state_json(
        document,
        events=tuple(state.events),
        decisions=tuple(state.decisions),
    )
    assert restored == state


def test_event_decision_approval_and_head_round_trip_exactly():
    state, approval, head = pending_fixture()
    event = state.events[-1]
    decision = state.decisions[-1]

    restored_event = decode_event_json(encode_event_json(event))
    assert restored_event == event
    assert calculate_event_hash(restored_event) == event.event_hash
    assert decode_decision_json(encode_decision_json(decision)) == decision
    assert decode_approval_json(encode_approval_json(approval)) == approval
    assert decode_head_json(encode_head_json(head)) == head


def test_replay_and_effect_receipts_round_trip_with_utc_timestamps():
    created_at = datetime(2026, 9, 19, 8, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    key_hash = opaque_key_hash("approval-command-1")
    replay = ReplayRecord(
        trace_id="TR-1",
        kind=ReplayKind.APPROVAL,
        key_hash=key_hash,
        fingerprint="sha256:fingerprint",
        result_reference="APR-1",
        created_at=created_at,
    )
    receipt = EffectReceipt(
        trace_id="TR-1",
        tool_name="confirm_freight_booking",
        key_hash=key_hash,
        fingerprint="sha256:effect",
        result={"confirmation_id": "CONFIRM-1", "amount_minor": 90000},
        created_at=created_at,
    )

    restored_replay = decode_replay_json(encode_replay_json(replay))
    restored_receipt = decode_effect_json(encode_effect_json(receipt))
    assert restored_replay.created_at == created_at
    assert restored_receipt.created_at == created_at
    assert restored_replay == replay
    assert restored_receipt == receipt


def test_unknown_storage_and_record_versions_fail_closed():
    state, _, _ = pending_fixture()
    envelope = json.loads(encode_state_json(state))

    wrong_storage = dict(envelope, storage_schema_version="future-storage")
    with pytest.raises(SerializationVersionError, match="storage schema"):
        decode_state_json(json.dumps(wrong_storage))

    wrong_record = dict(envelope, record_schema_version="future-state")
    with pytest.raises(SerializationVersionError, match="record schema"):
        decode_state_json(json.dumps(wrong_record))


def test_invalid_json_and_naive_datetimes_are_rejected():
    with pytest.raises(TracePersistenceError, match="valid JSON"):
        decode_state_json("not-json")

    receipt = EffectReceipt(
        trace_id="TR-1",
        tool_name="confirm_freight_booking",
        key_hash=opaque_key_hash("effect-1"),
        fingerprint="sha256:fingerprint",
        result={},
        created_at=datetime(2026, 9, 19),
    )
    with pytest.raises(TracePersistenceError, match="timezone"):
        encode_effect_json(receipt)


def test_item_size_guard_uses_utf8_bytes():
    with pytest.raises(ItemSizeLimitError, match="maximum"):
        assert_item_size("न" * 10, "test item", maximum_bytes=20)


def test_corrupted_enum_payload_is_reported_as_persistence_error():
    state, _, _ = pending_fixture()
    envelope = json.loads(encode_state_json(state))
    envelope["payload"]["status"] = "not-a-status"

    with pytest.raises(TracePersistenceError, match="trace state payload"):
        decode_state_json(json.dumps(envelope))


def test_codec_does_not_mutate_source_state():
    state, _, _ = pending_fixture()
    original = replace(state.prepared_actions[next(iter(state.prepared_actions))])

    encode_state_json(state)

    assert state.prepared_actions[original.prepared_action_id] == original
