"""Project-owned contracts around the Strands role runner."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from packages.domain.enums import AgentName
from packages.domain.models import ApprovalRecord, TrajectoryState
from packages.governor import ManifestGovernor


class RolePhase(StrEnum):
    RUN = "run"
    RESUME_APPROVED = "resume_approved"
    CANCEL = "cancel"


@dataclass(frozen=True, slots=True)
class AgentRunRequest:
    role: AgentName
    phase: RolePhase
    state: TrajectoryState
    governor: ManifestGovernor
    approval: ApprovalRecord | None = None
    cancellation_reason_code: str | None = None


@dataclass(frozen=True, slots=True)
class AgentRunResult:
    summary: str
    stop_reason: str
    turn_count: int
    runtime_mode: str
    model_provider: str
    model_id: str
    latency_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class RoleRuntime(Protocol):
    def invoke(self, request: AgentRunRequest) -> AgentRunResult:
        """Run one isolated role invocation."""
