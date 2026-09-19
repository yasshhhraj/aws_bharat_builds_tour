"""Durable-storage contracts and serialization support."""

from .models import (
    MAX_PERSISTED_ITEM_BYTES,
    STATE_SCHEMA_VERSION,
    STORAGE_SCHEMA_VERSION,
    EffectReceipt,
    ReplayKind,
    ReplayRecord,
    StoredTrace,
    TraceTransition,
)
from .protocol import TraceRepository
from .factory import build_trace_repository_from_env

__all__ = [
    "EffectReceipt",
    "MAX_PERSISTED_ITEM_BYTES",
    "ReplayKind",
    "ReplayRecord",
    "STATE_SCHEMA_VERSION",
    "STORAGE_SCHEMA_VERSION",
    "StoredTrace",
    "TraceRepository",
    "TraceTransition",
    "build_trace_repository_from_env",
]
