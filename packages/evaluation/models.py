"""Typed contracts for reproducible Checkpoint 6 evaluation evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


CaseClassification = Literal["attack", "benign"]
CaseRunner = Literal["journey", "governor", "approval", "ledger"]


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    case_id: str
    classification: CaseClassification
    family: str
    runner: CaseRunner
    description: str
    input: dict[str, Any]
    expected: dict[str, Any]
    tags: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class EvaluationObservation:
    case_id: str
    classification: CaseClassification
    family: str
    terminal_status: str | None = None
    policy_outcomes: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    applied_outcomes: tuple[str, ...] = ()
    effect_executed: bool | None = None
    guide_back_succeeded: bool | None = None
    approval_result: str | None = None
    verification_valid: bool | None = None
    first_bad_sequence: int | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def functional_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CaseResult:
    case: EvaluationCase
    observation: EvaluationObservation
    passed: bool
    failure_summary: str | None
    measured_iterations: int
    policy_samples_ms: tuple[float, ...]
    end_to_end_samples_ms: tuple[float, ...]

    def functional_dict(self) -> dict[str, Any]:
        return {
            "case": self.case.as_dict(),
            "observation": self.observation.functional_dict(),
            "passed": self.passed,
            "failure_summary": self.failure_summary,
        }


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    schema_version: str
    generated_at: str
    seed: str
    warmup_per_case: int
    measured_per_case: int
    active_modes: dict[str, str]
    case_catalog_digest: str
    functional_digest: str
    summary: dict[str, Any]
    latency: dict[str, Any]
    cases: tuple[CaseResult, ...]
    limitations: tuple[str, ...]

