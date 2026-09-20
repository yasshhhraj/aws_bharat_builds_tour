"""Narrow Strands tools that always cross the Manifest governor boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from strands import tool

from packages.domain.enums import AgentName, CommitmentStatus, DecisionOutcome
from packages.domain.errors import AgentIncompleteError, AgentRuntimeError
from packages.domain.models import ApprovalRecord, TrajectoryState, to_primitive
from packages.governor import ManifestGovernor

from .agent_runtime import RolePhase
from .tool_result_projector import ToolResultProjector


ROLE_TOOLS: dict[AgentName, tuple[str, ...]] = {
    AgentName.INVENTORY: ("get_order", "check_inventory"),
    AgentName.DISPATCH: ("list_available_vehicles", "create_dispatch_plan"),
    AgentName.CARRIER: (
        "list_carrier_quotes",
        "select_carrier_quote",
        "prepare_freight_booking",
        "confirm_freight_booking",
        "cancel_freight_booking",
    ),
    AgentName.CUSTOMER_COMMUNICATIONS: ("write_tracking_outbox",),
}


TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "get_order": {"type": "object", "properties": {}, "additionalProperties": False},
    "check_inventory": {"type": "object", "properties": {}, "additionalProperties": False},
    "list_available_vehicles": {"type": "object", "properties": {}, "additionalProperties": False},
    "create_dispatch_plan": {
        "type": "object",
        "properties": {
            "vehicle_id": {"type": "string"},
            "weight_value": {"type": "integer", "minimum": 0},
            "weight_unit": {"type": "string", "enum": ["kg"]},
            "weight_fact_id": {"type": "string"},
        },
        "required": ["vehicle_id", "weight_value", "weight_unit", "weight_fact_id"],
        "additionalProperties": False,
    },
    "list_carrier_quotes": {"type": "object", "properties": {}, "additionalProperties": False},
    "select_carrier_quote": {
        "type": "object",
        "properties": {"quote_id": {"type": "string"}},
        "required": ["quote_id"],
        "additionalProperties": False,
    },
    "prepare_freight_booking": {
        "type": "object",
        "properties": {
            "quote_id": {"type": "string"},
            "amount_minor": {"type": "integer", "minimum": 0},
            "currency": {"type": "string"},
        },
        "required": ["quote_id", "amount_minor", "currency"],
        "additionalProperties": False,
    },
    "confirm_freight_booking": {
        "type": "object",
        "properties": {"prepared_action_id": {"type": "string"}},
        "required": ["prepared_action_id"],
        "additionalProperties": False,
    },
    "cancel_freight_booking": {
        "type": "object",
        "properties": {"prepared_action_id": {"type": "string"}},
        "required": ["prepared_action_id"],
        "additionalProperties": False,
    },
    "write_tracking_outbox": {"type": "object", "properties": {}, "additionalProperties": False},
}


@dataclass(slots=True)
class GovernedInvocationContext:
    role: AgentName
    phase: RolePhase
    state: TrajectoryState
    governor: ManifestGovernor
    approval: ApprovalRecord | None = None
    cancellation_reason_code: str | None = None
    history: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    terminal: bool = False
    closed: bool = False
    blocked_reason: str | None = None
    projector: ToolResultProjector = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.projector = ToolResultProjector(self.governor.loader)

    @property
    def allowed_tools(self) -> tuple[str, ...]:
        if self.role != AgentName.CARRIER:
            return ROLE_TOOLS[self.role]
        if self.phase == RolePhase.RESUME_APPROVED:
            return ("confirm_freight_booking",)
        if self.phase == RolePhase.CANCEL:
            return ("cancel_freight_booking",)
        return ROLE_TOOLS[self.role][:-1]

    def execute(self, tool_name: str, model_arguments: dict[str, Any]) -> dict[str, Any]:
        if self.closed:
            raise AgentRuntimeError("The role invocation is closed.")
        if self.terminal:
            raise AgentRuntimeError("The role invocation is already terminal.")
        if tool_name not in self.allowed_tools:
            self.terminal = True
            self.blocked_reason = f"Tool {tool_name} is not available to {self.role.value}."
            raise AgentRuntimeError(self.blocked_reason)
        arguments = self._bind_arguments(tool_name, model_arguments)
        result = self.governor.execute_tool(
            self.state, self.role, tool_name, **arguments
        )
        if result.value is not None:
            self.projector.project(
                self.state, self.role, tool_name, arguments, result.value
            )
        payload = {
            "tool": tool_name,
            "outcome": result.decision.applied_outcome.value,
            "reason_code": result.decision.reason_code,
            "because": result.decision.because,
            "value": self._safe_value(tool_name, result.value),
            "guidance": to_primitive(result.guidance),
            "pending_approval": to_primitive(result.pending_approval),
        }
        self.history.append((tool_name, payload))
        if result.decision.applied_outcome == DecisionOutcome.BLOCK:
            self.terminal = True
            self.blocked_reason = result.decision.because
        elif result.pending_approval is not None:
            self.terminal = True
        return payload

    def close(self) -> None:
        """Prevent any late callback from executing another governed tool."""

        self.closed = True

    def assert_complete(self) -> None:
        """Reject prose-only or prematurely ended hosted-model turns."""

        state = self.state
        complete = False
        if self.role == AgentName.INVENTORY:
            complete = state.order is not None and state.inventory_fact is not None
        elif self.role == AgentName.DISPATCH:
            complete = state.dispatch_plan_id is not None
        elif self.role == AgentName.CARRIER and self.phase == RolePhase.RUN:
            complete = (
                state.selected_quote is not None
                and (
                    state.confirmed_booking_id is not None
                    or state.pending_approval_id is not None
                )
            )
        elif self.role == AgentName.CARRIER and self.phase == RolePhase.RESUME_APPROVED:
            complete = state.confirmed_booking_id is not None
        elif self.role == AgentName.CARRIER and self.phase == RolePhase.CANCEL:
            prepared_id = self.approval.prepared_action_id if self.approval else None
            prepared = state.prepared_actions.get(prepared_id or "")
            complete = prepared is not None and prepared.status == CommitmentStatus.CANCELLED
        elif self.role == AgentName.CUSTOMER_COMMUNICATIONS:
            complete = state.notification_id is not None
        if not complete:
            raise AgentIncompleteError(
                f"The {self.role.value} model response ended before its governed role task completed."
            )

    def _bind_arguments(
        self, tool_name: str, model_arguments: dict[str, Any]
    ) -> dict[str, Any]:
        state = self.state
        if tool_name == "get_order":
            return {"order_id": state.order_id}
        if tool_name == "check_inventory":
            if state.order is None:
                raise AgentRuntimeError("Inventory lookup requires the governed order result.")
            return {
                "order_id": state.order_id,
                "sku_id": state.order.sku_id,
                "quantity": state.order.quantity,
            }
        if tool_name == "list_available_vehicles":
            if state.order is None:
                raise AgentRuntimeError("Vehicle lookup requires the governed order result.")
            return {"destination_zone": state.order.destination_zone}
        if tool_name == "create_dispatch_plan":
            attempt = 1 + sum(name == tool_name for name, _ in self.history)
            return {
                "order_id": state.order_id,
                **model_arguments,
                "idempotency_key": f"{state.trace_id}:dispatch-plan:{attempt}",
            }
        if tool_name == "list_carrier_quotes":
            if state.order is None:
                raise AgentRuntimeError("Carrier lookup requires the governed order result.")
            return {
                "order_id": state.order_id,
                "destination_zone": state.order.destination_zone,
            }
        if tool_name == "select_carrier_quote":
            attempt = 1 + sum(name == tool_name for name, _ in self.history)
            return {
                "order_id": state.order_id,
                "quote_id": str(model_arguments["quote_id"]),
                "idempotency_key": f"{state.trace_id}:carrier-selection:{attempt}",
            }
        if tool_name == "prepare_freight_booking":
            quote_id = str(model_arguments["quote_id"])
            return {
                "order_id": state.order_id,
                **model_arguments,
                "idempotency_key": f"{state.trace_id}:prepare:{quote_id}",
            }
        if tool_name in {"confirm_freight_booking", "cancel_freight_booking"}:
            prepared_id = str(model_arguments["prepared_action_id"])
            prepared = state.prepared_actions.get(prepared_id)
            if prepared is None:
                raise AgentRuntimeError("The requested prepared action is not in governed state.")
            bound = {
                "prepared_action_id": prepared_id,
                "action_hash": prepared.action_hash,
                "idempotency_key": f"{state.trace_id}:{'confirm' if tool_name.startswith('confirm') else 'cancel'}:{prepared_id}",
            }
            if tool_name == "cancel_freight_booking":
                if not self.cancellation_reason_code:
                    raise AgentRuntimeError("Cancellation requires a bound reason code.")
                bound["cancellation_reason_code"] = self.cancellation_reason_code
            return bound
        if tool_name == "write_tracking_outbox":
            if state.selected_quote is None or state.confirmed_booking_id is None:
                raise AgentRuntimeError("Notification requires a confirmed governed booking.")
            return {
                "order_id": state.order_id,
                "recipient_ref": f"DEMO-RECIPIENT-{state.order_id.removeprefix('ORD-')}",
                "template_id": "TRACKING_UPDATE_V1",
                "template_variables": {
                    "order_id": state.order_id,
                    "carrier_id": state.selected_quote.carrier_id,
                },
                "idempotency_key": f"{state.trace_id}:tracking-outbox",
            }
        raise AgentRuntimeError(f"Tool {tool_name} has no argument binder.")

    def _safe_value(self, tool_name: str, value: Any) -> Any:
        safe = to_primitive(value)
        if tool_name == "list_available_vehicles":
            order = self.state.order
            fact = self.state.inventory_fact
            if order is None or fact is None:
                raise AgentRuntimeError(
                    "Dispatch vehicle discovery requires governed order and inventory facts."
                )
            return {
                "vehicles": safe,
                "shipment_context": {
                    "order_id": order.order_id,
                    "destination_zone": order.destination_zone,
                    "cargo_class": order.cargo_class,
                    "weight_value": fact.shipment_weight_kg,
                    "weight_unit": "kg",
                    "weight_fact_id": fact.fact_id,
                    "weight_source_id": fact.source_id,
                },
            }
        if tool_name == "list_carrier_quotes":
            order = self.state.order
            if order is None:
                raise AgentRuntimeError(
                    "Carrier quote discovery requires the governed order fact."
                )
            return {
                "quotes": safe,
                "shipment_context": {
                    "order_id": order.order_id,
                    "destination_zone": order.destination_zone,
                    "cargo_class": order.cargo_class,
                },
            }
        if tool_name == "write_tracking_outbox" and isinstance(safe, dict):
            safe.pop("rendered_message", None)
            safe.pop("message", None)
        return safe


def build_strands_tools(context: GovernedInvocationContext) -> list[Any]:
    """Create only the decorated tools available to this isolated role call."""

    def decorate(tool_name: str, function: Any) -> Any:
        definition = context.governor.registry.get_definition(tool_name)
        return tool(
            name=tool_name,
            description=definition.description,
            inputSchema={"json": TOOL_SCHEMAS[tool_name]},
        )(function)

    async def get_order() -> dict[str, Any]:
        return context.execute("get_order", {})

    async def check_inventory() -> dict[str, Any]:
        return context.execute("check_inventory", {})

    async def list_available_vehicles() -> dict[str, Any]:
        return context.execute("list_available_vehicles", {})

    async def create_dispatch_plan(
        vehicle_id: str,
        weight_value: int,
        weight_unit: str,
        weight_fact_id: str,
    ) -> dict[str, Any]:
        return context.execute(
            "create_dispatch_plan",
            {
                "vehicle_id": vehicle_id,
                "weight_value": weight_value,
                "weight_unit": weight_unit,
                "weight_fact_id": weight_fact_id,
            },
        )

    async def list_carrier_quotes() -> dict[str, Any]:
        return context.execute("list_carrier_quotes", {})

    async def select_carrier_quote(quote_id: str) -> dict[str, Any]:
        return context.execute("select_carrier_quote", {"quote_id": quote_id})

    async def prepare_freight_booking(
        quote_id: str, amount_minor: int, currency: str
    ) -> dict[str, Any]:
        return context.execute(
            "prepare_freight_booking",
            {
                "quote_id": quote_id,
                "amount_minor": amount_minor,
                "currency": currency,
            },
        )

    async def confirm_freight_booking(prepared_action_id: str) -> dict[str, Any]:
        return context.execute(
            "confirm_freight_booking",
            {"prepared_action_id": prepared_action_id},
        )

    async def cancel_freight_booking(prepared_action_id: str) -> dict[str, Any]:
        return context.execute(
            "cancel_freight_booking",
            {"prepared_action_id": prepared_action_id},
        )

    async def write_tracking_outbox() -> dict[str, Any]:
        return context.execute("write_tracking_outbox", {})

    functions = {
        "get_order": get_order,
        "check_inventory": check_inventory,
        "list_available_vehicles": list_available_vehicles,
        "create_dispatch_plan": create_dispatch_plan,
        "list_carrier_quotes": list_carrier_quotes,
        "select_carrier_quote": select_carrier_quote,
        "prepare_freight_booking": prepare_freight_booking,
        "confirm_freight_booking": confirm_freight_booking,
        "cancel_freight_booking": cancel_freight_booking,
        "write_tracking_outbox": write_tracking_outbox,
    }
    return [decorate(name, functions[name]) for name in context.allowed_tools]
