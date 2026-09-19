"""Read-only verification for an ordered hash-chain trace."""

from __future__ import annotations

from collections.abc import Sequence

from packages.domain.models import LedgerHead, TraceEvent, VerificationResult

from .canonical import (
    GENESIS_HASH,
    HASH_ALGORITHM,
    LEDGER_SCHEMA_VERSION,
    calculate_event_hash,
)


def verify_chain(
    trace_id: str,
    events: Sequence[TraceEvent],
    head: LedgerHead,
) -> VerificationResult:
    expected_sequence = 1
    expected_previous_hash = GENESIS_HASH
    computed_head_hash = GENESIS_HASH
    checked = 0

    def failure(code: str, sequence: int) -> VerificationResult:
        return VerificationResult(
            trace_id=trace_id,
            valid=False,
            checked_event_count=checked,
            first_bad_sequence=sequence,
            failure_code=code,
            stored_head_sequence=head.sequence,
            stored_head_hash=head.event_hash,
            computed_head_hash=computed_head_hash,
            algorithm=HASH_ALGORITHM,
            schema_version=LEDGER_SCHEMA_VERSION,
        )

    for event in events:
        if event.sequence != expected_sequence:
            return failure("SEQUENCE_MISMATCH", expected_sequence)
        if event.trace_id != trace_id:
            return failure("TRACE_ID_MISMATCH", event.sequence)
        if event.schema_version != LEDGER_SCHEMA_VERSION:
            return failure("SCHEMA_VERSION_MISMATCH", event.sequence)
        if event.previous_hash != expected_previous_hash:
            return failure("PREVIOUS_HASH_MISMATCH", event.sequence)
        try:
            recomputed = calculate_event_hash(event)
        except (TypeError, ValueError):
            return failure("EVENT_HASH_MISMATCH", event.sequence)
        if event.event_hash != recomputed:
            return failure("EVENT_HASH_MISMATCH", event.sequence)
        computed_head_hash = recomputed
        expected_previous_hash = recomputed
        expected_sequence += 1
        checked += 1

    if len(events) != head.event_count:
        return failure("EVENT_COUNT_MISMATCH", expected_sequence)
    if head.sequence != len(events):
        return failure("HEAD_SEQUENCE_MISMATCH", expected_sequence)
    if head.event_hash != computed_head_hash:
        return failure("HEAD_HASH_MISMATCH", head.sequence)
    if head.schema_version != LEDGER_SCHEMA_VERSION:
        return failure("SCHEMA_VERSION_MISMATCH", max(head.sequence, 1))

    return VerificationResult(
        trace_id=trace_id,
        valid=True,
        checked_event_count=checked,
        first_bad_sequence=None,
        failure_code=None,
        stored_head_sequence=head.sequence,
        stored_head_hash=head.event_hash,
        computed_head_hash=computed_head_hash,
        algorithm=HASH_ALGORITHM,
        schema_version=LEDGER_SCHEMA_VERSION,
    )
