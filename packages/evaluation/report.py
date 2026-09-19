"""Safe deterministic serialization of Checkpoint 6 evidence."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .metrics import latency_summary
from .models import EvaluationReport


FORBIDDEN_OUTPUT_KEYS = ("secret", "token", "password", "credential")


def report_to_dict(report: EvaluationReport) -> dict[str, Any]:
    cases = []
    for result in report.cases:
        cases.append(
            {
                "case": result.case.as_dict(),
                "observation": result.observation.functional_dict(),
                "passed": result.passed,
                "failure_summary": result.failure_summary,
                "measured_iterations": result.measured_iterations,
                "latency": {
                    "policy_ms": (
                        latency_summary(result.policy_samples_ms)
                        if result.policy_samples_ms
                        else None
                    ),
                    "end_to_end_ms": latency_summary(
                        result.end_to_end_samples_ms
                    ),
                },
            }
        )
    value = {
        "schema_version": report.schema_version,
        "generated_at": report.generated_at,
        "seed": report.seed,
        "iterations": {
            "warmup_per_case": report.warmup_per_case,
            "measured_per_case": report.measured_per_case,
        },
        "active_modes": report.active_modes,
        "case_catalog_digest": report.case_catalog_digest,
        "functional_digest": report.functional_digest,
        "summary": report.summary,
        "latency": report.latency,
        "cases": cases,
        "limitations": list(report.limitations),
    }
    _reject_forbidden_keys(value)
    return value


def render_json(report: EvaluationReport) -> str:
    return json.dumps(
        report_to_dict(report),
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"


def _rate(summary: dict[str, Any], numerator: str, denominator: str) -> str:
    top = int(summary[numerator])
    bottom = int(summary[denominator])
    percentage = (top / bottom * 100) if bottom else 0.0
    return f"{top}/{bottom} ({percentage:.1f}%)"


def render_markdown(report: EvaluationReport) -> str:
    summary = report.summary
    policy = report.latency["policy_ms"]
    total = report.latency["end_to_end_ms"]
    lines = [
        "# Manifest Checkpoint 6 Evaluation Results",
        "",
        f"**Schema:** `{report.schema_version}`  ",
        f"**Generated:** `{report.generated_at}`",
        f"**Seed:** `{report.seed}`  ",
        f"**Functional digest:** `{report.functional_digest}`",
        "",
        "## Active modes",
        "",
    ]
    for key, value in sorted(report.active_modes.items()):
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Functional results",
            "",
            f"- Cases passed: {summary['case_passed']}/{summary['case_total']}",
            "- Attack detection: "
            + _rate(summary, "attack_detected", "attack_total"),
            "- Benign pass rate: "
            + _rate(summary, "benign_passed", "benign_total"),
            f"- False positives: {summary['false_positive_count']}/{summary['benign_total']}",
            "- Guide-back success: "
            + _rate(summary, "guide_back_succeeded", "guide_back_total"),
            "",
            "## Latency observed on this local machine",
            "",
            "| Measurement | Samples | p50 (ms) | p95 (ms) | Mean (ms) |",
            "|---|---:|---:|---:|---:|",
            f"| Policy evaluation | {policy['count']} | {policy['p50']} | {policy['p95']} | {policy['mean']} |",
            f"| End-to-end case | {total['count']} | {total['p50']} | {total['p95']} | {total['mean']} |",
            "",
            "## Case results",
            "",
            "| Case | Class | Family | Result | Evidence |",
            "|---|---|---|---|---|",
        ]
    )
    for result in report.cases:
        informative_reasons = tuple(
            reason
            for reason in result.observation.reason_codes
            if reason != "ALLOW_POLICY_CHECKS_PASSED"
        )
        if result.observation.verification_valid is False:
            evidence = str(
                result.observation.details.get("failure_code", "ledger invalid")
            )
        elif result.observation.verification_valid is True:
            evidence = "ledger valid"
        elif result.observation.approval_result:
            evidence = result.observation.approval_result
        elif informative_reasons:
            evidence = ", ".join(dict.fromkeys(informative_reasons))
        else:
            evidence = "expected workflow"
        if result.failure_summary:
            evidence = result.failure_summary
        lines.append(
            f"| `{result.case.case_id}` | {result.case.classification} | "
            f"{result.case.family} | {'PASS' if result.passed else 'FAIL'} | {evidence} |"
        )
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in report.limitations)
    lines.extend(
        [
            "",
            "## Reproduce",
            "",
            "```bash",
            "python3 scripts/run_evaluation.py --warmup 1 --iterations 10",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def write_atomic(path: Path, content: str) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def write_report(report: EvaluationReport, json_path: Path, markdown_path: Path) -> None:
    write_atomic(json_path, render_json(report))
    write_atomic(markdown_path, render_markdown(report))


def _reject_forbidden_keys(value: Any, path: str = "report") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).casefold()
            if any(fragment in normalized for fragment in FORBIDDEN_OUTPUT_KEYS):
                raise ValueError(f"Forbidden key {key!r} at {path}.")
            _reject_forbidden_keys(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _reject_forbidden_keys(child, f"{path}[{index}]")
