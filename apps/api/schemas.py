"""Pydantic schemas for the Manifest HTTP boundary."""

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
    event_id: str
    trace_id: str
    sequence: int
    event_type: str
    agent: str | None
    tool_name: str | None
    effect_class: str | None
    summary: str
    details: dict[str, Any]
    occurred_at: str
    schema_version: str
    previous_hash: str
    event_hash: str
    idempotency_key: str | None


class EventsResponse(BaseModel):
    trace_id: str
    items: list[EventResponse]


class VerificationResponse(BaseModel):
    trace_id: str
    valid: bool
    checked_event_count: int
    first_bad_sequence: int | None
    failure_code: str | None
    stored_head_sequence: int
    stored_head_hash: str
    computed_head_hash: str
    algorithm: str
    schema_version: str
    verified_at: str


class RiskSignalPointResponse(BaseModel):
    sequence: int
    decision_id: str
    family: str
    reason_code: str
    outcome: str
    delta: int
    total: int


class SpendPointResponse(BaseModel):
    sequence: int
    label: str
    committed_minor: int
    reserved_minor: int
    projected_minor: int
    ceiling_minor: int


class WeightAttemptResponse(BaseModel):
    sequence: int
    proposal_id: str
    attempted_value: int
    unit: str
    fact_id: str
    policy_outcome: str
    reason_code: str


class WeightProvenanceResponse(BaseModel):
    fact_id: str
    authoritative_value: int
    unit: str
    source_id: str
    source_hash: str
    attempts: list[WeightAttemptResponse]
    final_value: int | None


class DashboardProjectionResponse(BaseModel):
    trace_id: str
    risk_signal_score: int
    risk_signal_method: str
    risk_points: list[RiskSignalPointResponse]
    spend_points: list[SpendPointResponse]
    weight_provenance: WeightProvenanceResponse | None


class TamperRequest(BaseModel):
    sequence: int = Field(ge=1)
    replacement_summary: str = Field(min_length=1, max_length=280)


class TamperResponse(BaseModel):
    trace_id: str
    sequence: int
    field: str
    status: str


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
    policy_bundle_hash: str | None = None
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
    model_provider: str
    model_id: str
    requested_model_id: str
    resolved_model_id: str | None
    provider_route_kind: str
    agent_max_turns: int
    agent_timeout_seconds: float
    model_max_output_tokens: int
    provider_fallback_active: bool
    governor_mode: str
    policy_engine: str
    policy_version: str
    policy_engine_ready: bool = True
    policy_bundle_hash: str | None = None
    policy_schema_hash: str | None = None
    cedar_runtime_version: str | None = None
    policy_fallback_active: bool = False
    storage_mode: str
    fixture_count: int
    supported_modes: list[str]
    supported_scenarios: list[str]
    approval_mode: str
    approval_auth_mode: str
    approval_mutation_ready: bool
    ledger_algorithm: str
    ledger_schema_version: str
    verify_ready: bool
    demo_tamper_enabled: bool
    demo_tamper_mutation_ready: bool
    dashboard_mode: str
    dashboard_ready: bool
    projection_version: str


class ResetResponse(BaseModel):
    status: str
    removed_run_count: int
