"""Canonical serialization and hashing primitives for ledger events."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import math
from collections.abc import Mapping
from typing import Any


HASH_ALGORITHM = "sha256"
HASH_PREFIX = "sha256:"
LEDGER_SCHEMA_VERSION = "ledger-event-v1"
GENESIS_HASH = HASH_PREFIX + ("0" * 64)


def normalize(value: Any) -> Any:
    """Convert supported values into deterministic JSON primitives."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("Ledger datetimes must include a timezone.")
        utc_value = value.astimezone(timezone.utc)
        return utc_value.isoformat(timespec="microseconds").replace("+00:00", "Z")
    if is_dataclass(value):
        return normalize(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize(item) for item in value]
    if isinstance(value, (set, frozenset)):
        raise TypeError("Sets are not supported in canonical ledger payloads.")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Non-finite floats are not supported in ledger payloads.")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Unsupported ledger value type: {type(value).__name__}.")


def canonical_json(value: Any) -> str:
    """Return the checkpoint's pinned canonical JSON representation."""
    return json.dumps(
        normalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_text(value: str) -> str:
    return HASH_PREFIX + hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_payload(payload: Mapping[str, Any]) -> str:
    return sha256_text(canonical_json(payload))


def event_hash_payload(event: Any) -> dict[str, Any]:
    """Build the exact payload covered by an event hash."""
    return {
        "agent": event.agent,
        "details": event.details,
        "effect_class": event.effect_class,
        "event_id": event.event_id,
        "event_type": event.event_type,
        "idempotency_key": event.idempotency_key,
        "occurred_at": event.occurred_at,
        "previous_hash": event.previous_hash,
        "schema_version": event.schema_version,
        "sequence": event.sequence,
        "summary": event.summary,
        "tool_name": event.tool_name,
        "trace_id": event.trace_id,
    }


def calculate_event_hash(event: Any) -> str:
    return hash_payload(event_hash_payload(event))


def event_description_fingerprint(
    *,
    trace_id: str,
    event_type: Any,
    summary: str,
    details: Mapping[str, Any],
    agent: Any,
    tool_name: str | None,
    effect_class: Any,
    idempotency_key: str,
) -> str:
    """Fingerprint caller-controlled fields for idempotent replay checks."""
    return hash_payload(
        {
            "agent": agent,
            "details": details,
            "effect_class": effect_class,
            "event_type": event_type,
            "idempotency_key": idempotency_key,
            "schema_version": LEDGER_SCHEMA_VERSION,
            "summary": summary,
            "tool_name": tool_name,
            "trace_id": trace_id,
        }
    )
