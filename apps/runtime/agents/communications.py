"""Customer communications role: write a synthetic outbox record."""

from packages.domain.enums import AgentName
from packages.domain.errors import ManifestError
from packages.domain.models import TrajectoryState
from packages.governor import ObserverGovernor

from .base import BaseAgent


class CustomerCommunicationsAgent(BaseAgent):
    name = AgentName.CUSTOMER_COMMUNICATIONS

    def run(self, state: TrajectoryState, governor: ObserverGovernor) -> str:
        if state.selected_quote is None:
            raise ManifestError("A carrier must be selected before notification.")
        message = (
            f"Synthetic tracking update for {state.order_id}: "
            f"assigned to {state.selected_quote.carrier_id}."
        )
        notification = governor.execute_tool(
            state,
            self.name,
            "write_tracking_outbox",
            order_id=state.order_id,
            message=message,
            idempotency_key=f"{state.trace_id}:tracking-outbox",
        )
        state.notification_id = str(notification["notification_id"])
        return "Customer Communications Agent wrote a simulated tracking message."
