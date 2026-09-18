"""Application-scoped dependency providers."""

from functools import lru_cache

from apps.runtime.service import RunService, build_run_service


@lru_cache(maxsize=1)
def _cached_run_service() -> RunService:
    return build_run_service()


async def get_run_service() -> RunService:
    # An async dependency avoids an unnecessary thread-pool hop for this small,
    # in-memory Checkpoint 1 service.
    return _cached_run_service()


def reset_run_service() -> None:
    """Clear the provider cache; useful for isolated tests."""
    _cached_run_service.cache_clear()
