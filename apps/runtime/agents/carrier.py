"""Carrier role with cold-chain guide-back and two-phase commitment."""

from packages.commitments import build_prepared_action
from packages.domain.enums import (
    AgentName,
    ApprovalStatus,
    CommitmentStatus,
    DecisionOutcome,
    WorkflowStage,
)
from packages.domain.errors import ApprovalStateMismatchError, NoSuitableCarrierError, PolicyBlockedError
from packages.domain.models import ApprovalRecord, CarrierQuote, TrajectoryState
from packages.governor import ManifestGovernor

from .base import BaseAgent


class CarrierAgent(BaseAgent):
    name = AgentName.CARRIER

    def run(self, state: TrajectoryState, governor: ManifestGovernor) -> str:
        if state.order is None or state.dispatch_plan_id is None or state.scenario_config is None:
            raise NoSuitableCarrierError("Carrier selection requires a dispatch plan and scenario.")
        listed = governor.execute_tool(
            state, self.name, "list_carrier_quotes",
            order_id=state.order_id,
            destination_zone=state.order.destination_zone,
        )
        if listed.value is None:
            raise PolicyBlockedError(listed.decision.because)
        quotes = [item for item in listed.value if isinstance(item, CarrierQuote)]
        selected = self._find_quote(quotes, state.scenario_config.preferred_quote_id)
        result = self._select(state, governor, selected, 1)
        if result.decision.applied_outcome == DecisionOutcome.GUIDE:
            candidates = [quote for quote in quotes if quote.cold_chain_certified and quote.lane_supported]
            if not candidates:
                raise NoSuitableCarrierError(f"No suitable carrier quote exists for {state.order_id}.")
            selected = min(candidates, key=lambda quote: (quote.amount_minor, quote.quote_id))
            result = self._select(state, governor, selected, 2)
        if result.value is None:
            raise PolicyBlockedError(result.decision.because)
        state.selected_quote = selected
        state.carrier_selection_id = str(result.value["selection_id"])
        state.quoted_by = selected.quote_issuer

        prepared_result = governor.execute_tool(
            state, self.name, "prepare_freight_booking",
            order_id=state.order_id,
            quote_id=selected.quote_id,
            amount_minor=selected.amount_minor,
            currency=selected.currency,
            idempotency_key=f"{state.trace_id}:prepare:{selected.quote_id}",
        )
        if prepared_result.decision.applied_outcome == DecisionOutcome.GUIDE:
            raise PolicyBlockedError("Selected carrier remained invalid during preparation.")
        if prepared_result.value is None:
            raise PolicyBlockedError(prepared_result.decision.because)
        prepared = build_prepared_action(
            state,
            prepared_action_id=str(prepared_result.value["prepared_action_id"]),
            quote_id=selected.quote_id,
            amount_minor=selected.amount_minor,
            currency=selected.currency,
            prepared_by=self.name,
        )
        state.prepared_actions[prepared.prepared_action_id] = prepared
        state.prepared_by = self.name
        state.spend_reserved_minor += selected.amount_minor
        state.workflow_stage = WorkflowStage.BOOKING_PREPARED

        confirmed = governor.execute_tool(
            state, self.name, "confirm_freight_booking",
            prepared_action_id=prepared.prepared_action_id,
            action_hash=prepared.action_hash,
            idempotency_key=f"{state.trace_id}:confirm:{prepared.prepared_action_id}",
        )
        if confirmed.pending_approval is not None:
            return f"Carrier Agent prepared {selected.carrier_id}; approval is required."
        if confirmed.value is None:
            raise PolicyBlockedError(confirmed.decision.because)
        amount = selected.amount_minor / 100
        return f"Carrier Agent confirmed {selected.carrier_id} for INR {amount:,.0f}."

    def resume_booking(
        self,
        state: TrajectoryState,
        governor: ManifestGovernor,
        approval: ApprovalRecord,
    ) -> str:
        if approval.status != ApprovalStatus.APPROVED:
            raise ApprovalStateMismatchError("Only an approved record can resume a booking.")
        prepared = state.prepared_actions.get(approval.prepared_action_id)
        if prepared is None or prepared.status != CommitmentStatus.APPROVED:
            raise ApprovalStateMismatchError("The prepared action is not approved for confirmation.")
        result = governor.execute_tool(
            state,
            self.name,
            "confirm_freight_booking",
            prepared_action_id=prepared.prepared_action_id,
            action_hash=prepared.action_hash,
            idempotency_key=f"{state.trace_id}:confirm:{prepared.prepared_action_id}",
        )
        if result.value is None:
            raise PolicyBlockedError(result.decision.because)
        return f"Carrier Agent confirmed approved booking {result.value['confirmation_id']}."

    def cancel_booking(
        self,
        state: TrajectoryState,
        governor: ManifestGovernor,
        approval: ApprovalRecord,
        reason_code: str,
    ) -> str:
        prepared = state.prepared_actions.get(approval.prepared_action_id)
        if prepared is None:
            raise ApprovalStateMismatchError("The prepared action to cancel was not found.")
        if approval.status == ApprovalStatus.REJECTED:
            prepared.status = CommitmentStatus.REJECTED
        elif approval.status == ApprovalStatus.EXPIRED:
            prepared.status = CommitmentStatus.EXPIRED
        else:
            raise ApprovalStateMismatchError("Only rejected or expired actions can be cancelled.")
        result = governor.execute_tool(
            state,
            self.name,
            "cancel_freight_booking",
            prepared_action_id=prepared.prepared_action_id,
            action_hash=prepared.action_hash,
            cancellation_reason_code=reason_code,
            idempotency_key=f"{state.trace_id}:cancel:{prepared.prepared_action_id}",
        )
        if result.value is None:
            raise PolicyBlockedError(result.decision.because)
        return f"Carrier Agent cancelled prepared booking {prepared.prepared_action_id}."

    def _select(self, state, governor, quote, attempt):
        return governor.execute_tool(
            state, self.name, "select_carrier_quote",
            order_id=state.order_id,
            quote_id=quote.quote_id,
            idempotency_key=f"{state.trace_id}:carrier-selection:{attempt}",
        )

    @staticmethod
    def _find_quote(quotes: list[CarrierQuote], quote_id: str) -> CarrierQuote:
        for quote in quotes:
            if quote.quote_id == quote_id:
                return quote
        raise NoSuitableCarrierError(f"Preferred quote {quote_id} is unavailable.")
