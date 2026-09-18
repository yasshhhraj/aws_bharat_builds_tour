from fixtures import FixtureLoader
from packages.domain.errors import FixtureError, IdempotencyConflictError
from packages.tools.mocks import MockLogisticsTools
import pytest


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


def test_idempotency_key_cannot_be_reused_with_different_arguments():
    mocks = MockLogisticsTools(FixtureLoader())
    mocks.create_dispatch_plan("ORD-8842", "VEH-COLD-01", "same-key", weight_value=500)
    with pytest.raises(IdempotencyConflictError):
        mocks.create_dispatch_plan("ORD-8842", "VEH-COLD-01", "same-key", weight_value=400)


def test_prepared_booking_cancellation_is_idempotent_and_prevents_confirmation():
    mocks = MockLogisticsTools(FixtureLoader())
    prepared = mocks.prepare_freight_booking(
        "ORD-8842", "QUOTE-COLD-01", 90000, "INR", "prepare-key"
    )
    arguments = {
        "prepared_action_id": prepared["prepared_action_id"],
        "action_hash": "sha256:synthetic",
        "cancellation_reason_code": "APPROVAL_REJECTED",
        "idempotency_key": "cancel-key",
    }

    assert mocks.cancel_freight_booking(**arguments) == mocks.cancel_freight_booking(
        **arguments
    )
    assert mocks.cancelled_booking_count == 1
    with pytest.raises(FixtureError, match="cancelled"):
        mocks.confirm_freight_booking(
            prepared["prepared_action_id"], "sha256:synthetic", "confirm-after-cancel"
        )
