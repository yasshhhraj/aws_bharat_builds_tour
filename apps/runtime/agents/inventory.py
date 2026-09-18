"""Inventory role: establish the sourced shipment weight."""

from packages.domain.enums import AgentName
from packages.domain.models import InventoryFact, Order, TrajectoryState
from packages.governor import ObserverGovernor

from .base import BaseAgent


class InventoryAgent(BaseAgent):
    name = AgentName.INVENTORY

    def run(self, state: TrajectoryState, governor: ObserverGovernor) -> str:
        order = governor.execute_tool(
            state, self.name, "get_order", order_id=state.order_id
        )
        if not isinstance(order, Order):
            raise TypeError("get_order returned an invalid result.")
        fact = governor.execute_tool(
            state,
            self.name,
            "check_inventory",
            order_id=order.order_id,
            sku_id=order.sku_id,
            quantity=order.quantity,
        )
        if not isinstance(fact, InventoryFact):
            raise TypeError("check_inventory returned an invalid result.")
        state.order = order
        state.inventory_fact = fact
        return (
            f"Inventory Agent verified {fact.shipment_weight_kg} kg of available "
            f"stock from {fact.source_id}."
        )
