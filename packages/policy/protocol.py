"""Policy engine port used by the governor."""

from typing import Protocol

from packages.domain.models import PolicyRequest, PolicySignal, TrajectoryState


class PolicyEngine(Protocol):
    name: str
    policy_version: str
    bundle_hash: str | None

    def validate_startup(self) -> None: ...

    def evaluate(
        self, request: PolicyRequest, state: TrajectoryState
    ) -> tuple[PolicySignal, ...]: ...

    def describe(self) -> dict[str, object]: ...
