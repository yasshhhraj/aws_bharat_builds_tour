"""Carrier role: choose a compliant deterministic quote."""

from packages.domain.enums import AgentName
from packages.domain.errors import NoSuitableCarrierError
from packages.domain.models import CarrierQuote, TrajectoryState
from packages.governor import ObserverGovernor

from .base import BaseAgent


class CarrierAgent(BaseAgent):
    name = AgentName.CARRIER

    def run(self, state: TrajectoryState, governor: ObserverGovernor) -> str:
        if state.order is None or state.dispatch_plan_id is None:
            raise NoSuitableCarrierError("Carrier selection requires a dispatch plan.")
        quotes = governor.execute_tool(
            state,
            self.name,
            "list_carrier_quotes",
            order_id=state.order_id,
            destination_zone=state.order.destination_zone,
        )
        requires_cold_chain = state.order.cargo_class == "perishable"
        candidates = [
            quote
            for quote in quotes
            if isinstance(quote, CarrierQuote)
            and quote.lane_supported
            and (not requires_cold_chain or quote.cold_chain_certified)
        ]
        if not candidates:
            raise NoSuitableCarrierError(
                f"No suitable carrier quote exists for {state.order_id}."
            )
        selected = min(candidates, key=lambda quote: (quote.amount_minor, quote.quote_id))
        selection = governor.execute_tool(
            state,
            self.name,
            "select_carrier_quote",
            order_id=state.order_id,
            quote_id=selected.quote_id,
            idempotency_key=f"{state.trace_id}:carrier-selection",
        )
        state.selected_quote = selected
        state.carrier_selection_id = str(selection["selection_id"])
        amount = selected.amount_minor / 100
        return (
            f"Carrier Agent selected certified carrier {selected.carrier_id} "
            f"for INR {amount:,.0f}."
        )
