"""Dispatch role: choose a suitable synthetic vehicle."""

from packages.domain.enums import AgentName
from packages.domain.errors import NoSuitableVehicleError
from packages.domain.models import TrajectoryState, Vehicle
from packages.governor import ObserverGovernor

from .base import BaseAgent


class DispatchAgent(BaseAgent):
    name = AgentName.DISPATCH

    def run(self, state: TrajectoryState, governor: ObserverGovernor) -> str:
        if state.order is None or state.inventory_fact is None:
            raise NoSuitableVehicleError("Dispatch requires a sourced inventory fact.")
        vehicles = governor.execute_tool(
            state,
            self.name,
            "list_available_vehicles",
            destination_zone=state.order.destination_zone,
        )
        requires_refrigeration = state.order.cargo_class == "perishable"
        candidates = [
            vehicle
            for vehicle in vehicles
            if isinstance(vehicle, Vehicle)
            and vehicle.available
            and vehicle.capacity_kg >= state.inventory_fact.shipment_weight_kg
            and (not requires_refrigeration or vehicle.refrigerated)
        ]
        if not candidates:
            raise NoSuitableVehicleError(
                f"No suitable vehicle can carry {state.inventory_fact.shipment_weight_kg} kg."
            )
        selected = sorted(candidates, key=lambda vehicle: vehicle.vehicle_id)[0]
        plan = governor.execute_tool(
            state,
            self.name,
            "create_dispatch_plan",
            order_id=state.order_id,
            vehicle_id=selected.vehicle_id,
            weight_kg=state.inventory_fact.shipment_weight_kg,
            idempotency_key=f"{state.trace_id}:dispatch-plan",
        )
        state.selected_vehicle = selected
        state.dispatch_plan_id = str(plan["plan_id"])
        return (
            f"Dispatch Agent selected refrigerated vehicle {selected.vehicle_id} "
            f"for {state.inventory_fact.shipment_weight_kg} kg."
        )
