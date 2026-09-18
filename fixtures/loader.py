"""Validation and loading for deterministic JSON fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from packages.domain.errors import FixtureError, OrderNotFoundError
from packages.domain.models import CarrierQuote, InventoryFact, Order, Vehicle


class FixtureLoader:
    def __init__(self, fixture_root: Path | None = None) -> None:
        self.root = fixture_root or Path(__file__).resolve().parent

    def _read_json(self, path: Path) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise FixtureError(f"Fixture file {path.name} is missing.") from exc
        except json.JSONDecodeError as exc:
            raise FixtureError(f"Fixture file {path.name} is not valid JSON.") from exc

    @staticmethod
    def _require(record: dict[str, Any], fields: set[str], label: str) -> None:
        missing = sorted(fields - record.keys())
        if missing:
            raise FixtureError(f"{label} is missing required fields: {', '.join(missing)}.")

    @staticmethod
    def _ensure_unique(records: list[dict[str, Any]], key: str, label: str) -> None:
        values = [record.get(key) for record in records]
        if any(value is None for value in values):
            raise FixtureError(f"A {label} record is missing {key}.")
        duplicates = sorted({value for value in values if values.count(value) > 1})
        if duplicates:
            raise FixtureError(
                f"Duplicate {label} IDs: {', '.join(str(value) for value in duplicates)}."
            )

    def list_orders(self) -> list[Order]:
        records = [self._read_json(path) for path in sorted((self.root / "orders").glob("*.json"))]
        self._ensure_unique(records, "order_id", "order")
        return [self._order_from_record(record) for record in records]

    def get_order(self, order_id: str) -> Order:
        path = self.root / "orders" / f"{order_id}.json"
        if not path.exists():
            raise OrderNotFoundError(f"Order {order_id} was not found.")
        return self._order_from_record(self._read_json(path))

    def get_inventory_fact(self, order: Order) -> InventoryFact:
        records = self._read_json(self.root / "inventory" / "inventory.json")
        if not isinstance(records, list):
            raise FixtureError("inventory.json must contain a list.")
        self._ensure_unique(records, "sku_id", "inventory SKU")
        required = {"sku_id", "available_quantity", "shipment_weight_kg", "source_id"}
        for record in records:
            self._require(record, required, "Inventory record")
            if record["sku_id"] == order.sku_id:
                if int(record["available_quantity"]) < order.quantity:
                    raise FixtureError(f"Insufficient inventory for {order.sku_id}.")
                return InventoryFact(
                    fact_id=f"WEIGHT-{order.order_id}",
                    sku_id=str(record["sku_id"]),
                    available_quantity=int(record["available_quantity"]),
                    shipment_weight_kg=int(record["shipment_weight_kg"]),
                    source_id=str(record["source_id"]),
                )
        raise FixtureError(f"No inventory record exists for {order.sku_id}.")

    def list_vehicles(self) -> list[Vehicle]:
        records = self._read_json(self.root / "vehicles" / "vehicles.json")
        if not isinstance(records, list):
            raise FixtureError("vehicles.json must contain a list.")
        self._ensure_unique(records, "vehicle_id", "vehicle")
        required = {"vehicle_id", "capacity_kg", "refrigerated", "available"}
        vehicles: list[Vehicle] = []
        for record in records:
            self._require(record, required, "Vehicle record")
            vehicles.append(
                Vehicle(
                    vehicle_id=str(record["vehicle_id"]),
                    capacity_kg=int(record["capacity_kg"]),
                    refrigerated=bool(record["refrigerated"]),
                    available=bool(record["available"]),
                )
            )
        return vehicles

    def list_carrier_quotes(self, destination_zone: str) -> list[CarrierQuote]:
        records = self._read_json(self.root / "carriers" / "carriers.json")
        if not isinstance(records, list):
            raise FixtureError("carriers.json must contain a list.")
        self._ensure_unique(records, "quote_id", "quote")
        required = {
            "quote_id",
            "carrier_id",
            "amount_minor",
            "currency",
            "cold_chain_certified",
            "lane_supported",
            "destination_zone",
        }
        quotes: list[CarrierQuote] = []
        for record in records:
            self._require(record, required, "Carrier record")
            if record["destination_zone"] != destination_zone:
                continue
            quotes.append(
                CarrierQuote(
                    quote_id=str(record["quote_id"]),
                    carrier_id=str(record["carrier_id"]),
                    amount_minor=int(record["amount_minor"]),
                    currency=str(record["currency"]),
                    cold_chain_certified=bool(record["cold_chain_certified"]),
                    lane_supported=bool(record["lane_supported"]),
                )
            )
        return quotes

    def validate_all(self) -> None:
        orders = self.list_orders()
        if not orders:
            raise FixtureError("At least one order fixture is required.")
        self.list_vehicles()
        for order in orders:
            self.get_inventory_fact(order)
            self.list_carrier_quotes(order.destination_zone)

    def _order_from_record(self, record: dict[str, Any]) -> Order:
        required = {
            "order_id",
            "sku_id",
            "quantity",
            "cargo_class",
            "destination_zone",
            "currency",
            "spend_ceiling_minor",
        }
        self._require(record, required, "Order record")
        return Order(
            order_id=str(record["order_id"]),
            sku_id=str(record["sku_id"]),
            quantity=int(record["quantity"]),
            cargo_class=str(record["cargo_class"]),
            destination_zone=str(record["destination_zone"]),
            currency=str(record["currency"]),
            spend_ceiling_minor=int(record["spend_ceiling_minor"]),
        )
