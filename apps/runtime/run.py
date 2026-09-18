"""Command-line entry point for the Checkpoint 2 governed journey."""

from __future__ import annotations

import argparse
import json
import sys

from packages.domain.enums import EventType, RunStatus
from packages.domain.errors import ManifestError
from packages.domain.models import to_primitive

from .service import build_run_service


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a governed Manifest shipment.")
    parser.add_argument("--order", default="ORD-8842", help="Synthetic order ID")
    parser.add_argument("--mode", default="enforce", choices=["shadow", "enforce"])
    parser.add_argument("--scenario", default="benign", choices=["benign", "adversarial"])
    parser.add_argument(
        "--approval",
        choices=["approve", "reject"],
        help="Resolve a pending demo approval in the same in-memory process.",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        service = build_run_service()
        summary = service.start_run(args.order, args.mode, args.scenario)
        if args.approval and summary.pending_approval_id:
            resolution = service.resolve_approval(
                summary.pending_approval_id,
                decision=args.approval,
                approver_label="DEMO-APPROVER-CLI-1",
                comment="Resolved by the same-process demo CLI.",
                expected_version=1,
                idempotency_key=f"{summary.trace_id}:cli-approval:{args.approval}",
            )
            summary = resolution.run
    except ManifestError as exc:
        print(f"Error [{exc.code}]: {exc.message}", file=sys.stderr)
        return 2

    if args.as_json:
        print(json.dumps(to_primitive(summary), indent=2, sort_keys=True))
    else:
        print(f"Manifest trace: {summary.trace_id}")
        events = service.get_events(summary.trace_id)
        visible = {
            EventType.AGENT_COMPLETED,
            EventType.TOOL_GUIDED,
            EventType.TOOL_BLOCKED,
            EventType.APPROVAL_REQUIRED,
        }
        display_events = (
            item for item in events
            if item.event_type in visible
            or (
                item.event_type == EventType.POLICY_DECIDED
                and item.details.get("policy_outcome") != "allow"
                and item.details.get("enforced") is False
            )
        )
        for number, event in enumerate(display_events, start=1):
            print(f"{number}. {event.summary}")
        print(
            f"Spend: INR {summary.projected_spend_minor / 100:,.0f} / "
            f"INR {(summary.spend_ceiling_minor or 0) / 100:,.0f}"
        )
        print(f"Run status: {summary.status.value.upper()}")
        if summary.pending_approval_id:
            print(f"Pending approval: {summary.pending_approval_id}")
    if summary.error:
        print(f"Error: {summary.error}", file=sys.stderr)
    if summary.status in {
        RunStatus.COMPLETED,
        RunStatus.PENDING_APPROVAL,
        RunStatus.CANCELLED,
    }:
        return 0
    if summary.status == RunStatus.BLOCKED:
        return 3
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
