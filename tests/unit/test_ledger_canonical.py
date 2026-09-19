from datetime import datetime, timezone
from enum import Enum

import pytest

from packages.domain.enums import AgentName, EffectClass, EventType
from packages.domain.models import TraceEvent
from packages.ledger.canonical import (
    GENESIS_HASH,
    calculate_event_hash,
    canonical_json,
    hash_payload,
    normalize,
)


class DemoEnum(str, Enum):
    VALUE = "value"


def test_canonical_hash_is_independent_of_mapping_insertion_order():
    first = {"b": 2, "a": {"z": "नमस्ते", "x": [1, True, None]}}
    second = {"a": {"x": [1, True, None], "z": "नमस्ते"}, "b": 2}

    assert canonical_json(first) == canonical_json(second)
    assert hash_payload(first) == hash_payload(second)
    assert hash_payload(first) == (
        "sha256:d0749b09a034eeb75e02cd0211b4dde5"
        "2824c544b2e5ba2a0359949b2f84b958"
    )


def test_canonical_normalization_handles_enum_and_utc_datetime():
    value = {
        "kind": DemoEnum.VALUE,
        "when": datetime(2026, 9, 19, 12, 30, 1, 42, tzinfo=timezone.utc),
    }

    assert normalize(value) == {
        "kind": "value",
        "when": "2026-09-19T12:30:01.000042Z",
    }


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_float_is_rejected(value):
    with pytest.raises(ValueError, match="Non-finite"):
        canonical_json({"value": value})


def test_set_and_naive_datetime_are_rejected():
    with pytest.raises(TypeError, match="Sets"):
        canonical_json({"values": {1, 2}})
    with pytest.raises(ValueError, match="timezone"):
        canonical_json({"when": datetime(2026, 9, 19)})


def test_list_order_changes_hash():
    assert hash_payload({"values": [1, 2]}) != hash_payload({"values": [2, 1]})


def test_complete_ledger_event_hash_is_pinned_by_fixed_vector():
    event = TraceEvent(
        event_id="EVT-FIXED",
        trace_id="TR-FIXED",
        sequence=1,
        event_type=EventType.RUN_STARTED,
        summary="Started",
        details={"mode": "enforce"},
        agent=AgentName.INVENTORY,
        tool_name="read_inventory",
        effect_class=EffectClass.READ,
        occurred_at=datetime(2026, 9, 19, tzinfo=timezone.utc),
        schema_version="ledger-event-v1",
        previous_hash=GENESIS_HASH,
        event_hash="",
        idempotency_key="run:TR-FIXED:started",
    )

    assert calculate_event_hash(event) == (
        "sha256:ed8b12414de1d8b812e8e8b9e07c91a3"
        "1c45f95f693f1a7aaab375cc8cdceaed"
    )
