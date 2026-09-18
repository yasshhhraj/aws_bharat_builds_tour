import pytest

from apps.runtime.agents import (
    CarrierAgent,
    CustomerCommunicationsAgent,
    DispatchAgent,
)
from packages.domain.errors import (
    ManifestError,
    NoSuitableCarrierError,
    NoSuitableVehicleError,
)
from packages.domain.models import TrajectoryState


def test_dispatch_requires_inventory_fact():
    with pytest.raises(NoSuitableVehicleError):
        DispatchAgent().run(TrajectoryState("TR-1", "ORD-8842"), None)


def test_carrier_requires_dispatch_plan():
    with pytest.raises(NoSuitableCarrierError):
        CarrierAgent().run(TrajectoryState("TR-1", "ORD-8842"), None)


def test_communications_requires_selected_carrier():
    with pytest.raises(ManifestError, match="carrier"):
        CustomerCommunicationsAgent().run(
            TrajectoryState("TR-1", "ORD-8842"), None
        )
