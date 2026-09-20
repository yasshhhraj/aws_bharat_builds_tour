"""Construct the selected role implementation without changing orchestration."""

from __future__ import annotations

from .agents import CarrierAgent, CustomerCommunicationsAgent, DispatchAgent, InventoryAgent
from .agents.base import BaseAgent
from .runtime_settings import RuntimeSettings
from .strands_agents import StrandsCarrierAgent, StrandsRoleAgent
from .strands_runtime import StrandsRuntime
from packages.domain.enums import AgentName


def build_runtime_agents(settings: RuntimeSettings) -> list[BaseAgent]:
    settings.validate()
    if settings.runtime_mode == "legacy":
        return [
            InventoryAgent(),
            DispatchAgent(),
            CarrierAgent(),
            CustomerCommunicationsAgent(),
        ]
    runtime = StrandsRuntime(settings)
    return [
        StrandsRoleAgent(AgentName.INVENTORY, runtime),
        StrandsRoleAgent(AgentName.DISPATCH, runtime),
        StrandsCarrierAgent(runtime),
        StrandsRoleAgent(AgentName.CUSTOMER_COMMUNICATIONS, runtime),
    ]
