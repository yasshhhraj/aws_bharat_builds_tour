"""Application-scoped dependency providers."""

from functools import lru_cache
import hmac
import os

from apps.runtime.service import RunService, build_run_service
from packages.domain.errors import ApprovalAuthNotConfiguredError, ApproverUnauthorizedError


@lru_cache(maxsize=1)
def _cached_run_service() -> RunService:
    return build_run_service()


async def get_run_service() -> RunService:
    # An async dependency avoids an unnecessary thread-pool hop for this small,
    # in-memory Checkpoint 3 service.
    return _cached_run_service()


def reset_run_service() -> None:
    """Clear the provider cache; useful for isolated tests."""
    _cached_run_service.cache_clear()


def approval_mutation_ready() -> bool:
    return bool(os.environ.get("DEMO_APPROVER_SECRET"))


def verify_demo_approver_secret(supplied: str | None) -> None:
    configured = os.environ.get("DEMO_APPROVER_SECRET")
    if not configured:
        raise ApprovalAuthNotConfiguredError(
            "Approval mutation is unavailable because the demo secret is not configured."
        )
    if supplied is None or not hmac.compare_digest(configured, supplied):
        raise ApproverUnauthorizedError("The demo approver secret is invalid.")
