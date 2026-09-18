from fixtures import FixtureLoader
from packages.tools.mocks import MockLogisticsTools


def test_mock_writes_are_idempotent():
    mocks = MockLogisticsTools(FixtureLoader())
    arguments = {
        "order_id": "ORD-8842",
        "vehicle_id": "VEH-COLD-01",
        "weight_kg": 500,
        "idempotency_key": "same-key",
    }

    assert mocks.create_dispatch_plan(**arguments) == mocks.create_dispatch_plan(
        **arguments
    )


def test_mock_outbox_is_simulated():
    result = MockLogisticsTools(FixtureLoader()).write_tracking_outbox(
        "ORD-8842", "Synthetic message", "outbox-key"
    )

    assert result["notification_id"] == "NOTIFY-ORD-8842"
    assert result["delivery"] == "simulated_outbox"
