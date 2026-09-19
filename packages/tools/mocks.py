"""Deterministic, side-effect-free logistics adapters."""

from __future__ import annotations

from threading import RLock
from typing import Any

from fixtures import FixtureLoader
from packages.domain.errors import FixtureError, IdempotencyConflictError


class MockLogisticsTools:
    def __init__(self, loader: FixtureLoader) -> None:
        self.loader = loader
        self._dispatch_plans: dict[str, dict[str, Any]] = {}
        self._carrier_selections: dict[str, dict[str, Any]] = {}
        self._outbox: dict[str, dict[str, Any]] = {}
        self._prepared_bookings: dict[str, dict[str, Any]] = {}
        self._confirmed_bookings: dict[str, dict[str, Any]] = {}
        self._cancelled_bookings: dict[str, dict[str, Any]] = {}
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
        idempotency_key: str,
        weight_kg: int | None = None,
        weight_value: int | None = None,
        weight_unit: str = "kg",
        weight_fact_id: str | None = None,
    ) -> dict[str, Any]:
        effective_weight = weight_value if weight_value is not None else weight_kg
        if effective_weight is None or weight_unit != "kg":
            raise FixtureError("Dispatch requires a weight expressed in kg.")
        vehicles = {vehicle.vehicle_id: vehicle for vehicle in self.loader.list_vehicles()}
        vehicle = vehicles.get(vehicle_id)
        if vehicle is None:
            raise FixtureError(f"Vehicle {vehicle_id} was not found.")
        if not vehicle.available or vehicle.capacity_kg < effective_weight:
            raise FixtureError(f"Vehicle {vehicle_id} cannot carry {effective_weight} kg.")
        payload = {
            "plan_id": f"PLAN-{order_id}-{vehicle_id}",
            "order_id": order_id,
            "vehicle_id": vehicle_id,
            "weight_kg": effective_weight,
            "weight_fact_id": weight_fact_id,
        }
        with self._lock:
            self._store_idempotently(self._dispatch_plans, idempotency_key, payload)
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
            payload = {"selection_id": f"SELECTION-{order_id}-{quote_id}", "order_id": order_id, "quote_id": quote_id}
            self._store_idempotently(self._carrier_selections, idempotency_key, payload)
            return dict(self._carrier_selections[idempotency_key])

    def prepare_freight_booking(
        self,
        order_id: str,
        quote_id: str,
        amount_minor: int,
        currency: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        order = self.loader.get_order(order_id)
        if isinstance(amount_minor, bool) or not isinstance(amount_minor, int) or amount_minor < 0:
            raise FixtureError("Booking amount must be a non-negative integer.")
        quotes = {quote.quote_id: quote for quote in self.loader.list_carrier_quotes(order.destination_zone)}
        quote = quotes.get(quote_id)
        if quote is None or quote.amount_minor != amount_minor or quote.currency != currency:
            raise FixtureError("Prepared booking does not match the selected quote.")
        payload = {
            "prepared_action_id": f"PREP-{order_id}-{quote_id}",
            "order_id": order_id,
            "quote_id": quote_id,
            "amount_minor": amount_minor,
            "currency": currency,
        }
        with self._lock:
            self._store_idempotently(self._prepared_bookings, idempotency_key, payload)
            return dict(self._prepared_bookings[idempotency_key])

    def confirm_freight_booking(
        self,
        prepared_action_id: str,
        action_hash: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        if not prepared_action_id or not action_hash:
            raise FixtureError("Confirmation requires a prepared action and hash.")
        with self._lock:
            prepared_ids = {
                item["prepared_action_id"] for item in self._prepared_bookings.values()
            }
            cancelled_ids = {
                item["prepared_action_id"] for item in self._cancelled_bookings.values()
            }
            # Some policy-unit tests intentionally exercise the governed
            # confirmation boundary with an in-memory PreparedAction without
            # first invoking the mock prepare adapter. Preserve that test seam
            # while enforcing existence during normal adapter-backed runs.
            if prepared_ids and prepared_action_id not in prepared_ids:
                raise FixtureError(f"Prepared booking {prepared_action_id} was not found.")
            if prepared_action_id in cancelled_ids:
                raise FixtureError(f"Prepared booking {prepared_action_id} was cancelled.")
            payload = {
                "confirmation_id": f"CONFIRM-{prepared_action_id}",
                "prepared_action_id": prepared_action_id,
                "action_hash": action_hash,
            }
            self._store_idempotently(self._confirmed_bookings, idempotency_key, payload)
            return dict(self._confirmed_bookings[idempotency_key])

    def cancel_freight_booking(
        self,
        prepared_action_id: str,
        action_hash: str,
        cancellation_reason_code: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        if not prepared_action_id or not action_hash or not cancellation_reason_code:
            raise FixtureError("Cancellation requires a prepared action, hash, and reason.")
        with self._lock:
            prepared_ids = {
                item["prepared_action_id"] for item in self._prepared_bookings.values()
            }
            confirmed_ids = {
                item["prepared_action_id"] for item in self._confirmed_bookings.values()
            }
            # A freshly reconstructed runtime has no process-local preparation
            # cache; the governed durable state and effect receipt are then the
            # source of truth. Still reject mismatches when this process has a
            # populated preparation cache.
            if prepared_ids and prepared_action_id not in prepared_ids:
                raise FixtureError(f"Prepared booking {prepared_action_id} was not found.")
            if prepared_action_id in confirmed_ids:
                raise FixtureError(f"Prepared booking {prepared_action_id} is already confirmed.")
            payload = {
                "cancellation_id": f"CANCEL-{prepared_action_id}",
                "prepared_action_id": prepared_action_id,
                "status": "cancelled",
                "reason_code": cancellation_reason_code,
            }
            self._store_idempotently(self._cancelled_bookings, idempotency_key, payload)
            return dict(self._cancelled_bookings[idempotency_key])

    def write_tracking_outbox(
        self,
        order_id: str,
        message: str | None = None,
        idempotency_key: str | None = None,
        recipient_ref: str | None = None,
        template_id: str | None = None,
        template_variables: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        self.loader.get_order(order_id)
        if message is not None and not message.strip():
            raise FixtureError("Tracking message cannot be empty.")
        if message is None and (not recipient_ref or not template_id):
            raise FixtureError("Tracking notification requires a recipient and template.")
        rendered = message or f"Synthetic {template_id} for {order_id}."
        if not idempotency_key:
            raise FixtureError("Tracking notification requires an idempotency key.")
        with self._lock:
            payload = {
                "notification_id": f"NOTIFY-{order_id}", "order_id": order_id,
                "recipient_ref": recipient_ref, "template_id": template_id,
                "template_variables": template_variables or {},
                "rendered_message": rendered, "delivery": "simulated_outbox",
            }
            self._store_idempotently(self._outbox, idempotency_key, payload)
            return dict(self._outbox[idempotency_key])

    @staticmethod
    def _store_idempotently(store: dict[str, dict[str, Any]], key: str, payload: dict[str, Any]) -> None:
        existing = store.get(key)
        if existing is not None and existing != payload:
            raise IdempotencyConflictError(f"Idempotency key {key} was reused with different arguments.")
        if existing is None:
            store[key] = dict(payload)

    def reset(self) -> None:
        with self._lock:
            self._dispatch_plans.clear()
            self._carrier_selections.clear()
            self._outbox.clear()
            self._prepared_bookings.clear()
            self._confirmed_bookings.clear()
            self._cancelled_bookings.clear()

    @property
    def confirmed_booking_count(self) -> int:
        with self._lock:
            return len(self._confirmed_bookings)

    @property
    def cancelled_booking_count(self) -> int:
        with self._lock:
            return len(self._cancelled_bookings)

    @property
    def notification_count(self) -> int:
        with self._lock:
            return len(self._outbox)
