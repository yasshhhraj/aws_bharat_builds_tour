"""Policy engine port used by the governor."""

from typing import Protocol

from packages.domain.models import PolicyRequest, PolicySignal, TrajectoryState


class PolicyEngine(Protocol):
    name: str
    policy_version: str

    def evaluate(
        self, request: PolicyRequest, state: TrajectoryState
    ) -> tuple[PolicySignal, ...]: ...
