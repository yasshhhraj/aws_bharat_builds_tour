"""Opt-in live OpenRouter tests; skipped during every ordinary test run."""

from __future__ import annotations

import os
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from apps.runtime.agent_runtime import AgentRunRequest, RolePhase
from apps.runtime.runtime_settings import RuntimeSettings
from apps.runtime.service import build_run_service
from packages.domain.enums import AgentName, GovernanceMode, RunStatus, ScenarioName
from packages.domain.models import TrajectoryState


pytestmark = pytest.mark.skipif(
    os.environ.get("MANIFEST_RUN_LIVE_OPENROUTER") != "1"
    and os.environ.get("MANIFEST_RUN_LIVE_BEDROCK_MANTLE") != "1",
    reason="Live hosted-provider tests require explicit provider-specific opt-in.",
)

RESULTS_DIR = Path(__file__).resolve().parents[2] / "docs" / "results"


def _settings() -> RuntimeSettings:
    settings = RuntimeSettings.from_env()
    assert settings.runtime_mode == "strands"
    if os.environ.get("MANIFEST_RUN_LIVE_BEDROCK_MANTLE") == "1":
        assert settings.model_provider == "bedrock_mantle"
        assert os.environ.get("BEDROCK_MANTLE_API_KEY")
    else:
        assert settings.model_provider == "openrouter"
        assert os.environ.get("OPENROUTER_API_KEY")
    return settings


