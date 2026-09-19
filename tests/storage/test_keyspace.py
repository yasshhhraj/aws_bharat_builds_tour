from datetime import datetime, timezone

import pytest

from packages.domain.errors import StorageConfigurationError
from packages.storage.keyspace import (
    approval_pointer_pk,
    approval_replay_sk,
    decision_sk,
    effect_sk,
    event_replay_sk,
    event_sk,
    namespace_approval_sk,
    namespace_pk,
    namespace_trace_sk,
    opaque_key_hash,
    trace_pk,
    validate_namespace,
)


def test_trace_and_sequence_keys_are_deterministic_and_sort_numerically():
    assert trace_pk("TR-8842") == "TRACE#TR-8842"
    assert event_sk(2) == "EVENT#000000000002"
    assert event_sk(10) == "EVENT#000000000010"
    assert event_sk(2) < event_sk(10)


def test_decision_and_approval_pointer_keys_are_stable():
    occurred_at = datetime(2026, 9, 19, 5, 30, 1, 42, tzinfo=timezone.utc)
    assert decision_sk(occurred_at, "DEC-1") == (
        "DECISION#2026-09-19T05:30:01.000042Z#DEC-1"
    )
    assert approval_pointer_pk("APR-1") == "APPROVAL#APR-1"
    assert namespace_approval_sk(occurred_at, "APR-1") == (
        "APPROVAL#2026-09-19T05:30:01.000042Z#APR-1"
    )


def test_idempotency_keys_are_opaque_in_storage_keys():
    raw = "contains:user-visible-sensitive-context"
    digest = opaque_key_hash(raw)

    assert len(digest) == 64
    assert raw not in event_replay_sk(digest)
    assert raw not in approval_replay_sk(digest)
    assert raw not in effect_sk(digest)


@pytest.mark.parametrize("value", ["", "prod", "production", "all", "*"])
def test_unsafe_or_reserved_namespaces_are_rejected(value):
    with pytest.raises(StorageConfigurationError):
        validate_namespace(value)


def test_namespace_and_pointer_keys_are_scoped():
    assert namespace_pk("checkpoint8-local") == "DEMO#checkpoint8-local"
    assert namespace_trace_sk("TR-1") == "TRACE#TR-1"


@pytest.mark.parametrize("value", [0, -1, True, 1_000_000_000_000])
def test_invalid_event_sequences_are_rejected(value):
    with pytest.raises(StorageConfigurationError):
        event_sk(value)


def test_identifier_and_timestamp_validation_fail_closed():
    with pytest.raises(StorageConfigurationError, match="cannot contain"):
        trace_pk("TR#unsafe")
    with pytest.raises(StorageConfigurationError, match="timezone"):
        decision_sk(datetime(2026, 9, 19), "DEC-1")
