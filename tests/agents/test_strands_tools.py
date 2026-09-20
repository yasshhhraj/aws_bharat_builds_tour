from apps.runtime.agent_runtime import RolePhase
from apps.runtime.runtime_settings import RuntimeSettings
from apps.runtime.service import build_run_service
from apps.runtime.strands_tools import GovernedInvocationContext, build_strands_tools
from packages.domain.enums import AgentName, GovernanceMode, RunStatus, ScenarioName
from packages.domain.errors import AgentIncompleteError, AgentRuntimeError
from packages.domain.models import TrajectoryState


def build_context(role: AgentName):
    service = build_run_service(runtime_settings=RuntimeSettings())
    order = service.loader.get_order("ORD-8842")
    mandate = service.loader.get_mandate(order, GovernanceMode.ENFORCE)
    scenario = service.loader.get_scenario("ORD-8842", ScenarioName.BENIGN)
    state = TrajectoryState(
        trace_id=f"TR-TOOLS-{role.value}",
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
    return GovernedInvocationContext(
        role, RolePhase.RUN, state, service.orchestrator.governor
    )


def test_each_role_receives_only_its_registered_tools():
    expected = {
        AgentName.INVENTORY: {"get_order", "check_inventory"},
        AgentName.DISPATCH: {"list_available_vehicles", "create_dispatch_plan"},
        AgentName.CARRIER: {
            "list_carrier_quotes",
            "select_carrier_quote",
            "prepare_freight_booking",
            "confirm_freight_booking",
        },
        AgentName.CUSTOMER_COMMUNICATIONS: {"write_tracking_outbox"},
    }
    for role, names in expected.items():
        tools = build_strands_tools(build_context(role))
        assert {item.tool_name for item in tools} == names


def test_model_schemas_do_not_expose_authority_or_idempotency_fields():
    forbidden = {
        "agent",
        "role",
        "trace_id",
        "mode",
        "policy_version",
        "action_hash",
        "idempotency_key",
        "cancellation_reason_code",
    }
    for role in AgentName:
        for item in build_strands_tools(build_context(role)):
            properties = item.tool_spec["inputSchema"]["json"].get("properties", {})
            assert forbidden.isdisjoint(properties)


def test_empty_inventory_tool_binds_the_active_order_and_calls_governor():
    context = build_context(AgentName.INVENTORY)

    payload = context.execute("get_order", {})

    assert payload["outcome"] == "allow"
    assert payload["value"]["order_id"] == "ORD-8842"
    assert context.state.order is not None
    assert context.state.tool_call_count == 1


def test_dispatch_read_exposes_only_governed_prerequisite_facts():
    inventory = build_context(AgentName.INVENTORY)
    inventory.execute("get_order", {})
    inventory.execute("check_inventory", {})
    dispatch = GovernedInvocationContext(
        AgentName.DISPATCH,
        RolePhase.RUN,
        inventory.state,
        inventory.governor,
    )

    payload = dispatch.execute("list_available_vehicles", {})

    assert payload["outcome"] == "allow"
    assert payload["value"]["shipment_context"] == {
        "order_id": "ORD-8842",
        "destination_zone": "BLR-SOUTH",
        "cargo_class": "perishable",
        "weight_value": 500,
        "weight_unit": "kg",
        "weight_fact_id": "WEIGHT-ORD-8842",
        "weight_source_id": "WMS-SNAPSHOT-001",
    }
    assert {item["vehicle_id"] for item in payload["value"]["vehicles"]} == {
        "VEH-COLD-01",
        "VEH-SMALL-01",
    }


def test_closed_context_rejects_late_tool_execution():
    context = build_context(AgentName.INVENTORY)
    context.close()

    try:
        context.execute("get_order", {})
    except AgentRuntimeError as exc:
        assert "closed" in exc.message
    else:  # pragma: no cover - assertion guard
        raise AssertionError("Closed context accepted a late tool call")


def test_incomplete_context_rejects_prose_only_completion():
    context = build_context(AgentName.INVENTORY)

    try:
        context.assert_complete()
    except AgentIncompleteError as exc:
        assert "before its governed role task completed" in exc.message
    else:  # pragma: no cover - assertion guard
        raise AssertionError("Incomplete role was accepted")
