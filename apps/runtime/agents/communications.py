"""Customer communications role: write a synthetic outbox record."""

from packages.domain.enums import AgentName
from packages.domain.errors import ManifestError
from packages.domain.models import TrajectoryState
from packages.governor import ManifestGovernor

from apps.runtime.tool_result_projector import ToolResultProjector

from .base import BaseAgent


class CustomerCommunicationsAgent(BaseAgent):
    name = AgentName.CUSTOMER_COMMUNICATIONS

    def run(self, state: TrajectoryState, governor: ManifestGovernor) -> str:
        if state.selected_quote is None or state.confirmed_booking_id is None:
            raise ManifestError("A confirmed carrier booking is required before notification.")
        result = governor.execute_tool(
            state,
            self.name,
            "write_tracking_outbox",
            order_id=state.order_id,
            recipient_ref=f"DEMO-RECIPIENT-{state.order_id.removeprefix('ORD-')}",
            template_id="TRACKING_UPDATE_V1",
            template_variables={
                "order_id": state.order_id,
                "carrier_id": state.selected_quote.carrier_id,
            },
            idempotency_key=f"{state.trace_id}:tracking-outbox",
        )
        if result.value is None:
            raise ManifestError(result.decision.because)
        ToolResultProjector(governor.loader).project(
            state,
            self.name,
            "write_tracking_outbox",
            {"order_id": state.order_id},
            result.value,
        )
        return "Customer Communications Agent wrote a simulated tracking message."
