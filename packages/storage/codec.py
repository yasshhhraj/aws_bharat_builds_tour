"""Explicit, versioned JSON codecs for durable Manifest records."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
import json
from typing import Any, Callable, TypeVar

from packages.domain.enums import (
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
from packages.domain.errors import (
    ItemSizeLimitError,
    SerializationVersionError,
    TracePersistenceError,
)
from packages.domain.models import (
    ApprovalRecord,
    CarrierQuote,
    Decision,
    EffectRecord,
    InventoryFact,
    LedgerHead,
    NumericFact,
    Order,
    PolicySignal,
    PreparedAction,
    ScenarioConfig,
    ShipmentMandate,
    TraceEvent,
    TrajectoryState,
    Vehicle,
)
from packages.ledger.canonical import canonical_json

from .models import (
    MAX_PERSISTED_ITEM_BYTES,
    STATE_SCHEMA_VERSION,
    STORAGE_SCHEMA_VERSION,
    EffectReceipt,
    ReplayKind,
    ReplayRecord,
)


EVENT_RECORD_SCHEMA_VERSION = "trace-event-record-v1"
DECISION_RECORD_SCHEMA_VERSION = "decision-record-v1"
APPROVAL_RECORD_SCHEMA_VERSION = "approval-record-v1"
HEAD_RECORD_SCHEMA_VERSION = "ledger-head-record-v1"
REPLAY_RECORD_SCHEMA_VERSION = "replay-record-v1"
EFFECT_RECORD_SCHEMA_VERSION = "effect-receipt-v1"

T = TypeVar("T")


def _normalize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise TracePersistenceError("Persisted datetimes must include a timezone.")
        return (
            value.astimezone(timezone.utc)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
    if is_dataclass(value):
        return _normalize(asdict(value))
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted((_normalize(item) for item in value), key=str)
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TracePersistenceError(
        f"Unsupported persisted value type: {type(value).__name__}."
    )


def _encode(schema_version: str, payload: Any, label: str) -> str:
    document = canonical_json(
        {
            "storage_schema_version": STORAGE_SCHEMA_VERSION,
            "record_schema_version": schema_version,
            "payload": _normalize(payload),
        }
    )
    assert_item_size(document, label)
    return document


def _decode(document: str, expected_schema: str, label: str) -> dict[str, Any]:
    try:
        envelope = json.loads(document)
    except (TypeError, json.JSONDecodeError) as exc:
        raise TracePersistenceError(f"Stored {label} is not valid JSON.") from exc
    if not isinstance(envelope, dict):
        raise TracePersistenceError(f"Stored {label} must be a JSON object.")
    if envelope.get("storage_schema_version") != STORAGE_SCHEMA_VERSION:
        raise SerializationVersionError(
            f"Stored {label} uses an unsupported storage schema version."
        )
    if envelope.get("record_schema_version") != expected_schema:
        raise SerializationVersionError(
            f"Stored {label} uses an unsupported record schema version."
        )
    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        raise TracePersistenceError(f"Stored {label} payload must be an object.")
    return payload


def _construct(label: str, builder: Callable[[], T]) -> T:
    try:
        return builder()
    except (KeyError, TypeError, ValueError) as exc:
        raise TracePersistenceError(f"Stored {label} payload is invalid.") from exc


def _datetime(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Datetime must be a string.")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Datetime must include a timezone.")
    return parsed.astimezone(timezone.utc)


def assert_item_size(
    document: str,
    label: str,
    *,
    maximum_bytes: int = MAX_PERSISTED_ITEM_BYTES,
) -> None:
    size = len(document.encode("utf-8"))
    if size > maximum_bytes:
        raise ItemSizeLimitError(
            f"Serialized {label} is {size} bytes; maximum is {maximum_bytes}."
        )


def encode_state_json(state: TrajectoryState) -> str:
    payload = _normalize(state)
    payload.pop("events", None)
    payload.pop("decisions", None)
    return _encode(STATE_SCHEMA_VERSION, payload, "trace state")


def decode_state_json(
    document: str,
    *,
    events: tuple[TraceEvent, ...] = (),
    decisions: tuple[Decision, ...] = (),
) -> TrajectoryState:
    payload = _decode(document, STATE_SCHEMA_VERSION, "trace state")

    def build() -> TrajectoryState:
        mandate_data = payload.get("mandate")
        mandate = None
        if mandate_data is not None:
            mandate = ShipmentMandate(
                mandate_id=mandate_data["mandate_id"],
                order_id=mandate_data["order_id"],
                mode=GovernanceMode(mandate_data["mode"]),
                currency=mandate_data["currency"],
                spend_ceiling_minor=mandate_data["spend_ceiling_minor"],
                approval_threshold_minor=mandate_data["approval_threshold_minor"],
                cargo_class=mandate_data["cargo_class"],
                allowed_effect_classes=frozenset(
                    EffectClass(value)
                    for value in mandate_data["allowed_effect_classes"]
                ),
                policy_version=mandate_data["policy_version"],
            )
        scenario_data = payload.get("scenario_config")
        scenario_config = (
            ScenarioConfig(
                name=ScenarioName(scenario_data["name"]),
                prior_committed_minor=scenario_data["prior_committed_minor"],
                attempted_weight_kg=scenario_data["attempted_weight_kg"],
                preferred_vehicle_id=scenario_data["preferred_vehicle_id"],
                preferred_quote_id=scenario_data["preferred_quote_id"],
            )
            if scenario_data is not None
            else None
        )
        order = Order(**payload["order"]) if payload.get("order") else None
        inventory = (
            InventoryFact(**payload["inventory_fact"])
            if payload.get("inventory_fact")
            else None
        )
        facts = {
            fact_id: NumericFact(**record)
            for fact_id, record in payload.get("facts", {}).items()
        }
        selected_vehicle = (
            Vehicle(**payload["selected_vehicle"])
            if payload.get("selected_vehicle")
            else None
        )
        selected_quote = (
            CarrierQuote(**payload["selected_quote"])
            if payload.get("selected_quote")
            else None
        )
        prepared_actions = {
            prepared_id: _prepared_action(record)
            for prepared_id, record in payload.get("prepared_actions", {}).items()
        }
        effect_history = [
            EffectRecord(
                tool_name=record["tool_name"],
                effect_class=EffectClass(record["effect_class"]),
                resource_id=record["resource_id"],
                actor=record["actor"],
            )
            for record in payload.get("effect_history", [])
        ]
        current_agent = payload.get("current_agent")
        prepared_by = payload.get("prepared_by")
        return TrajectoryState(
            trace_id=payload["trace_id"],
            order_id=payload["order_id"],
            status=RunStatus(payload["status"]),
            current_agent=AgentName(current_agent) if current_agent else None,
            mode=GovernanceMode(payload["mode"]),
            scenario=ScenarioName(payload["scenario"]),
            scenario_config=scenario_config,
            mandate=mandate,
            policy_version=payload["policy_version"],
            workflow_stage=WorkflowStage(payload["workflow_stage"]),
            order=order,
            inventory_fact=inventory,
            facts=facts,
            selected_vehicle=selected_vehicle,
            selected_quote=selected_quote,
            dispatch_plan_id=payload.get("dispatch_plan_id"),
            carrier_selection_id=payload.get("carrier_selection_id"),
            prepared_actions=prepared_actions,
            confirmed_booking_id=payload.get("confirmed_booking_id"),
            pending_approval_id=payload.get("pending_approval_id"),
            spend_committed_minor=payload["spend_committed_minor"],
            spend_reserved_minor=payload["spend_reserved_minor"],
            decisions=list(decisions),
            guide_attempts=dict(payload.get("guide_attempts", {})),
            effect_history=effect_history,
            quoted_by=payload.get("quoted_by"),
            prepared_by=AgentName(prepared_by) if prepared_by else None,
            approved_by=payload.get("approved_by"),
            notification_id=payload.get("notification_id"),
            events=list(events),
            next_sequence=payload["next_sequence"],
            tool_call_count=payload["tool_call_count"],
            error=payload.get("error"),
            terminal_reason=payload.get("terminal_reason"),
            storage_revision=payload.get("storage_revision", 0),
        )

    return _construct("trace state", build)


def _prepared_action(payload: dict[str, Any]) -> PreparedAction:
    return PreparedAction(
        prepared_action_id=payload["prepared_action_id"],
        trace_id=payload["trace_id"],
        tool_name=payload["tool_name"],
        resource_id=payload["resource_id"],
        amount_minor=payload["amount_minor"],
        currency=payload["currency"],
        prepared_by=AgentName(payload["prepared_by"]),
        arguments=dict(payload["arguments"]),
        action_hash=payload["action_hash"],
        state_hash=payload["state_hash"],
        mandate_id=payload["mandate_id"],
        policy_version=payload["policy_version"],
        spend_committed_at_prepare_minor=payload[
            "spend_committed_at_prepare_minor"
        ],
        spend_reserved_before_minor=payload["spend_reserved_before_minor"],
        spend_reserved_after_minor=payload["spend_reserved_after_minor"],
        status=CommitmentStatus(payload["status"]),
        expires_at=_datetime(payload["expires_at"]),
    )


def encode_event_json(event: TraceEvent) -> str:
    return _encode(EVENT_RECORD_SCHEMA_VERSION, event, "trace event")


def decode_event_json(document: str) -> TraceEvent:
    payload = _decode(document, EVENT_RECORD_SCHEMA_VERSION, "trace event")
    return _construct(
        "trace event",
        lambda: TraceEvent(
            event_id=payload["event_id"],
            trace_id=payload["trace_id"],
            sequence=payload["sequence"],
            event_type=EventType(payload["event_type"]),
            summary=payload["summary"],
            details=dict(payload.get("details", {})),
            agent=AgentName(payload["agent"]) if payload.get("agent") else None,
            tool_name=payload.get("tool_name"),
            effect_class=(
                EffectClass(payload["effect_class"])
                if payload.get("effect_class")
                else None
            ),
            occurred_at=_datetime(payload["occurred_at"]),
            schema_version=payload["schema_version"],
            previous_hash=payload["previous_hash"],
            event_hash=payload["event_hash"],
            idempotency_key=payload.get("idempotency_key"),
        ),
    )


def encode_decision_json(decision: Decision) -> str:
    return _encode(DECISION_RECORD_SCHEMA_VERSION, decision, "decision")


def decode_decision_json(document: str) -> Decision:
    payload = _decode(document, DECISION_RECORD_SCHEMA_VERSION, "decision")

    def build() -> Decision:
        reasons = tuple(
            PolicySignal(
                family=record["family"],
                policy_id=record["policy_id"],
                outcome=DecisionOutcome(record["outcome"]),
                reason_code=record["reason_code"],
                because=record["because"],
                guidance=record.get("guidance"),
            )
            for record in payload["reasons"]
        )
        return Decision(
            decision_id=payload["decision_id"],
            request_id=payload["request_id"],
            trace_id=payload["trace_id"],
            proposal_id=payload["proposal_id"],
            agent=AgentName(payload["agent"]),
            tool_name=payload["tool_name"],
            effect_class=(
                EffectClass(payload["effect_class"])
                if payload.get("effect_class")
                else None
            ),
            policy_outcome=DecisionOutcome(payload["policy_outcome"]),
            applied_outcome=DecisionOutcome(payload["applied_outcome"]),
            enforced=payload["enforced"],
            reason_code=payload["reason_code"],
            because=payload["because"],
            reasons=reasons,
            guidance=payload.get("guidance"),
            policy_version=payload["policy_version"],
            engine_name=payload["engine_name"],
            evaluation_ms=payload["evaluation_ms"],
            policy_bundle_hash=payload.get("policy_bundle_hash"),
            created_at=_datetime(payload["created_at"]),
        )

    return _construct("decision", build)


def encode_approval_json(approval: ApprovalRecord) -> str:
    return _encode(APPROVAL_RECORD_SCHEMA_VERSION, approval, "approval")


def decode_approval_json(document: str) -> ApprovalRecord:
    payload = _decode(document, APPROVAL_RECORD_SCHEMA_VERSION, "approval")
    return _construct(
        "approval",
        lambda: ApprovalRecord(
            approval_id=payload["approval_id"],
            trace_id=payload["trace_id"],
            prepared_action_id=payload["prepared_action_id"],
            action_hash=payload["action_hash"],
            state_hash=payload["state_hash"],
            policy_version=payload["policy_version"],
            reason_code=payload["reason_code"],
            status=ApprovalStatus(payload["status"]),
            created_at=_datetime(payload["created_at"]),
            expires_at=_datetime(payload["expires_at"]),
            version=payload["version"],
            decided_at=(
                _datetime(payload["decided_at"])
                if payload.get("decided_at")
                else None
            ),
            decision=(
                ApprovalDecision(payload["decision"])
                if payload.get("decision")
                else None
            ),
            approver_label=payload.get("approver_label"),
            comment=payload.get("comment"),
            decision_idempotency_key=payload.get("decision_idempotency_key"),
        ),
    )


def encode_head_json(head: LedgerHead) -> str:
    return _encode(HEAD_RECORD_SCHEMA_VERSION, head, "ledger head")


def decode_head_json(document: str) -> LedgerHead:
    payload = _decode(document, HEAD_RECORD_SCHEMA_VERSION, "ledger head")
    return _construct(
        "ledger head",
        lambda: LedgerHead(
            trace_id=payload["trace_id"],
            sequence=payload["sequence"],
            event_count=payload["event_count"],
            event_hash=payload["event_hash"],
            schema_version=payload["schema_version"],
            updated_at=_datetime(payload["updated_at"]),
        ),
    )


def encode_replay_json(record: ReplayRecord) -> str:
    return _encode(REPLAY_RECORD_SCHEMA_VERSION, record, "replay record")


def decode_replay_json(document: str) -> ReplayRecord:
    payload = _decode(document, REPLAY_RECORD_SCHEMA_VERSION, "replay record")
    return _construct(
        "replay record",
        lambda: ReplayRecord(
            trace_id=payload["trace_id"],
            kind=ReplayKind(payload["kind"]),
            key_hash=payload["key_hash"],
            fingerprint=payload["fingerprint"],
            result_reference=payload["result_reference"],
            created_at=_datetime(payload["created_at"]),
        ),
    )


def encode_effect_json(receipt: EffectReceipt) -> str:
    return _encode(EFFECT_RECORD_SCHEMA_VERSION, receipt, "effect receipt")


def decode_effect_json(document: str) -> EffectReceipt:
    payload = _decode(document, EFFECT_RECORD_SCHEMA_VERSION, "effect receipt")
    return _construct(
        "effect receipt",
        lambda: EffectReceipt(
            trace_id=payload["trace_id"],
            tool_name=payload["tool_name"],
            key_hash=payload["key_hash"],
            fingerprint=payload["fingerprint"],
            result=dict(payload["result"]),
            created_at=_datetime(payload["created_at"]),
        ),
    )
