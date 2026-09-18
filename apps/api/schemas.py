"""Pydantic schemas for the Checkpoint 3 HTTP boundary."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    order_id: str = Field(min_length=1)
    mode: Literal["shadow", "enforce"] = "enforce"
    scenario: Literal["benign", "adversarial"] = "benign"


class RunResponse(BaseModel):
    trace_id: str
    order_id: str
    status: str
    current_agent: str | None
    mode: str
    scenario: str
    policy_version: str
    policy_engine: str
    workflow_stage: str
    selected_vehicle_id: str | None
    selected_carrier_id: str | None
    selected_amount_minor: int | None
    notification_id: str | None
    confirmed_booking_id: str | None
    spend_committed_minor: int
    spend_reserved_minor: int
    projected_spend_minor: int
    spend_ceiling_minor: int | None
    pending_approval_id: str | None
    decision_count: int
    event_count: int
    error: str | None
    terminal_reason: str | None


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


class DecisionResponse(BaseModel):
    decision_id: str
    request_id: str
    trace_id: str
    proposal_id: str
    agent: str
    tool_name: str
    effect_class: str | None
    policy_outcome: str
    applied_outcome: str
    enforced: bool
    reason_code: str
    because: str
    reasons: list[dict[str, Any]]
    guidance: dict[str, Any] | None
    policy_version: str
    engine_name: str
    evaluation_ms: float
    created_at: str


class DecisionsResponse(BaseModel):
    trace_id: str
    items: list[DecisionResponse]


class ApprovalResponse(BaseModel):
    approval_id: str
    trace_id: str
    prepared_action_id: str
    action_hash: str
    state_hash: str
    policy_version: str
    reason_code: str
    status: str
    created_at: str
    expires_at: str
    version: int
    decided_at: str | None
    decision: str | None
    approver_label: str | None
    comment: str | None


class ApprovalDecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    approver_label: str = Field(
        min_length=3,
        max_length=64,
        pattern=r"^DEMO-APPROVER-[A-Z0-9-]+$",
    )
    comment: str | None = Field(default=None, max_length=280)
    expected_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=128)


class ApprovalDecisionResponse(BaseModel):
    approval: ApprovalResponse
    run: RunResponse
    idempotent_replay: bool


class ApprovalsResponse(BaseModel):
    items: list[ApprovalResponse]


class OrderResponse(BaseModel):
    order_id: str
    cargo_class: str
    shipment_weight_kg: int
    currency: str
    scenarios: list[str]


class OrdersResponse(BaseModel):
    items: list[OrderResponse]


class HealthResponse(BaseModel):
    status: str
    version: str
    runtime_mode: str
    governor_mode: str
    policy_engine: str
    policy_version: str
    storage_mode: str
    fixture_count: int
    supported_modes: list[str]
    supported_scenarios: list[str]
    approval_mode: str
    approval_auth_mode: str
    approval_mutation_ready: bool


class ResetResponse(BaseModel):
    status: str
    removed_run_count: int
