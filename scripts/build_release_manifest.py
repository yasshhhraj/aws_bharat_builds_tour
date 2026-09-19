#!/usr/bin/env python3
"""Bind Checkpoint 6 evidence to source and fixture state."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from packages.evaluation.release_manifest import (  # noqa: E402
    build_release_manifest,
    write_release_manifest,
)


def _inside_project(value: str, suffix: str) -> Path:
    path = (PROJECT_ROOT / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    try:
        path.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Path must remain inside the project.") from exc
    if path.suffix != suffix:
        raise argparse.ArgumentTypeError(f"Path must use the {suffix} suffix.")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evaluation", default="docs/results/checkpoint-6-evaluation.json"
    )
    parser.add_argument(
        "--output", default="docs/releases/checkpoint-6-local-baseline.json"
    )
    parser.add_argument("--test-command", default="./scripts/run_checkpoint_6.sh")
    args = parser.parse_args()
    evaluation = _inside_project(args.evaluation, ".json")
    output = _inside_project(args.output, ".json")
    manifest = build_release_manifest(
        repo_root=PROJECT_ROOT,
        evaluation_path=evaluation,
        test_command=args.test_command,
    )
    write_release_manifest(output, manifest)
    print(
        f"Release manifest ({manifest['policy']['engine']}): "
        f"{manifest['source']['commit']} (dirty={manifest['source']['dirty']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
