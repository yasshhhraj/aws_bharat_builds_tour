"""Inventory role: establish the sourced shipment weight."""

from packages.domain.enums import AgentName
from packages.domain.models import InventoryFact, Order, TrajectoryState
from packages.governor import ManifestGovernor

from apps.runtime.tool_result_projector import ToolResultProjector

from .base import BaseAgent


class InventoryAgent(BaseAgent):
    name = AgentName.INVENTORY

    def run(self, state: TrajectoryState, governor: ManifestGovernor) -> str:
        order_result = governor.execute_tool(
            state, self.name, "get_order", order_id=state.order_id
        )
        order = getattr(order_result, "value", order_result)
        if not isinstance(order, Order):
            raise TypeError("get_order returned an invalid result.")
        projector = ToolResultProjector(governor.loader)
        projector.project(state, self.name, "get_order", {"order_id": state.order_id}, order)
        fact_result = governor.execute_tool(
            state,
            self.name,
            "check_inventory",
            order_id=order.order_id,
            sku_id=order.sku_id,
            quantity=order.quantity,
        )
        fact = getattr(fact_result, "value", fact_result)
        if not isinstance(fact, InventoryFact):
            raise TypeError("check_inventory returned an invalid result.")
        projector.project(
            state,
            self.name,
            "check_inventory",
            {"order_id": order.order_id, "sku_id": order.sku_id, "quantity": order.quantity},
            fact,
        )
        return (
            f"Inventory Agent verified {fact.shipment_weight_kg} kg of available "
            f"stock from {fact.source_id}."
        )
