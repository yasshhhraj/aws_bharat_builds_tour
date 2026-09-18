"""Application service shared by the CLI and HTTP API."""

from __future__ import annotations

from fixtures import FixtureLoader
from packages.domain.errors import UnsupportedModeError
from packages.domain.models import OrderSummary, ResetResult, RunSummary, TraceEvent
from packages.governor import ObserverGovernor
from packages.ledger import MemoryTraceStore
from packages.tools import MockLogisticsTools, build_tool_registry

from .agents import (
    CarrierAgent,
    CustomerCommunicationsAgent,
    DispatchAgent,
    InventoryAgent,
)
from .orchestrator import ShipmentOrchestrator


class RunService:
    def __init__(
        self,
        loader: FixtureLoader,
        store: MemoryTraceStore,
        mocks: MockLogisticsTools,
        orchestrator: ShipmentOrchestrator,
    ) -> None:
        self.loader = loader
        self.store = store
        self.mocks = mocks
        self.orchestrator = orchestrator

    def start_run(self, order_id: str, mode: str = "shadow") -> RunSummary:
        if mode != "shadow":
            raise UnsupportedModeError(
                "Checkpoint 1 supports only shadow mode."
            )
        self.loader.get_order(order_id)
        state = self.orchestrator.run(order_id)
        return RunSummary.from_state(state)

    def get_run(self, trace_id: str) -> RunSummary:
        return RunSummary.from_state(self.store.get_state(trace_id))

    def get_events(self, trace_id: str) -> list[TraceEvent]:
        return self.store.get_events(trace_id)

    def list_orders(self) -> list[OrderSummary]:
        summaries: list[OrderSummary] = []
        for order in self.loader.list_orders():
            fact = self.loader.get_inventory_fact(order)
            summaries.append(
                OrderSummary(
                    order_id=order.order_id,
                    cargo_class=order.cargo_class,
                    shipment_weight_kg=fact.shipment_weight_kg,
                    currency=order.currency,
                )
            )
        return summaries

    def reset_demo(self) -> ResetResult:
        removed = self.store.reset()
        self.mocks.reset()
        return ResetResult(status="reset", removed_run_count=removed)


def build_run_service() -> RunService:
    loader = FixtureLoader()
    loader.validate_all()
    store = MemoryTraceStore()
    registry, mocks = build_tool_registry(loader)
    governor = ObserverGovernor(registry, store)
    agents = [
        InventoryAgent(),
        DispatchAgent(),
        CarrierAgent(),
        CustomerCommunicationsAgent(),
    ]
    orchestrator = ShipmentOrchestrator(agents, governor, store)
    return RunService(loader, store, mocks, orchestrator)
