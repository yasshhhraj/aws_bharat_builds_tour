"""Isolated repeated execution and functional determinism checks."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from time import perf_counter_ns
from typing import Callable

from packages.policy import PolicyEngine, PythonReferencePolicyEngine
from .case_loader import EvaluationCaseLoader
from .cases import execute_case
from .metrics import latency_summary, summarize_results
from .models import CaseResult, EvaluationObservation, EvaluationReport


EVALUATION_SCHEMA_VERSION = "manifest-evaluation-v1"


def canonical_digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _expected_failure(
    expected: dict[str, object], observation: EvaluationObservation
) -> str | None:
    actual = observation.functional_dict()
    for key, wanted in expected.items():
        if key == "details":
            for detail_key, detail_value in dict(wanted).items():
                actual_value = observation.details.get(detail_key)
                if actual_value != detail_value:
                    return (
                        f"details.{detail_key} expected {detail_value!r}, "
                        f"observed {actual_value!r}"
                    )
            continue
        observed = actual.get(key)
        if isinstance(wanted, list):
            missing = [value for value in wanted if value not in (observed or ())]
            if missing:
                return f"{key} is missing expected values {missing!r}"
        elif observed != wanted:
            return f"{key} expected {wanted!r}, observed {observed!r}"
    return None


class EvaluationRunner:
    def __init__(
        self,
        loader: EvaluationCaseLoader | None = None,
        *,
        engine_factory: Callable[[], PolicyEngine] | None = None,
    ) -> None:
        self.loader = loader or EvaluationCaseLoader()
        self._uses_default_engine = engine_factory is None
        self.engine_factory = engine_factory or PythonReferencePolicyEngine

    def _execute_case(self, case):
        if self._uses_default_engine:
            return execute_case(case)
        return execute_case(case, self.engine_factory())

    def run(
        self,
        *,
        seed: str = "manifest-checkpoint-6-v1",
        warmup: int = 1,
        iterations: int = 10,
    ) -> EvaluationReport:
        if not seed.strip():
            raise ValueError("Evaluation seed cannot be empty.")
        if warmup < 0 or iterations < 1:
            raise ValueError("Warm-up must be non-negative and iterations positive.")
        cases = self.loader.load()
        results = tuple(
            self._run_case(case, warmup=warmup, iterations=iterations)
            for case in cases
        )
        functional = [item.functional_dict() for item in results]
        policy_samples = [
            sample for item in results for sample in item.policy_samples_ms
        ]
        end_to_end_samples = [
            sample for item in results for sample in item.end_to_end_samples_ms
        ]
        engine_description = self.engine_factory().describe()
        engine_name = str(engine_description["policy_engine"])
        storage_mode = (
            "dynamodb_local"
            if os.getenv("MANIFEST_STORAGE_BACKEND", "memory").lower() == "dynamodb"
            else "memory_hash_chain"
        )
        limitations = [
            "All logistics data and operational effects are synthetic.",
            (
                "Storage is local DynamoDB with a tamper-evident, not immutable, hash chain."
                if storage_mode.startswith("dynamodb")
                else "Storage is an in-memory hash chain and is not durable or immutable."
            ),
            "Agents are deterministic Python roles; Strands and Bedrock are not active.",
            "Latency reflects this local machine and is not a production benchmark.",
        ]
        if engine_name == "python_reference":
            limitations.insert(
                1, "Authorization uses the Python reference engine; Cedar is not active."
            )
        else:
            limitations.insert(
                1, "Cedar runs as a local loopback sidecar; no remote PDP is active."
            )
        active_modes = {
            "runtime": "deterministic",
            "policy_engine": engine_name,
            "policy_version": "demo-v1",
            "storage": storage_mode,
            "approval": "local",
            "deployment": "local",
            "dashboard": "static_no_build",
        }
        if engine_name == "cedar":
            for source_key, report_key in (
                ("policy_bundle_hash", "policy_bundle_hash"),
                ("policy_schema_hash", "policy_schema_hash"),
                ("cedar_runtime_version", "cedar_runtime_version"),
            ):
                value = engine_description.get(source_key)
                if value:
                    active_modes[report_key] = str(value)
        return EvaluationReport(
            schema_version=EVALUATION_SCHEMA_VERSION,
            generated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            seed=seed,
            warmup_per_case=warmup,
            measured_per_case=iterations,
            active_modes=active_modes,
            case_catalog_digest=canonical_digest(
                [case.as_dict() for case in cases]
            ),
            functional_digest=canonical_digest(functional),
            summary=summarize_results(results),
            latency={
                "policy_ms": latency_summary(policy_samples),
                "end_to_end_ms": latency_summary(end_to_end_samples),
            },
            cases=results,
            limitations=tuple(limitations),
        )

    def _run_case(self, case, *, warmup: int, iterations: int) -> CaseResult:
        errors: list[str] = []
        for _ in range(warmup):
            try:
                self._execute_case(case)
            except Exception as exc:
                errors.append(f"warm-up raised {type(exc).__name__}")

        observations: list[EvaluationObservation] = []
        policy_samples: list[float] = []
        end_to_end_samples: list[float] = []
        for _ in range(iterations):
            started = perf_counter_ns()
            try:
                observation, decision_samples = self._execute_case(case)
            except Exception as exc:  # Keep denominators visible for case failures.
                observation = EvaluationObservation(
                    case_id=case.case_id,
                    classification=case.classification,
                    family=case.family,
                    details={"executor_error": type(exc).__name__},
                )
                decision_samples = ()
                errors.append(f"executor raised {type(exc).__name__}")
            elapsed_ms = (perf_counter_ns() - started) / 1_000_000
            observations.append(observation)
            policy_samples.extend(decision_samples)
            end_to_end_samples.append(elapsed_ms)

        reference = observations[0]
        reference_digest = canonical_digest(reference.functional_dict())
        if any(
            canonical_digest(item.functional_dict()) != reference_digest
            for item in observations[1:]
        ):
            errors.append("functional result changed across measured iterations")
        expected_failure = _expected_failure(case.expected, reference)
        if expected_failure:
            errors.append(expected_failure)
        failure = "; ".join(dict.fromkeys(errors)) or None
        return CaseResult(
            case=case,
            observation=reference,
            passed=failure is None,
            failure_summary=failure,
            measured_iterations=iterations,
            policy_samples_ms=tuple(policy_samples),
            end_to_end_samples_ms=tuple(end_to_end_samples),
        )
