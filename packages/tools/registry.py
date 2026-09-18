"""Effect-classified tool registration and dispatch."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from packages.domain.errors import FixtureError, UnknownToolError
from packages.domain.enums import AgentName, EffectClass
from packages.domain.models import ToolDefinition

ToolHandler = Callable[..., Any]


class ToolRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, definition: ToolDefinition, handler: ToolHandler) -> None:
        if definition.name in self._definitions or definition.name in self._handlers:
            raise FixtureError(f"Tool {definition.name} is registered more than once.")
        self._definitions[definition.name] = definition
        self._handlers[definition.name] = handler

    def get_definition(self, tool_name: str) -> ToolDefinition:
        try:
            return self._definitions[tool_name]
        except KeyError as exc:
            raise UnknownToolError(f"Tool {tool_name} is not registered.") from exc

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        self.get_definition(tool_name)
        try:
            handler = self._handlers[tool_name]
        except KeyError as exc:
            raise UnknownToolError(f"Tool {tool_name} has no handler.") from exc
        return handler(**arguments)

    def list_definitions(self) -> list[ToolDefinition]:
        return [self._definitions[name] for name in sorted(self._definitions)]

    def validate_startup(self) -> None:
        definition_names = set(self._definitions)
        handler_names = set(self._handlers)
        if definition_names != handler_names:
            missing_handlers = sorted(definition_names - handler_names)
            missing_definitions = sorted(handler_names - definition_names)
            raise FixtureError(
                "Tool registry mismatch. "
                f"Missing handlers: {missing_handlers}; "
                f"missing definitions: {missing_definitions}."
            )
        for definition in self._definitions.values():
            if not definition.description.strip():
                raise FixtureError(f"Tool {definition.name} has no description.")
            if not isinstance(definition.owner, AgentName):
                raise FixtureError(f"Tool {definition.name} has no valid owner.")
            if not isinstance(definition.effect_class, EffectClass):
                raise FixtureError(f"Tool {definition.name} has no valid effect class.")
