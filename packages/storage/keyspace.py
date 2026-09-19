"""Deterministic and validated DynamoDB key construction."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re

from packages.domain.errors import StorageConfigurationError


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_NAMESPACE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_RESERVED_NAMESPACES = frozenset({"prod", "production", "all", "*"})


def _identifier(value: str, label: str) -> str:
    if "#" in value:
        raise StorageConfigurationError(f"{label} cannot contain '#'.")
    if not _IDENTIFIER.fullmatch(value):
        raise StorageConfigurationError(
            f"{label} must use 1-128 safe identifier characters."
        )
    return value


def validate_namespace(value: str, *, allow_reserved: bool = False) -> str:
    if not _NAMESPACE.fullmatch(value):
        raise StorageConfigurationError(
            "Demo namespace must use 1-64 letters, digits, dots, underscores, or dashes."
        )
    if not allow_reserved and value.casefold() in _RESERVED_NAMESPACES:
        raise StorageConfigurationError("The selected demo namespace is reserved.")
    return value


def trace_pk(trace_id: str) -> str:
    return f"TRACE#{_identifier(trace_id, 'Trace ID')}"


def event_sk(sequence: int) -> str:
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
        raise StorageConfigurationError("Event sequence must be a positive integer.")
    if sequence > 999_999_999_999:
        raise StorageConfigurationError("Event sequence exceeds the key format limit.")
    return f"EVENT#{sequence:012d}"


def decision_sk(created_at: datetime, decision_id: str) -> str:
    if created_at.tzinfo is None:
        raise StorageConfigurationError("Decision timestamp must include a timezone.")
    timestamp = (
        created_at.astimezone(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )
    return f"DECISION#{timestamp}#{_identifier(decision_id, 'Decision ID')}"


def approval_sk(approval_id: str) -> str:
    return f"APPROVAL#{_identifier(approval_id, 'Approval ID')}"


def approval_pointer_pk(approval_id: str) -> str:
    return approval_sk(approval_id)


def namespace_pk(namespace: str) -> str:
    return f"DEMO#{validate_namespace(namespace)}"


def namespace_trace_sk(trace_id: str) -> str:
    return f"TRACE#{_identifier(trace_id, 'Trace ID')}"


def namespace_approval_sk(created_at: datetime, approval_id: str) -> str:
    if created_at.tzinfo is None:
        raise StorageConfigurationError("Approval timestamp must include a timezone.")
    timestamp = (
        created_at.astimezone(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )
    return f"APPROVAL#{timestamp}#{_identifier(approval_id, 'Approval ID')}"


def opaque_key_hash(value: str) -> str:
    if not value:
        raise StorageConfigurationError("An idempotency key cannot be empty.")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def event_replay_sk(key_hash: str) -> str:
    return f"REPLAY#EVENT#{_hash(key_hash)}"


def approval_replay_sk(key_hash: str) -> str:
    return f"REPLAY#APPROVAL#{_hash(key_hash)}"


def effect_sk(key_hash: str) -> str:
    return f"EFFECT#{_hash(key_hash)}"


def _hash(value: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise StorageConfigurationError("Storage key hash must be lowercase SHA-256 hex.")
    return value
