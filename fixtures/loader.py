"""Validation and loading for deterministic JSON fixtures."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

from packages.domain.errors import FixtureError, OrderNotFoundError
from packages.domain.enums import EffectClass, GovernanceMode, ScenarioName
from packages.domain.errors import UnsupportedScenarioError
from packages.domain.models import (
    CarrierQuote,
    InventoryFact,
    Order,
    ScenarioConfig,
    ShipmentMandate,
    Vehicle,
)


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
                    source_hash=self._source_hash(
                        order.order_id,
                        str(record["source_id"]),
                        int(record["shipment_weight_kg"]),
                    ),
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
            for scenario in ScenarioName:
                self.get_scenario(order.order_id, scenario)
            self.get_mandate(order, GovernanceMode.ENFORCE)

    def get_mandate(self, order: Order, mode: GovernanceMode) -> ShipmentMandate:
        record = self._read_json(self.root / "mandates" / f"M-{order.order_id.removeprefix('ORD-')}-1.json")
        required = {
            "mandate_id",
            "order_id",
            "currency",
            "spend_ceiling_minor",
            "approval_threshold_minor",
            "cargo_class",
            "allowed_effect_classes",
            "policy_version",
        }
        self._require(record, required, "Mandate")
        if str(record["order_id"]) != order.order_id:
            raise FixtureError("Mandate order does not match the requested order.")
        if str(record["currency"]) != order.currency:
            raise FixtureError("Mandate currency does not match the order.")
        if int(record["spend_ceiling_minor"]) != order.spend_ceiling_minor:
            raise FixtureError("Mandate spend ceiling does not match the order.")
        if str(record["cargo_class"]) != order.cargo_class:
            raise FixtureError("Mandate cargo class does not match the order.")
        if not str(record["policy_version"]).strip():
            raise FixtureError("Mandate policy version cannot be empty.")
        try:
            effects = frozenset(EffectClass(value) for value in record["allowed_effect_classes"])
        except (TypeError, ValueError) as exc:
            raise FixtureError("Mandate contains an invalid effect class.") from exc
        ceiling = self._non_negative_int(record["spend_ceiling_minor"], "spend ceiling")
        threshold = self._non_negative_int(record["approval_threshold_minor"], "approval threshold")
        if not effects:
            raise FixtureError("Mandate must allow at least one effect class.")
        return ShipmentMandate(
            mandate_id=str(record["mandate_id"]),
            order_id=order.order_id,
            mode=mode,
            currency=order.currency,
            spend_ceiling_minor=ceiling,
            approval_threshold_minor=threshold,
            cargo_class=str(record["cargo_class"]),
            allowed_effect_classes=effects,
            policy_version=str(record["policy_version"]),
        )

    def get_scenario(
        self, order_id: str, scenario: ScenarioName | str
    ) -> ScenarioConfig:
        try:
            name = scenario if isinstance(scenario, ScenarioName) else ScenarioName(scenario)
        except ValueError as exc:
            raise UnsupportedScenarioError(f"Scenario {scenario} is not supported.") from exc
        path = self.root / "scenarios" / f"{order_id}-{name.value}.json"
        record = self._read_json(path)
        self._require(record, {"scenario", "prior_committed_minor", "dispatch", "carrier"}, "Scenario")
        dispatch = record["dispatch"]
        carrier = record["carrier"]
        if not isinstance(dispatch, dict) or not isinstance(carrier, dict):
            raise FixtureError("Scenario dispatch and carrier settings must be objects.")
        self._require(dispatch, {"attempted_weight_kg", "preferred_vehicle_id"}, "Scenario dispatch")
        self._require(carrier, {"preferred_quote_id"}, "Scenario carrier")
        if str(record["scenario"]) != name.value:
            raise FixtureError("Scenario name does not match its fixture file.")
        prior = self._non_negative_int(record["prior_committed_minor"], "prior committed spend")
        weight = self._non_negative_int(dispatch["attempted_weight_kg"], "attempted weight")
        vehicles = {item.vehicle_id for item in self.list_vehicles()}
        order = self.get_order(order_id)
        quotes = {item.quote_id for item in self.list_carrier_quotes(order.destination_zone)}
        if str(dispatch["preferred_vehicle_id"]) not in vehicles:
            raise FixtureError("Scenario references an unknown vehicle.")
        if str(carrier["preferred_quote_id"]) not in quotes:
            raise FixtureError("Scenario references an unknown carrier quote.")
        return ScenarioConfig(
            name=name,
            prior_committed_minor=prior,
            attempted_weight_kg=weight,
            preferred_vehicle_id=str(dispatch["preferred_vehicle_id"]),
            preferred_quote_id=str(carrier["preferred_quote_id"]),
        )

    @staticmethod
    def _source_hash(order_id: str, source_id: str, value: int) -> str:
        payload = json.dumps(
            {"name": "shipment_weight", "order_id": order_id, "source_id": source_id, "unit": "kg", "value": value},
            sort_keys=True,
            separators=(",", ":"),
        )
        return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _non_negative_int(value: Any, label: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise FixtureError(f"{label.capitalize()} must be a non-negative integer.")
        return value

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
