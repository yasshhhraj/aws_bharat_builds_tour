import pytest

from fixtures import FixtureLoader
from packages.domain.enums import AgentName, EffectClass
from packages.domain.errors import FixtureError, UnknownToolError
from packages.domain.models import ToolDefinition
from packages.tools import ToolRegistry, build_tool_registry


def test_checkpoint_three_registers_ten_classified_tools():
    registry, _ = build_tool_registry(FixtureLoader())
    definitions = registry.list_definitions()

    assert len(definitions) == 10
    assert any(item.name == "cancel_freight_booking" for item in definitions)
    assert all(definition.owner for definition in definitions)
    assert all(definition.effect_class for definition in definitions)
    assert all(definition.description for definition in definitions)


def test_unknown_tool_fails_closed():
    registry = ToolRegistry()
    with pytest.raises(UnknownToolError):
        registry.execute("unregistered", {})


def test_duplicate_tool_is_rejected():
    registry = ToolRegistry()
    definition = ToolDefinition(
        "read", AgentName.INVENTORY, EffectClass.READ, "Read data.", True
    )
    registry.register(definition, lambda: None)
    with pytest.raises(FixtureError, match="more than once"):
        registry.register(definition, lambda: None)
