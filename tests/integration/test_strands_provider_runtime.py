import time

import pytest

from apps.runtime.agent_runtime import AgentRunRequest, RolePhase
from apps.runtime.recorded_model import RecordedManifestModel
from apps.runtime.runtime_settings import RuntimeSettings
from apps.runtime.service import build_run_service
from apps.runtime.strands_runtime import StrandsRuntime
from packages.domain.enums import AgentName, EventType, GovernanceMode, RunStatus, ScenarioName
from packages.domain.errors import (
    AgentIncompleteError,
    AgentRuntimeError,
    ProviderTimeoutError,
)
from packages.domain.models import TrajectoryState


class ScriptedHostedFactory:
    def validate(self, settings):
        assert settings.model_provider == "openrouter"

    def create(self, settings, context):
        return RecordedManifestModel(context, model_id=settings.model_id)


class ProseOnlyModel(RecordedManifestModel):
    def _next_call(self):
        return None

    def _summary(self):
        return "I would inspect inventory."


class ProseOnlyFactory(ScriptedHostedFactory):
    def create(self, settings, context):
        return ProseOnlyModel(context, model_id=settings.model_id)


class CapturingFactory(ScriptedHostedFactory):
    context = None

    def create(self, settings, context):
        self.context = context
        return object()


class LateToolAgent:
    cancelled = False
    late_error = None

    def __init__(self, **kwargs):
        del kwargs

    def __call__(self, *args, **kwargs):
        del args, kwargs
        time.sleep(0.05)
        try:
            timeout_factory.context.execute("get_order", {})
        except Exception as exc:  # the assertion inspects this exact boundary failure
            type(self).late_error = exc

    def cancel(self):
        type(self).cancelled = True


timeout_factory = CapturingFactory()


def test_provider_neutral_runtime_executes_governed_tools_and_records_metrics():
    service = build_run_service()
    order = service.loader.get_order("ORD-8842")
    mandate = service.loader.get_mandate(order, GovernanceMode.ENFORCE)
    scenario = service.loader.get_scenario("ORD-8842", ScenarioName.BENIGN)
    state = TrajectoryState(
        trace_id="TR-HOSTED-FAKE-INVENTORY",
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
    settings = RuntimeSettings("strands", "openrouter", "openrouter/free")
    runtime = StrandsRuntime(settings, ScriptedHostedFactory())

    result = runtime.invoke(
        AgentRunRequest(
            AgentName.INVENTORY,
            RolePhase.RUN,
            state,
            service.orchestrator.governor,
        )
    )

    assert state.inventory_fact is not None
    assert result.model_provider == "openrouter"
    assert result.model_id == "openrouter/free"
    assert result.turn_count == 3
    event = next(
        item
        for item in service.get_events(state.trace_id)
        if item.event_type == EventType.AGENT_MODEL_COMPLETED
    )
    assert event.details["provider_route_kind"] == "router"
    assert event.details["provider_fallback_active"] is False
    assert event.details["model_cycles"] == 3
    assert event.summary == "Completed bounded inventory model invocation."
    assert result.summary == (
        "Inventory Agent verified the synthetic order and 500 kg inventory fact."
    )


def test_prose_only_hosted_response_fails_without_marking_role_complete():
    service = build_run_service()
    order = service.loader.get_order("ORD-8842")
    mandate = service.loader.get_mandate(order, GovernanceMode.ENFORCE)
    scenario = service.loader.get_scenario("ORD-8842", ScenarioName.BENIGN)
    state = TrajectoryState(
        trace_id="TR-HOSTED-PROSE-ONLY",
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
    runtime = StrandsRuntime(
        RuntimeSettings("strands", "openrouter", "openrouter/free"),
        ProseOnlyFactory(),
    )

    with pytest.raises(AgentIncompleteError):
        runtime.invoke(
            AgentRunRequest(
                AgentName.INVENTORY,
                RolePhase.RUN,
                state,
                service.orchestrator.governor,
            )
        )

    assert state.order is None
    assert state.inventory_fact is None
    assert not any(
        item.event_type == EventType.AGENT_MODEL_COMPLETED
        for item in service.get_events(state.trace_id)
    )


def test_timeout_closes_context_before_a_late_tool_callback(monkeypatch):
    service = build_run_service()
    order = service.loader.get_order("ORD-8842")
    mandate = service.loader.get_mandate(order, GovernanceMode.ENFORCE)
    scenario = service.loader.get_scenario("ORD-8842", ScenarioName.BENIGN)
    state = TrajectoryState(
        trace_id="TR-HOSTED-LATE-TOOL",
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
    monkeypatch.setattr("apps.runtime.strands_runtime.Agent", LateToolAgent)
    LateToolAgent.cancelled = False
    LateToolAgent.late_error = None
    runtime = StrandsRuntime(
        RuntimeSettings(
            "strands",
            "openrouter",
            "openrouter/free",
            timeout_seconds=0.01,
        ),
        timeout_factory,
    )

    with pytest.raises(ProviderTimeoutError):
        runtime.invoke(
            AgentRunRequest(
                AgentName.INVENTORY,
                RolePhase.RUN,
                state,
                service.orchestrator.governor,
            )
        )
    time.sleep(0.08)

    assert LateToolAgent.cancelled is True
    assert isinstance(LateToolAgent.late_error, AgentRuntimeError)
    assert str(LateToolAgent.late_error) == "The role invocation is closed."
    assert state.order is None
    assert service.get_decisions(state.trace_id) == []
