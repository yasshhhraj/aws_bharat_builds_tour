"""Pydantic schemas for the Checkpoint 1 HTTP boundary."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    order_id: str = Field(min_length=1)
    mode: Literal["shadow"] = "shadow"


class RunResponse(BaseModel):
    trace_id: str
    order_id: str
    status: str
    current_agent: str | None
    selected_vehicle_id: str | None
    selected_carrier_id: str | None
    selected_amount_minor: int | None
    notification_id: str | None
    event_count: int
    error: str | None


class EventResponse(BaseModel):
    trace_id: str
    sequence: int
    event_type: str
    agent: str | None
    tool_name: str | None
    effect_class: str | None
    summary: str
    details: dict[str, Any]
    occurred_at: str


class EventsResponse(BaseModel):
    trace_id: str
    items: list[EventResponse]


class OrderResponse(BaseModel):
    order_id: str
    cargo_class: str
    shipment_weight_kg: int
    currency: str


class OrdersResponse(BaseModel):
    items: list[OrderResponse]


class HealthResponse(BaseModel):
    status: str
    version: str
    runtime_mode: str
    governor_mode: str
    storage_mode: str
    fixture_count: int


class ResetResponse(BaseModel):
    status: str
    removed_run_count: int
