"""Four deterministic agent roles used by the walking skeleton."""

from .carrier import CarrierAgent
from .communications import CustomerCommunicationsAgent
from .dispatch import DispatchAgent
from .inventory import InventoryAgent

__all__ = [
    "CarrierAgent",
    "CustomerCommunicationsAgent",
    "DispatchAgent",
    "InventoryAgent",
]