def _write_evidence(
    stage, settings, service, state, *, result="passed", error_category=None
):
    """Write only bounded project fields; never serialize provider clients or prompts."""

    verification = service.verify_trace(state.trace_id)
    decisions = service.get_decisions(state.trace_id)
    is_mantle = settings.model_provider == "bedrock_mantle"
    evidence = {
        "schema_version": (
            "manifest-bedrock-mantle-live-v1"
            if is_mantle
            else "manifest-openrouter-live-v1"
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "result": result,
        "error_category": error_category,
        "runtime_mode": settings.runtime_mode,
        "model_provider": settings.model_provider,
        "requested_model_id": settings.model_id,
        "resolved_model_id": None,
        "provider_route_kind": settings.provider_route_kind,
        "provider_fallback_active": False,
        "policy_engine": service.policy_engine.describe()["policy_engine"],
        "trace_id": state.trace_id,
        "run_status": state.status.value,
        "ledger_valid": verification.valid,
        "governed_tools": [
            {
                "tool_name": decision.tool_name,
                "applied_outcome": decision.applied_outcome.value,
                "reason_code": decision.reason_code,
                "enforced": decision.enforced,
            }
            for decision in decisions
        ],
        "limitations": (
            [
                "Synthetic Manifest fixture data only.",
                "Amazon Bedrock Mantle inference is paid and hosted.",
                "Resolved model is null because the adapter did not expose a separate resolved identity.",
            ]
            if is_mantle
            else [
                "Synthetic Manifest fixture data only.",
                "The requested free router may select different hosted models.",
                "Resolved model is null unless independently observed in OpenRouter Activity.",
            ]
        ),
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    prefix = "checkpoint-10-bedrock-mantle" if is_mantle else "checkpoint-10-openrouter"
    stem = RESULTS_DIR / f"{prefix}-{stage}"
    stem.with_suffix(".json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tools = ", ".join(item["tool_name"] for item in evidence["governed_tools"])
    stem.with_suffix(".md").write_text(
        "\n".join(
            (
                f"# Checkpoint 10 {'Bedrock Mantle' if is_mantle else 'OpenRouter'} Evidence — {stage}",
                "",
                f"- Result: `{evidence['result']}`",
                f"- Error category: `{evidence['error_category'] or 'none'}`",
                f"- Provider: `{evidence['model_provider']}`",
                f"- Requested model: `{evidence['requested_model_id']}`",
                f"- Route kind: `{evidence['provider_route_kind']}`",
                f"- Policy engine: `{evidence['policy_engine']}`",
                f"- Run status: `{evidence['run_status']}`",
                f"- Ledger valid: `{evidence['ledger_valid']}`",
                f"- Governed tools: `{tools}`",
                "- Resolved model: `not exposed by the active adapter`",
                "",
                "Only synthetic fixture data was used. Application-level provider fallback was disabled.",
                "",
            )
        ),
        encoding="utf-8",
    )


def test_openrouter_inventory_probe_uses_governed_read_tools():
    settings = _settings()
    service = build_run_service(runtime_settings=settings)
    order = service.loader.get_order("ORD-8842")
    mandate = service.loader.get_mandate(order, GovernanceMode.ENFORCE)
    scenario = service.loader.get_scenario("ORD-8842", ScenarioName.BENIGN)
    state = TrajectoryState(
        trace_id=(
            "TR-BEDROCK-MANTLE-INVENTORY-PROBE"
            if settings.model_provider == "bedrock_mantle"
            else "TR-OPENROUTER-INVENTORY-PROBE"
        ),
        order_id=order.order_id,
        status=RunStatus.RUNNING,
        mode=GovernanceMode.ENFORCE,
        scenario=ScenarioName.BENIGN,
        scenario_config=scenario,
        mandate=mandate,
        policy_version=mandate.policy_version,
        spend_committed_minor=scenario.prior_committed_minor,
    )
    service.store.create_run(state)
    inventory = service.orchestrator.agents[0]

    try:
        summary = inventory.run(state, service.orchestrator.governor)
    except Exception as exc:
        _write_evidence(
            "inventory-probe",
            settings,
            service,
            state,
            result="failed",
            error_category=getattr(exc, "code", "UNEXPECTED_ERROR"),
        )
        raise

    assert "inventory" in summary.casefold() or state.inventory_fact is not None
    assert state.order is not None
    assert state.inventory_fact is not None
    assert [item.tool_name for item in service.get_decisions(state.trace_id)] == [
        "get_order",
        "check_inventory",
    ]
    assert service.verify_trace(state.trace_id).valid is True
    _write_evidence("inventory-probe", settings, service, state)


def test_openrouter_benign_hero_journey_preserves_governed_outcome():
    service = build_run_service(runtime_settings=_settings())

    summary = service.start_run("ORD-8842", "enforce", "benign")

    _write_evidence(
        "benign",
        _settings(),
        service,
        summary,
        result="passed" if summary.status == RunStatus.COMPLETED else "failed",
        error_category=(
            next(
                (
                    event.details.get("error_code")
                    for event in reversed(service.get_events(summary.trace_id))
                    if event.event_type.value == "run_failed"
                ),
                None,
            )
        ),
    )

    assert summary.status == RunStatus.COMPLETED, summary.error
    assert summary.selected_vehicle_id == "VEH-COLD-01"
    assert summary.selected_carrier_id == "CARRIER-COLD-01"
    assert summary.confirmed_booking_id is not None
    assert summary.notification_id == "NOTIFY-ORD-8842"
    assert service.verify_trace(summary.trace_id).valid is True


def test_openrouter_adversarial_journey_keeps_cedar_authoritative():
    service = build_run_service(runtime_settings=_settings())

    summary = service.start_run("ORD-8842", "enforce", "adversarial")

    expected_statuses = {RunStatus.PENDING_APPROVAL, RunStatus.BLOCKED}
    _write_evidence(
        "adversarial",
        _settings(),
        service,
        summary,
        result="passed" if summary.status in expected_statuses else "failed",
        error_category=(
            next(
                (
                    event.details.get("error_code")
                    for event in reversed(service.get_events(summary.trace_id))
                    if event.event_type.value == "run_failed"
                ),
                None,
            )
        ),
    )

    assert summary.status in expected_statuses, summary.error
    decisions = service.get_decisions(summary.trace_id)
    assert any(item.enforced for item in decisions)
    assert any(item.applied_outcome.value in {"guide", "escalate", "block"} for item in decisions)
    assert summary.confirmed_booking_id is None
    assert service.verify_trace(summary.trace_id).valid is True
