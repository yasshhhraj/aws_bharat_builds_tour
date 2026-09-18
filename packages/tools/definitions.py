"""Checkpoint 1 tool definitions and registry assembly."""

from fixtures import FixtureLoader
from packages.domain.enums import AgentName, EffectClass
from packages.domain.models import ToolDefinition

from .mocks import MockLogisticsTools
from .registry import ToolRegistry


def build_tool_registry(loader: FixtureLoader) -> tuple[ToolRegistry, MockLogisticsTools]:
    mocks = MockLogisticsTools(loader)
    registry = ToolRegistry()
    registrations = [
        (
            ToolDefinition("get_order", AgentName.INVENTORY, EffectClass.READ, "Read one synthetic order.", True),
            mocks.get_order,
        ),
        (
            ToolDefinition("check_inventory", AgentName.INVENTORY, EffectClass.READ, "Read available stock and sourced weight.", True),
            mocks.check_inventory,
        ),
        (
            ToolDefinition("list_available_vehicles", AgentName.DISPATCH, EffectClass.READ, "List available synthetic vehicles.", True),
            mocks.list_available_vehicles,
        ),
        (
            ToolDefinition("create_dispatch_plan", AgentName.DISPATCH, EffectClass.REVERSIBLE_WRITE, "Create a reversible synthetic dispatch plan.", True),
            mocks.create_dispatch_plan,
        ),
        (
            ToolDefinition("list_carrier_quotes", AgentName.CARRIER, EffectClass.READ, "List synthetic carrier quotes.", True),
            mocks.list_carrier_quotes,
        ),
        (
            ToolDefinition("select_carrier_quote", AgentName.CARRIER, EffectClass.REVERSIBLE_WRITE, "Select a reversible synthetic carrier quote.", True),
            mocks.select_carrier_quote,
        ),
        (
            ToolDefinition("write_tracking_outbox", AgentName.CUSTOMER_COMMUNICATIONS, EffectClass.EXTERNAL_DISCLOSURE, "Write a simulated tracking notification to an in-memory outbox.", True),
            mocks.write_tracking_outbox,
        ),
    ]
    for definition, handler in registrations:
        registry.register(definition, handler)
    registry.validate_startup()
    return registry, mocks
