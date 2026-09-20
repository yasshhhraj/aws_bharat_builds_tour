"""Deterministic offline Strands model for repeatable governed journeys."""

from __future__ import annotations

from collections.abc import AsyncGenerator
import json
from typing import Any, TypeVar

from pydantic import BaseModel
from strands.models import Model
from strands.types.content import Messages
from strands.types.streaming import StreamEvent
from strands.types.tools import ToolSpec

from packages.domain.enums import AgentName
from packages.domain.errors import AgentRuntimeError

from .agent_runtime import RolePhase
from .strands_tools import GovernedInvocationContext


T = TypeVar("T", bound=BaseModel)


class RecordedManifestModel(Model):
    """A finite-state model that drives the real Strands tool loop offline."""

    def __init__(
        self,
        context: GovernedInvocationContext,
        *,
        model_id: str = "manifest-recorded-v1",
    ) -> None:
        self.context = context
        self.config: dict[str, Any] = {
            "model_id": model_id,
            "context_window_limit": 16_384,
        }
        self.model_call_count = 0

    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        return dict(self.config)

    async def structured_output(
        self,
        output_model: type[T],
        prompt: Messages,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[dict[str, T | Any], None]:
        if False:  # pragma: no cover - retains async-generator semantics
            yield {}
        raise AgentRuntimeError("Recorded mode does not support structured output.")

    async def stream(
        self,
        messages: Messages,
        tool_specs: list[ToolSpec] | None = None,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[StreamEvent, None]:
        del messages, system_prompt, kwargs
        self.model_call_count += 1
        next_call = self._next_call()
        if next_call is None:
            async for event in self._text_events(self._summary()):
                yield event
            return
        tool_name, arguments = next_call
        available = {item["name"] for item in tool_specs or []}
        if tool_name not in available:
            raise AgentRuntimeError(
                f"Recorded plan requested unavailable tool {tool_name}."
            )
        async for event in self._tool_events(tool_name, arguments):
            yield event

    def _next_call(self) -> tuple[str, dict[str, Any]] | None:
        if self.context.terminal:
            return None
        role = self.context.role
        if role == AgentName.INVENTORY:
            return self._inventory_call()
        if role == AgentName.DISPATCH:
            return self._dispatch_call()
        if role == AgentName.CARRIER:
            return self._carrier_call()
        if role == AgentName.CUSTOMER_COMMUNICATIONS:
            return self._communications_call()
        raise AgentRuntimeError(f"Recorded role {role.value} is not supported.")

    def _inventory_call(self) -> tuple[str, dict[str, Any]] | None:
        state = self.context.state
        if state.order is None:
            return "get_order", {}
        if state.inventory_fact is None:
            return "check_inventory", {}
        return None

    def _dispatch_call(self) -> tuple[str, dict[str, Any]] | None:
        state = self.context.state
        if not self._called("list_available_vehicles"):
            return "list_available_vehicles", {}
        if state.dispatch_plan_id is not None:
            return None
        scenario = state.scenario_config
        fact = state.inventory_fact
        if scenario is None or fact is None:
            raise AgentRuntimeError("Recorded dispatch requires scenario and inventory facts.")
        create_results = self._results("create_dispatch_plan")
        if not create_results:
            return (
                "create_dispatch_plan",
                {
                    "vehicle_id": scenario.preferred_vehicle_id,
                    "weight_value": scenario.attempted_weight_kg,
                    "weight_unit": "kg",
                    "weight_fact_id": fact.fact_id,
                },
            )
        last = create_results[-1]
        if last["outcome"] != "guide":
            return None
        guidance = last.get("guidance") or {}
        required = guidance.get("required_vehicle") or {}
        weight = int(guidance.get("required_value", fact.shipment_weight_kg))
        candidates = [
            vehicle
            for vehicle in self.context.governor.loader.list_vehicles()
            if vehicle.available
            and vehicle.capacity_kg
            >= int(required.get("minimum_capacity_kg") or weight)
            and (not required.get("refrigerated") or vehicle.refrigerated)
        ]
        if not candidates:
            raise AgentRuntimeError("Recorded dispatch found no guided vehicle.")
        selected = sorted(candidates, key=lambda item: item.vehicle_id)[0]
        return (
            "create_dispatch_plan",
            {
                "vehicle_id": selected.vehicle_id,
                "weight_value": weight,
                "weight_unit": str(guidance.get("required_unit", "kg")),
                "weight_fact_id": str(
                    guidance.get("required_fact_id", fact.fact_id)
                ),
            },
        )

    def _carrier_call(self) -> tuple[str, dict[str, Any]] | None:
        state = self.context.state
        if self.context.phase == RolePhase.RESUME_APPROVED:
            if state.confirmed_booking_id is not None:
                return None
            prepared = self._bound_prepared()
            return "confirm_freight_booking", {
                "prepared_action_id": prepared.prepared_action_id
            }
        if self.context.phase == RolePhase.CANCEL:
            if self._called("cancel_freight_booking"):
                return None
            prepared = self._bound_prepared()
            return "cancel_freight_booking", {
                "prepared_action_id": prepared.prepared_action_id
            }

        if not self._called("list_carrier_quotes"):
            return "list_carrier_quotes", {}
        if state.selected_quote is None:
            scenario = state.scenario_config
            if scenario is None:
                raise AgentRuntimeError("Recorded carrier requires a scenario.")
            select_results = self._results("select_carrier_quote")
            if not select_results:
                quote_id = scenario.preferred_quote_id
            elif select_results[-1]["outcome"] == "guide":
                if state.order is None:
                    raise AgentRuntimeError("Recorded carrier requires an order.")
                candidates = [
                    quote
                    for quote in self.context.governor.loader.list_carrier_quotes(
                        state.order.destination_zone
                    )
                    if quote.cold_chain_certified and quote.lane_supported
                ]
                if not candidates:
                    raise AgentRuntimeError("Recorded carrier found no guided quote.")
                quote_id = min(
                    candidates, key=lambda quote: (quote.amount_minor, quote.quote_id)
                ).quote_id
            else:
                return None
            return "select_carrier_quote", {"quote_id": quote_id}

        if not state.prepared_actions:
            quote = state.selected_quote
            return (
                "prepare_freight_booking",
                {
                    "quote_id": quote.quote_id,
                    "amount_minor": quote.amount_minor,
                    "currency": quote.currency,
                },
            )
        if state.pending_approval_id is None and state.confirmed_booking_id is None:
            prepared = next(iter(state.prepared_actions.values()))
            return "confirm_freight_booking", {
                "prepared_action_id": prepared.prepared_action_id
            }
        return None

    def _communications_call(self) -> tuple[str, dict[str, Any]] | None:
        if self.context.state.notification_id is None:
            return "write_tracking_outbox", {}
        return None

    def _bound_prepared(self):
        approval = self.context.approval
        if approval is None:
            raise AgentRuntimeError("Carrier continuation requires a bound approval.")
        prepared = self.context.state.prepared_actions.get(approval.prepared_action_id)
        if prepared is None:
            raise AgentRuntimeError("The approval's prepared action was not found.")
        return prepared

    def _called(self, tool_name: str) -> bool:
        return any(name == tool_name for name, _ in self.context.history)

    def _results(self, tool_name: str) -> list[dict[str, Any]]:
        return [payload for name, payload in self.context.history if name == tool_name]

    def _summary(self) -> str:
        state = self.context.state
        role = self.context.role
        if self.context.blocked_reason:
            return self.context.blocked_reason
        if role == AgentName.INVENTORY and state.inventory_fact is not None:
            fact = state.inventory_fact
            return (
                f"Inventory Agent verified {fact.shipment_weight_kg} kg of available "
                f"stock from {fact.source_id}."
            )
        if role == AgentName.DISPATCH and state.selected_vehicle is not None:
            plan_results = self._results("create_dispatch_plan")
            weight = (plan_results[-1].get("value") or {}).get("weight_kg", 0)
            return (
                f"Dispatch Agent selected vehicle {state.selected_vehicle.vehicle_id} "
                f"for {weight} kg."
            )
        if role == AgentName.CARRIER:
            if self.context.phase == RolePhase.CANCEL:
                prepared = self._bound_prepared()
                return f"Carrier Agent cancelled prepared booking {prepared.prepared_action_id}."
            if state.pending_approval_id and state.selected_quote is not None:
                return (
                    f"Carrier Agent prepared {state.selected_quote.carrier_id}; "
                    "approval is required."
                )
            if self.context.phase == RolePhase.RESUME_APPROVED:
                return (
                    "Carrier Agent confirmed approved booking "
                    f"{state.confirmed_booking_id}."
                )
            if state.selected_quote is not None and state.confirmed_booking_id is not None:
                amount = state.selected_quote.amount_minor / 100
                return (
                    f"Carrier Agent confirmed {state.selected_quote.carrier_id} "
                    f"for INR {amount:,.0f}."
                )
        if role == AgentName.CUSTOMER_COMMUNICATIONS and state.notification_id:
            return "Customer Communications Agent wrote a simulated tracking message."
        return f"{role.value} completed without an additional effect."

    async def _tool_events(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> AsyncGenerator[StreamEvent, None]:
        tool_use_id = f"recorded-{self.context.role.value}-{self.model_call_count}"
        yield {"messageStart": {"role": "assistant"}}
        yield {
            "contentBlockStart": {
                "contentBlockIndex": 0,
                "start": {
                    "toolUse": {"name": tool_name, "toolUseId": tool_use_id}
                },
            }
        }
        yield {
            "contentBlockDelta": {
                "contentBlockIndex": 0,
                "delta": {"toolUse": {"input": json.dumps(arguments, sort_keys=True)}},
            }
        }
        yield {"contentBlockStop": {"contentBlockIndex": 0}}
        yield {"messageStop": {"stopReason": "tool_use"}}
        yield self._metadata_event()

    async def _text_events(
        self, text: str
    ) -> AsyncGenerator[StreamEvent, None]:
        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockStart": {"contentBlockIndex": 0, "start": {}}}
        yield {
            "contentBlockDelta": {
                "contentBlockIndex": 0,
                "delta": {"text": text},
            }
        }
        yield {"contentBlockStop": {"contentBlockIndex": 0}}
        yield {"messageStop": {"stopReason": "end_turn"}}
        yield self._metadata_event()

    @staticmethod
    def _metadata_event() -> StreamEvent:
        return {
            "metadata": {
                "usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2},
                "metrics": {"latencyMs": 0},
            }
        }
