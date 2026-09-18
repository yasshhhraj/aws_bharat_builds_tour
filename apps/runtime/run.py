"""Command-line entry point for the Checkpoint 1 journey."""

from __future__ import annotations

import argparse
import sys

from packages.domain.enums import EventType, RunStatus
from packages.domain.errors import ManifestError

from .service import build_run_service


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a deterministic Manifest shipment.")
    parser.add_argument("--order", default="ORD-8842", help="Synthetic order ID")
    parser.add_argument("--mode", default="shadow", choices=["shadow"])
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        service = build_run_service()
        summary = service.start_run(args.order, args.mode)
    except ManifestError as exc:
        print(f"Error [{exc.code}]: {exc.message}", file=sys.stderr)
        return 2

    print(f"Manifest trace: {summary.trace_id}")
    completed_steps = [
        event
        for event in service.get_events(summary.trace_id)
        if event.event_type == EventType.AGENT_COMPLETED
    ]
    for number, event in enumerate(completed_steps, start=1):
        print(f"{number}. {event.summary}")
    print(f"Run status: {summary.status.value.upper()}")
    if summary.error:
        print(f"Error: {summary.error}", file=sys.stderr)
    return 0 if summary.status == RunStatus.COMPLETED else 1


if __name__ == "__main__":
    raise SystemExit(main())
