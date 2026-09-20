"""Dispatch role with bounded policy-guided replanning."""

from packages.domain.enums import AgentName, DecisionOutcome
from packages.domain.errors import NoSuitableVehicleError, PolicyBlockedError
from packages.domain.models import TrajectoryState, Vehicle
from packages.governor import ManifestGovernor

from apps.runtime.tool_result_projector import ToolResultProjector

from .base import BaseAgent


class DispatchAgent(BaseAgent):
    name = AgentName.DISPATCH

    def run(self, state: TrajectoryState, governor: ManifestGovernor) -> str:
        if state.order is None or state.inventory_fact is None or state.scenario_config is None:
            raise NoSuitableVehicleError("Dispatch requires a sourced inventory fact and scenario.")
        listed = governor.execute_tool(
            state, self.name, "list_available_vehicles",
            destination_zone=state.order.destination_zone,
        )
        if listed.value is None:
            raise PolicyBlockedError(listed.decision.because)
        vehicles = [item for item in listed.value if isinstance(item, Vehicle)]
        selected = self._find_vehicle(vehicles, state.scenario_config.preferred_vehicle_id)
        weight = state.scenario_config.attempted_weight_kg
        fact = state.inventory_fact

        result = governor.execute_tool(
            state, self.name, "create_dispatch_plan",
            order_id=state.order_id,
            vehicle_id=selected.vehicle_id,
            weight_value=weight,
            weight_unit="kg",
            weight_fact_id=fact.fact_id,
            idempotency_key=f"{state.trace_id}:dispatch-plan:1",
        )
        if result.decision.applied_outcome == DecisionOutcome.GUIDE:
            guidance = result.guidance or {}
            required = guidance.get("required_vehicle", {})
            corrected_weight = int(guidance.get("required_value", fact.shipment_weight_kg))
            candidates = [
                vehicle for vehicle in vehicles
                if vehicle.available
                and vehicle.capacity_kg >= int(required.get("minimum_capacity_kg") or corrected_weight)
                and (not required.get("refrigerated") or vehicle.refrigerated)
            ]
            if not candidates:
                raise NoSuitableVehicleError(f"No suitable vehicle can carry {corrected_weight} kg.")
            selected = sorted(candidates, key=lambda item: item.vehicle_id)[0]
            result = governor.execute_tool(
                state, self.name, "create_dispatch_plan",
                order_id=state.order_id,
                vehicle_id=selected.vehicle_id,
                weight_value=corrected_weight,
                weight_unit=str(guidance.get("required_unit", "kg")),
                weight_fact_id=str(guidance.get("required_fact_id", fact.fact_id)),
                idempotency_key=f"{state.trace_id}:dispatch-plan:2",
            )
            weight = corrected_weight
        if result.value is None:
            raise PolicyBlockedError(result.decision.because)
        ToolResultProjector(governor.loader).project(
            state,
            self.name,
            "create_dispatch_plan",
            {"vehicle_id": selected.vehicle_id},
            result.value,
        )
        return f"Dispatch Agent selected vehicle {selected.vehicle_id} for {weight} kg."

    @staticmethod
    def _find_vehicle(vehicles: list[Vehicle], vehicle_id: str) -> Vehicle:
        for vehicle in vehicles:
            if vehicle.vehicle_id == vehicle_id:
                return vehicle
        raise NoSuitableVehicleError(f"Preferred vehicle {vehicle_id} is unavailable.")
