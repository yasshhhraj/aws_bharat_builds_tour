"""Creation and hashing of reversible synthetic commitments."""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from typing import Any

from packages.domain.enums import AgentName, CommitmentStatus
from packages.domain.models import PreparedAction, TrajectoryState, utc_now


def canonical_hash(value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def prepared_action_hash(prepared: PreparedAction) -> str:
    return canonical_hash(prepared.arguments)


def prepared_state_hash(state: TrajectoryState, prepared: PreparedAction) -> str:
    return canonical_hash(
        {
            "trace_id": state.trace_id,
            "order_id": state.order_id,
            "mandate_id": prepared.mandate_id,
            "policy_version": prepared.policy_version,
            "prepared_action_id": prepared.prepared_action_id,
            "quote_id": prepared.resource_id,
            "amount_minor": prepared.amount_minor,
            "currency": prepared.currency,
            "committed_minor": prepared.spend_committed_at_prepare_minor,
            "reserved_before_minor": prepared.spend_reserved_before_minor,
            "reserved_after_minor": prepared.spend_reserved_after_minor,
            "selected_quote_id": prepared.resource_id,
        }
    )


def build_prepared_action(
    state: TrajectoryState,
    *,
    prepared_action_id: str,
    quote_id: str,
    amount_minor: int,
    currency: str,
    prepared_by: AgentName,
) -> PreparedAction:
    if state.mandate is None:
        raise ValueError("A shipment mandate is required to prepare a commitment.")
    reserved_before = state.spend_reserved_minor
    reserved_after = reserved_before + amount_minor
    arguments = {
        "prepared_action_id": prepared_action_id,
        "quote_id": quote_id,
        "amount_minor": amount_minor,
        "currency": currency,
    }
    action_hash = canonical_hash(arguments)
    prepared = PreparedAction(
        prepared_action_id=prepared_action_id,
        trace_id=state.trace_id,
        tool_name="confirm_freight_booking",
        resource_id=quote_id,
        amount_minor=amount_minor,
        currency=currency,
        prepared_by=prepared_by,
        arguments=arguments,
        action_hash=action_hash,
        state_hash="",
        mandate_id=state.mandate.mandate_id,
        policy_version=state.policy_version,
        spend_committed_at_prepare_minor=state.spend_committed_minor,
        spend_reserved_before_minor=reserved_before,
        spend_reserved_after_minor=reserved_after,
        status=CommitmentStatus.PREPARED,
        expires_at=utc_now() + timedelta(minutes=15),
    )
    prepared.state_hash = prepared_state_hash(state, prepared)
    return prepared
