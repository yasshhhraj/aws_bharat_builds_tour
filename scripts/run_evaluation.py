#!/usr/bin/env python3
"""Generate deterministic Checkpoint 6 evaluation evidence."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from packages.evaluation.report import write_report  # noqa: E402
from packages.evaluation.runner import EvaluationRunner  # noqa: E402
from packages.policy import (  # noqa: E402
    PythonReferencePolicyEngine,
    build_policy_engine_from_env,
)


def _output_path(value: str, suffix: str) -> Path:
    path = (PROJECT_ROOT / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    try:
        path.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Output must remain inside the project.") from exc
    if path.suffix != suffix:
        raise argparse.ArgumentTypeError(f"Output must use the {suffix} suffix.")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", default="manifest-checkpoint-6-v1")
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument(
        "--policy-engine",
        choices=("python_reference", "cedar"),
        default="python_reference",
    )
    parser.add_argument(
        "--json-output",
        default="docs/results/checkpoint-6-evaluation.json",
    )
    parser.add_argument(
        "--markdown-output",
        default="docs/results/checkpoint-6-evaluation.md",
    )
    args = parser.parse_args()
    json_path = _output_path(args.json_output, ".json")
    markdown_path = _output_path(args.markdown_output, ".md")
    if args.policy_engine == "cedar":
        engine_factory = build_policy_engine_from_env
    else:
        engine_factory = PythonReferencePolicyEngine
    report = EvaluationRunner(engine_factory=engine_factory).run(
        seed=args.seed, warmup=args.warmup, iterations=args.iterations
    )
    write_report(report, json_path, markdown_path)
    failed = int(report.summary["case_failed"])
    print(
        f"Policy evaluation ({args.policy_engine}): {report.summary['case_passed']}/"
        f"{report.summary['case_total']} cases passed; "
        f"functional digest {report.functional_digest}"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
