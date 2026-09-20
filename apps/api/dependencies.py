"""Application-scoped dependency providers."""

from functools import lru_cache
import hmac
import os

from fastapi import Header

from apps.runtime.service import RunService, build_run_service
from packages.domain.errors import (
    ApprovalAuthNotConfiguredError,
    ApproverUnauthorizedError,
    DemoAccessNotConfiguredError,
    DemoAccessUnauthorizedError,
    LedgerTamperDisabledError,
    LedgerTamperUnauthorizedError,
)


def deployment_mode() -> str:
    mode = os.environ.get("MANIFEST_DEPLOYMENT_MODE", "local").strip().lower()
    if mode not in {"local", "aws"}:
        raise ValueError("MANIFEST_DEPLOYMENT_MODE must be local or aws.")
    return mode


def demo_access_required() -> bool:
    return deployment_mode() == "aws"


def demo_access_ready() -> bool:
    return not demo_access_required() or bool(os.environ.get("DEMO_ACCESS_SECRET"))


def verify_demo_access_secret(supplied: str | None) -> None:
    if not demo_access_required():
        return
    configured = os.environ.get("DEMO_ACCESS_SECRET")
    if not configured:
        raise DemoAccessNotConfiguredError(
            "Public demo mutations are unavailable because access is not configured."
        )
    if supplied is None or not hmac.compare_digest(configured, supplied):
        raise DemoAccessUnauthorizedError("The demo access secret is invalid.")


async def require_demo_access(
    supplied: str | None = Header(default=None, alias="X-Manifest-Demo-Secret"),
) -> None:
    verify_demo_access_secret(supplied)


@lru_cache(maxsize=1)
def _cached_run_service() -> RunService:
    return build_run_service()


async def get_run_service() -> RunService:
    # An async dependency avoids an unnecessary thread-pool hop for this small service.
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


def demo_tamper_enabled() -> bool:
    return os.environ.get("ENABLE_DEMO_TAMPER", "").strip().lower() == "true"


def tamper_mutation_ready() -> bool:
    return demo_tamper_enabled() and bool(os.environ.get("DEMO_TAMPER_SECRET"))


def verify_demo_tamper_secret(supplied: str | None) -> None:
    if not demo_tamper_enabled():
        raise LedgerTamperDisabledError("The disposable tamper demo is disabled.")
    configured = os.environ.get("DEMO_TAMPER_SECRET")
    if not configured or supplied is None or not hmac.compare_digest(configured, supplied):
        raise LedgerTamperUnauthorizedError("The demo tamper secret is invalid.")
