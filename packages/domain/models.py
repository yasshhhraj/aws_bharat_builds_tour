"""Core standard-library data models for the Checkpoint 1 runtime."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .enums import AgentName, EffectClass, EventType, RunStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_primitive(value: Any) -> Any:
    """Convert runtime objects to JSON-compatible primitives."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    if hasattr(value, "__dataclass_fields__"):
        return {key: to_primitive(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): to_primitive(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_primitive(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class Order:
    order_id: str
    sku_id: str
    quantity: int
    cargo_class: str
    destination_zone: str
    currency: str
    spend_ceiling_minor: int


@dataclass(frozen=True, slots=True)
class InventoryFact:
    fact_id: str
    sku_id: str
    available_quantity: int
    shipment_weight_kg: int
    source_id: str


@dataclass(frozen=True, slots=True)
class Vehicle:
    vehicle_id: str
    capacity_kg: int
    refrigerated: bool
    available: bool


@dataclass(frozen=True, slots=True)
class CarrierQuote:
    quote_id: str
    carrier_id: str
    amount_minor: int
    currency: str
    cold_chain_certified: bool
    lane_supported: bool


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    owner: AgentName
    effect_class: EffectClass
    description: str
    idempotent: bool


@dataclass(frozen=True, slots=True)
class TraceEvent:
    trace_id: str
    sequence: int
    event_type: EventType
    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    agent: AgentName | None = None
    tool_name: str | None = None
    effect_class: EffectClass | None = None
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class TrajectoryState:
    trace_id: str
    order_id: str
    status: RunStatus = RunStatus.PENDING
    current_agent: AgentName | None = None
    order: Order | None = None
    inventory_fact: InventoryFact | None = None
    selected_vehicle: Vehicle | None = None
    selected_quote: CarrierQuote | None = None
    dispatch_plan_id: str | None = None
    carrier_selection_id: str | None = None
    notification_id: str | None = None
    events: list[TraceEvent] = field(default_factory=list)
    next_sequence: int = 1
    tool_call_count: int = 0
    error: str | None = None


@dataclass(frozen=True, slots=True)
class RunSummary:
    trace_id: str
    order_id: str
    status: RunStatus
    current_agent: AgentName | None
    selected_vehicle_id: str | None
    selected_carrier_id: str | None
    selected_amount_minor: int | None
    notification_id: str | None
    event_count: int
    error: str | None

    @classmethod
    def from_state(cls, state: TrajectoryState) -> "RunSummary":
        return cls(
            trace_id=state.trace_id,
            order_id=state.order_id,
            status=state.status,
            current_agent=state.current_agent,
            selected_vehicle_id=(
                state.selected_vehicle.vehicle_id if state.selected_vehicle else None
            ),
            selected_carrier_id=(
                state.selected_quote.carrier_id if state.selected_quote else None
            ),
            selected_amount_minor=(
                state.selected_quote.amount_minor if state.selected_quote else None
            ),
            notification_id=state.notification_id,
            event_count=len(state.events),
            error=state.error,
        )


@dataclass(frozen=True, slots=True)
class OrderSummary:
    order_id: str
    cargo_class: str
    shipment_weight_kg: int
    currency: str


@dataclass(frozen=True, slots=True)
class ResetResult:
    status: str
    removed_run_count: int
