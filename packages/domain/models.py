"""Typed domain contracts shared by the Manifest runtime and API."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .enums import (
    AgentName,
    ApprovalDecision,
    ApprovalStatus,
    CommitmentStatus,
    DecisionOutcome,
    EffectClass,
    EventType,
    GovernanceMode,
    RunStatus,
    ScenarioName,
    WorkflowStage,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_primitive(value: Any) -> Any:
    """Convert runtime values into JSON-compatible primitives."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    if hasattr(value, "__dataclass_fields__"):
        return {key: to_primitive(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): to_primitive(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
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
    source_hash: str = ""


@dataclass(frozen=True, slots=True)
class NumericFact:
    fact_id: str
    name: str
    value: int
    unit: str
    source_id: str
    source_hash: str
    created_by_tool: str


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
    quote_issuer: str = "synthetic_carrier_adapter"


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    owner: AgentName
    effect_class: EffectClass
    description: str
    idempotent: bool


@dataclass(frozen=True, slots=True)
class ShipmentMandate:
    mandate_id: str
    order_id: str
    mode: GovernanceMode
    currency: str
    spend_ceiling_minor: int
    approval_threshold_minor: int
    cargo_class: str
    allowed_effect_classes: frozenset[EffectClass]
    policy_version: str


@dataclass(frozen=True, slots=True)
class ScenarioConfig:
    name: ScenarioName
    prior_committed_minor: int
    attempted_weight_kg: int
    preferred_vehicle_id: str
    preferred_quote_id: str


@dataclass(frozen=True, slots=True)
class ToolProposal:
    proposal_id: str
    trace_id: str
    agent: AgentName
    tool_name: str
    effect_class: EffectClass | None
    arguments: dict[str, Any]
    attempt: int


@dataclass(frozen=True, slots=True)
class PolicyRequest:
    request_id: str
    principal: AgentName
    action: str
    resource_type: str
    resource_id: str
    context: dict[str, Any]


@dataclass(frozen=True, slots=True)
class PolicySignal:
    family: str
    policy_id: str
    outcome: DecisionOutcome
    reason_code: str
    because: str
    guidance: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class Decision:
    decision_id: str
    request_id: str
    trace_id: str
    proposal_id: str
    agent: AgentName
    tool_name: str
    effect_class: EffectClass | None
    policy_outcome: DecisionOutcome
    applied_outcome: DecisionOutcome
    enforced: bool
    reason_code: str
    because: str
    reasons: tuple[PolicySignal, ...]
    guidance: dict[str, Any] | None
    policy_version: str
    engine_name: str
    evaluation_ms: float
    policy_bundle_hash: str | None = None
    created_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class GovernedToolResult:
    decision: Decision
    value: Any | None = None
    guidance: dict[str, Any] | None = None
    pending_approval: "PendingApproval | None" = None


@dataclass(slots=True)
class PreparedAction:
    prepared_action_id: str
    trace_id: str
    tool_name: str
    resource_id: str
    amount_minor: int
    currency: str
    prepared_by: AgentName
    arguments: dict[str, Any]
    action_hash: str
    state_hash: str
    mandate_id: str
    policy_version: str
    spend_committed_at_prepare_minor: int
    spend_reserved_before_minor: int
    spend_reserved_after_minor: int
    status: CommitmentStatus
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ApprovalRecord:
    approval_id: str
    trace_id: str
    prepared_action_id: str
    action_hash: str
    state_hash: str
    policy_version: str
    reason_code: str
    status: ApprovalStatus
    created_at: datetime
    expires_at: datetime
    version: int = 1
    decided_at: datetime | None = None
    decision: ApprovalDecision | None = None
    approver_label: str | None = None
    comment: str | None = None
    decision_idempotency_key: str | None = None


# Compatibility name retained for Checkpoint 2 callers.
PendingApproval = ApprovalRecord


@dataclass(frozen=True, slots=True)
class EffectRecord:
    tool_name: str
    effect_class: EffectClass
    resource_id: str
    actor: str


@dataclass(frozen=True, slots=True)
class TraceEvent:
    event_id: str
    trace_id: str
    sequence: int
    event_type: EventType
    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    agent: AgentName | None = None
    tool_name: str | None = None
    effect_class: EffectClass | None = None
    occurred_at: datetime = field(default_factory=utc_now)
    schema_version: str = "ledger-event-v1"
    previous_hash: str = ""
    event_hash: str = ""
    idempotency_key: str | None = None


@dataclass(frozen=True, slots=True)
class LedgerHead:
    trace_id: str
    sequence: int
    event_count: int
    event_hash: str
    schema_version: str
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class VerificationResult:
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
    verified_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class TamperResult:
    trace_id: str
    sequence: int
    field: str
    status: str = "tampered_for_demo"


@dataclass(frozen=True, slots=True)
class RiskSignalPoint:
    sequence: int
    decision_id: str
    family: str
    reason_code: str
    outcome: DecisionOutcome
    delta: int
    total: int


@dataclass(frozen=True, slots=True)
class SpendPoint:
    sequence: int
    label: str
    committed_minor: int
    reserved_minor: int
    projected_minor: int
    ceiling_minor: int


@dataclass(frozen=True, slots=True)
class WeightAttempt:
    sequence: int
    proposal_id: str
    attempted_value: int
    unit: str
    fact_id: str
    policy_outcome: DecisionOutcome
    reason_code: str


@dataclass(frozen=True, slots=True)
class WeightProvenanceProjection:
    fact_id: str
    authoritative_value: int
    unit: str
    source_id: str
    source_hash: str
    attempts: tuple[WeightAttempt, ...]
    final_value: int | None


@dataclass(frozen=True, slots=True)
class DashboardProjection:
    trace_id: str
    risk_signal_score: int
    risk_signal_method: str
    risk_points: tuple[RiskSignalPoint, ...]
    spend_points: tuple[SpendPoint, ...]
    weight_provenance: WeightProvenanceProjection | None


@dataclass(slots=True)
class TrajectoryState:
    trace_id: str
    order_id: str
    status: RunStatus = RunStatus.PENDING
    current_agent: AgentName | None = None
    mode: GovernanceMode = GovernanceMode.SHADOW
    scenario: ScenarioName = ScenarioName.BENIGN
    scenario_config: ScenarioConfig | None = None
    mandate: ShipmentMandate | None = None
    policy_version: str = "demo-v1"
    workflow_stage: WorkflowStage = WorkflowStage.STARTED
    order: Order | None = None
    inventory_fact: InventoryFact | None = None
    facts: dict[str, NumericFact] = field(default_factory=dict)
    selected_vehicle: Vehicle | None = None
    selected_quote: CarrierQuote | None = None
    dispatch_plan_id: str | None = None
    carrier_selection_id: str | None = None
    prepared_actions: dict[str, PreparedAction] = field(default_factory=dict)
    confirmed_booking_id: str | None = None
    pending_approval_id: str | None = None
    spend_committed_minor: int = 0
    spend_reserved_minor: int = 0
    decisions: list[Decision] = field(default_factory=list)
    guide_attempts: dict[str, int] = field(default_factory=dict)
    effect_history: list[EffectRecord] = field(default_factory=list)
    quoted_by: str | None = None
    prepared_by: AgentName | None = None
    approved_by: str | None = None
    notification_id: str | None = None
    events: list[TraceEvent] = field(default_factory=list)
    next_sequence: int = 1
    tool_call_count: int = 0
    error: str | None = None
    terminal_reason: str | None = None
    storage_revision: int = 0


@dataclass(frozen=True, slots=True)
class RunSummary:
    trace_id: str
    order_id: str
    status: RunStatus
    current_agent: AgentName | None
    mode: GovernanceMode
    scenario: ScenarioName
    policy_version: str
    policy_engine: str
    workflow_stage: WorkflowStage
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

    @classmethod
    def from_state(cls, state: TrajectoryState, policy_engine: str = "unknown") -> "RunSummary":
        ceiling = state.mandate.spend_ceiling_minor if state.mandate else None
        return cls(
            trace_id=state.trace_id,
            order_id=state.order_id,
            status=state.status,
            current_agent=state.current_agent,
            mode=state.mode,
            scenario=state.scenario,
            policy_version=state.policy_version,
            policy_engine=policy_engine,
            workflow_stage=state.workflow_stage,
            selected_vehicle_id=state.selected_vehicle.vehicle_id if state.selected_vehicle else None,
            selected_carrier_id=state.selected_quote.carrier_id if state.selected_quote else None,
            selected_amount_minor=state.selected_quote.amount_minor if state.selected_quote else None,
            notification_id=state.notification_id,
            confirmed_booking_id=state.confirmed_booking_id,
            spend_committed_minor=state.spend_committed_minor,
            spend_reserved_minor=state.spend_reserved_minor,
            projected_spend_minor=state.spend_committed_minor + state.spend_reserved_minor,
            spend_ceiling_minor=ceiling,
            pending_approval_id=state.pending_approval_id,
            decision_count=len(state.decisions),
            event_count=len(state.events),
            error=state.error,
            terminal_reason=state.terminal_reason,
        )


@dataclass(frozen=True, slots=True)
class ApprovalResolution:
    approval: ApprovalRecord
    run: RunSummary
    idempotent_replay: bool = False


@dataclass(frozen=True, slots=True)
class OrderSummary:
    order_id: str
    cargo_class: str
    shipment_weight_kg: int
    currency: str
    scenarios: tuple[ScenarioName, ...] = (ScenarioName.BENIGN, ScenarioName.ADVERSARIAL)


@dataclass(frozen=True, slots=True)
class ResetResult:
    status: str
    removed_run_count: int
