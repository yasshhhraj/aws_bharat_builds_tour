import json

import pytest

from fixtures import FixtureLoader
from packages.domain.errors import FixtureError, OrderNotFoundError


def test_primary_fixture_is_stable():
    loader = FixtureLoader()
    order = loader.get_order("ORD-8842")
    fact = loader.get_inventory_fact(order)

    assert order.cargo_class == "perishable"
    assert order.spend_ceiling_minor == 400000
    assert fact.fact_id == "WEIGHT-ORD-8842"
    assert fact.shipment_weight_kg == 500
    assert fact.source_id == "WMS-SNAPSHOT-001"


def test_fixture_loader_returns_fresh_lists():
    loader = FixtureLoader()
    first = loader.list_vehicles()
    second = loader.list_vehicles()

    assert first == second
    assert first is not second


def test_unknown_order_has_typed_error():
    with pytest.raises(OrderNotFoundError, match="UNKNOWN"):
        FixtureLoader().get_order("UNKNOWN")


def test_missing_required_order_field_is_rejected(tmp_path):
    root = tmp_path
    (root / "orders").mkdir()
    (root / "orders" / "BROKEN.json").write_text(
        json.dumps({"order_id": "BROKEN"}), encoding="utf-8"
    )

    with pytest.raises(FixtureError, match="missing required fields"):
        FixtureLoader(root).list_orders()
