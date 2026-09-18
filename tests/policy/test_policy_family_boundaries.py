from fixtures import FixtureLoader
from packages.commitments import build_prepared_action
from packages.domain.enums import AgentName, DecisionOutcome, GovernanceMode, RunStatus, ScenarioName
from packages.domain.models import NumericFact, PolicyRequest, TrajectoryState
from packages.governor import ManifestGovernor
from packages.ledger import MemoryTraceStore
from packages.policy import PythonReferencePolicyEngine
from packages.tools import build_tool_registry


def governed_state():
    loader = FixtureLoader()
    order = loader.get_order("ORD-8842")
    fact = loader.get_inventory_fact(order)
    state = TrajectoryState(
        "TR-POLICY",
        order.order_id,
        status=RunStatus.RUNNING,
        mode=GovernanceMode.ENFORCE,
        scenario=ScenarioName.BENIGN,
        scenario_config=loader.get_scenario(order.order_id, "benign"),
        mandate=loader.get_mandate(order, GovernanceMode.ENFORCE),
        order=order,
        inventory_fact=fact,
        spend_committed_minor=310000,
    )
    state.facts[fact.fact_id] = NumericFact(
        fact.fact_id, "shipment_weight", fact.shipment_weight_kg, "kg",
        fact.source_id, fact.source_hash, "check_inventory"
    )
    store = MemoryTraceStore()
    store.create_run(state)
    registry, _ = build_tool_registry(loader)
    governor = ManifestGovernor(registry, store, PythonReferencePolicyEngine(), loader)
    return state, store, governor


def test_tool_owner_mismatch_and_unknown_tool_fail_closed():
    state, _, governor = governed_state()
    wrong_owner = governor.execute_tool(state, AgentName.CARRIER, "get_order", order_id="ORD-8842")
    unknown = governor.execute_tool(state, AgentName.INVENTORY, "not_registered")

    assert wrong_owner.decision.applied_outcome == DecisionOutcome.BLOCK
    assert wrong_owner.decision.reason_code == "TOOL_OWNER_MISMATCH"
    assert unknown.decision.applied_outcome == DecisionOutcome.BLOCK
    assert unknown.decision.reason_code == "UNKNOWN_TOOL"


def test_missing_provenance_reference_blocks_before_dispatch_effect():
    state, _, governor = governed_state()
    result = governor.execute_tool(
        state, AgentName.DISPATCH, "create_dispatch_plan",
        order_id="ORD-8842", vehicle_id="VEH-COLD-01",
        weight_value=500, weight_unit="kg", weight_fact_id="UNKNOWN",
        idempotency_key="missing-fact",
    )
    assert result.decision.applied_outcome == DecisionOutcome.BLOCK
    assert result.decision.reason_code == "PROVENANCE_REFERENCE_MISSING"
    assert result.value is None


def test_pii_boundary_rejects_free_form_message():
    state, store, governor = governed_state()
    result = governor.execute_tool(
        state, AgentName.CUSTOMER_COMMUNICATIONS, "write_tracking_outbox",
        order_id="ORD-8842", message="send to user@example.com",
        idempotency_key="unsafe-disclosure",
    )
    assert result.decision.applied_outcome == DecisionOutcome.BLOCK
    assert result.decision.reason_code == "PII_FIELD_NOT_ALLOWED"
    assert result.value is None
    attempted = store.get_events(state.trace_id)[0].details["arguments"]
    assert "message" not in attempted


def test_commitment_budget_allows_exact_ceiling_and_escalates_above_it():
    engine = PythonReferencePolicyEngine()
    state, _, _ = governed_state()
    prepared = build_prepared_action(
        state, prepared_action_id="PREP-1", quote_id="QUOTE-COLD-01",
        amount_minor=90000, currency="INR", prepared_by=AgentName.CARRIER,
    )
    state.prepared_actions[prepared.prepared_action_id] = prepared
    state.spend_reserved_minor = 90000
    request = PolicyRequest(
        "REQ-1", AgentName.CARRIER, "confirm_freight_booking",
        "shipment_action", "PREP-1",
        {"tool_owner": "carrier", "effect_class": "financial_commit", "arguments": {"prepared_action_id": "PREP-1", "action_hash": prepared.action_hash}, "resource": {}},
    )

    at_ceiling = engine.evaluate(request, state)
    assert any(item.reason_code == "SPEND_WITHIN_CEILING" for item in at_ceiling)
    state.spend_committed_minor = 365000
    above = engine.evaluate(request, state)
    assert any(item.reason_code == "SPEND_APPROVAL_REQUIRED" and item.outcome == DecisionOutcome.ESCALATE for item in above)


def test_changed_action_hash_is_blocked_by_separation_policy():
    engine = PythonReferencePolicyEngine()
    state, _, _ = governed_state()
    prepared = build_prepared_action(
        state, prepared_action_id="PREP-2", quote_id="QUOTE-COLD-01",
        amount_minor=90000, currency="INR", prepared_by=AgentName.CARRIER,
    )
    state.prepared_actions[prepared.prepared_action_id] = prepared
    request = PolicyRequest(
        "REQ-2", AgentName.CARRIER, "confirm_freight_booking",
        "shipment_action", "PREP-2",
        {"tool_owner": "carrier", "effect_class": "financial_commit", "arguments": {"prepared_action_id": "PREP-2", "action_hash": "sha256:changed"}, "resource": {}},
    )
    signals = engine.evaluate(request, state)
    assert any(item.reason_code == "PREPARED_ACTION_MISMATCH" and item.outcome == DecisionOutcome.BLOCK for item in signals)


def test_confirm_requires_prepare_and_cannot_execute_twice():
    state, _, governor = governed_state()
    missing = governor.execute_tool(
        state, AgentName.CARRIER, "confirm_freight_booking",
        prepared_action_id="MISSING", action_hash="sha256:none",
        idempotency_key="missing-confirm",
    )
    assert missing.decision.reason_code == "PREPARED_ACTION_REQUIRED"
    assert missing.value is None

    prepared = build_prepared_action(
        state, prepared_action_id="PREP-3", quote_id="QUOTE-COLD-01",
        amount_minor=90000, currency="INR", prepared_by=AgentName.CARRIER,
    )
    state.prepared_actions[prepared.prepared_action_id] = prepared
    state.spend_reserved_minor = prepared.amount_minor
    first = governor.execute_tool(
        state, AgentName.CARRIER, "confirm_freight_booking",
        prepared_action_id=prepared.prepared_action_id,
        action_hash=prepared.action_hash, idempotency_key="confirm-once",
    )
    second = governor.execute_tool(
        state, AgentName.CARRIER, "confirm_freight_booking",
        prepared_action_id=prepared.prepared_action_id,
        action_hash=prepared.action_hash, idempotency_key="confirm-again",
    )
    assert first.value is not None
    assert state.spend_committed_minor == 400000
    assert state.spend_reserved_minor == 0
    assert second.decision.reason_code == "PREPARED_ACTION_MISMATCH"
    assert second.value is None
