"""Environment-driven storage selection."""

from __future__ import annotations

import os

from packages.domain.errors import StorageConfigurationError

from .protocol import TraceRepository


def build_trace_repository_from_env() -> TraceRepository:
    backend = os.getenv("MANIFEST_STORAGE_BACKEND", "memory").strip().lower()
    if backend == "memory":
        from packages.ledger import MemoryTraceStore

        store: TraceRepository = MemoryTraceStore()
    elif backend == "dynamodb":
        from .dynamodb import DynamoDBTraceStore

        store = DynamoDBTraceStore()
    else:
        raise StorageConfigurationError(
            f"Storage backend {backend or '<empty>'} is not supported."
        )
    store.validate_startup()
    return store
