"""Deterministic, side-effect-free logistics adapters."""

from __future__ import annotations

from threading import RLock
from typing import Any

from fixtures import FixtureLoader
from packages.domain.errors import FixtureError


class MockLogisticsTools:
    def __init__(self, loader: FixtureLoader) -> None:
        self.loader = loader
        self._dispatch_plans: dict[str, dict[str, Any]] = {}
        self._carrier_selections: dict[str, dict[str, Any]] = {}
        self._outbox: dict[str, dict[str, Any]] = {}
        self._lock = RLock()

    def get_order(self, order_id: str):
        return self.loader.get_order(order_id)

    def check_inventory(self, order_id: str, sku_id: str, quantity: int):
        order = self.loader.get_order(order_id)
        if order.sku_id != sku_id or order.quantity != quantity:
            raise FixtureError(f"Inventory request does not match order {order_id}.")
        return self.loader.get_inventory_fact(order)

    def list_available_vehicles(self, destination_zone: str):
        if not destination_zone:
            raise FixtureError("A destination zone is required.")
        return [vehicle for vehicle in self.loader.list_vehicles() if vehicle.available]

    def create_dispatch_plan(
        self,
        order_id: str,
        vehicle_id: str,
        weight_kg: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        vehicles = {vehicle.vehicle_id: vehicle for vehicle in self.loader.list_vehicles()}
        vehicle = vehicles.get(vehicle_id)
        if vehicle is None:
            raise FixtureError(f"Vehicle {vehicle_id} was not found.")
        if not vehicle.available or vehicle.capacity_kg < weight_kg:
            raise FixtureError(f"Vehicle {vehicle_id} cannot carry {weight_kg} kg.")
        with self._lock:
            if idempotency_key not in self._dispatch_plans:
                self._dispatch_plans[idempotency_key] = {
                    "plan_id": f"PLAN-{order_id}-{vehicle_id}",
                    "order_id": order_id,
                    "vehicle_id": vehicle_id,
                    "weight_kg": weight_kg,
                }
            return dict(self._dispatch_plans[idempotency_key])

    def list_carrier_quotes(self, order_id: str, destination_zone: str):
        self.loader.get_order(order_id)
        return self.loader.list_carrier_quotes(destination_zone)

    def select_carrier_quote(
        self, order_id: str, quote_id: str, idempotency_key: str
    ) -> dict[str, Any]:
        order = self.loader.get_order(order_id)
        quotes = {
            quote.quote_id: quote
            for quote in self.loader.list_carrier_quotes(order.destination_zone)
        }
        if quote_id not in quotes:
            raise FixtureError(f"Quote {quote_id} was not found for {order_id}.")
        with self._lock:
            if idempotency_key not in self._carrier_selections:
                self._carrier_selections[idempotency_key] = {
                    "selection_id": f"SELECTION-{order_id}-{quote_id}",
                    "order_id": order_id,
                    "quote_id": quote_id,
                }
            return dict(self._carrier_selections[idempotency_key])

    def write_tracking_outbox(
        self, order_id: str, message: str, idempotency_key: str
    ) -> dict[str, Any]:
        self.loader.get_order(order_id)
        if not message.strip():
            raise FixtureError("Tracking message cannot be empty.")
        with self._lock:
            if idempotency_key not in self._outbox:
                self._outbox[idempotency_key] = {
                    "notification_id": f"NOTIFY-{order_id}",
                    "order_id": order_id,
                    "message": message,
                    "delivery": "simulated_outbox",
                }
            return dict(self._outbox[idempotency_key])

    def reset(self) -> None:
        with self._lock:
            self._dispatch_plans.clear()
            self._carrier_selections.clear()
            self._outbox.clear()
