"""Deterministic state projection for successful governed tool results."""

from __future__ import annotations

from typing import Any

from fixtures import FixtureLoader
from packages.commitments import build_prepared_action
from packages.domain.enums import AgentName, WorkflowStage
from packages.domain.errors import ToolExecutionError
from packages.domain.models import (
    CarrierQuote,
    InventoryFact,
    NumericFact,
    Order,
    TrajectoryState,
    Vehicle,
)


class ToolResultProjector:
    """Apply workflow projections only after the governor returns a value."""

    def __init__(self, loader: FixtureLoader) -> None:
        self.loader = loader

    def project(
        self,
        state: TrajectoryState,
        agent: AgentName,
        tool_name: str,
        arguments: dict[str, Any],
        value: Any,
    ) -> None:
        if tool_name == "get_order":
            if not isinstance(value, Order):
                raise ToolExecutionError("get_order returned an invalid result.")
            state.order = value
            return

        if tool_name == "check_inventory":
            if not isinstance(value, InventoryFact):
                raise ToolExecutionError("check_inventory returned an invalid result.")
            state.inventory_fact = value
            state.facts[value.fact_id] = NumericFact(
                fact_id=value.fact_id,
                name="shipment_weight",
                value=value.shipment_weight_kg,
                unit="kg",
                source_id=value.source_id,
                source_hash=value.source_hash,
                created_by_tool="check_inventory",
            )
            return

        if tool_name == "create_dispatch_plan":
            payload = self._mapping(tool_name, value)
            vehicle_id = str(arguments["vehicle_id"])
            vehicle = self._vehicle(vehicle_id)
            state.selected_vehicle = vehicle
            state.dispatch_plan_id = str(payload["plan_id"])
            return

        if tool_name == "select_carrier_quote":
            payload = self._mapping(tool_name, value)
            quote_id = str(arguments["quote_id"])
            quote = self._quote(state, quote_id)
            state.selected_quote = quote
            state.carrier_selection_id = str(payload["selection_id"])
            state.quoted_by = quote.quote_issuer
            return

        if tool_name == "prepare_freight_booking":
            payload = self._mapping(tool_name, value)
            prepared_id = str(payload["prepared_action_id"])
            if prepared_id in state.prepared_actions:
                return
            amount_minor = int(arguments["amount_minor"])
            prepared = build_prepared_action(
                state,
                prepared_action_id=prepared_id,
                quote_id=str(arguments["quote_id"]),
                amount_minor=amount_minor,
                currency=str(arguments["currency"]),
                prepared_by=agent,
            )
            state.prepared_actions[prepared_id] = prepared
            state.prepared_by = agent
            state.spend_reserved_minor += amount_minor
            state.workflow_stage = WorkflowStage.BOOKING_PREPARED
            return

        if tool_name == "write_tracking_outbox":
            payload = self._mapping(tool_name, value)
            state.notification_id = str(payload["notification_id"])

    @staticmethod
    def _mapping(tool_name: str, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ToolExecutionError(f"{tool_name} returned an invalid result.")
        return value

    def _vehicle(self, vehicle_id: str) -> Vehicle:
        for vehicle in self.loader.list_vehicles():
            if vehicle.vehicle_id == vehicle_id:
                return vehicle
        raise ToolExecutionError(f"Vehicle {vehicle_id} was not found during projection.")

    def _quote(self, state: TrajectoryState, quote_id: str) -> CarrierQuote:
        if state.order is None:
            raise ToolExecutionError("Carrier projection requires an order.")
        for quote in self.loader.list_carrier_quotes(state.order.destination_zone):
            if quote.quote_id == quote_id:
                return quote
        raise ToolExecutionError(f"Quote {quote_id} was not found during projection.")
