"""Trajectory-aware governed tool boundary for Manifest."""

from __future__ import annotations

from time import perf_counter
from typing import Any
from uuid import uuid4
import hashlib

from fixtures import FixtureLoader
from packages.domain.enums import (
    AgentName,
    ApprovalStatus,
    CommitmentStatus,
    DecisionOutcome,
    EffectClass,
    EventType,
    GovernanceMode,
    WorkflowStage,
)
from packages.domain.errors import ManifestError, ToolExecutionError, UnknownToolError
from packages.domain.models import (
    Decision,
    EffectRecord,
    GovernedToolResult,
    PendingApproval,
    PolicyRequest,
    PolicySignal,
    ToolProposal,
    TrajectoryState,
    to_primitive,
    utc_now,
)
from packages.ledger.canonical import canonical_json
from packages.storage.keyspace import opaque_key_hash
from packages.storage.models import EffectReceipt
from packages.policy.protocol import PolicyEngine
from packages.storage.protocol import TraceRepository
from packages.tools.registry import ToolRegistry
from .reasons import REASON_CODES


_PRECEDENCE = {
    DecisionOutcome.ALLOW: 0,
    DecisionOutcome.GUIDE: 1,
    DecisionOutcome.ESCALATE: 2,
    DecisionOutcome.BLOCK: 3,
}


class ManifestGovernor:
    def __init__(
        self,
        registry: ToolRegistry,
        store: TraceRepository,
        engine: PolicyEngine,
        loader: FixtureLoader,
        *,
        max_tool_calls: int = 30,
        max_guided_attempts: int = 2,
    ) -> None:
        self.registry = registry
        self.store = store
        self.engine = engine
        self.loader = loader
        self.max_tool_calls = max_tool_calls
        self.max_guided_attempts = max_guided_attempts

    def execute_tool(
        self,
        state: TrajectoryState,
        agent: AgentName,
        tool_name: str,
        **arguments: Any,
    ) -> GovernedToolResult:
        if state.tool_call_count >= self.max_tool_calls:
            raise ToolExecutionError(f"Trace {state.trace_id} exceeded the tool-call limit.")
        state.tool_call_count += 1
        attempt = state.guide_attempts.get(tool_name, 0) + 1
        state.guide_attempts[tool_name] = attempt

        try:
            definition = self.registry.get_definition(tool_name)
        except UnknownToolError:
            definition = None

        proposal = ToolProposal(
            proposal_id=f"PROP-{uuid4()}",
            trace_id=state.trace_id,
            agent=agent,
            tool_name=tool_name,
            effect_class=definition.effect_class if definition else None,
            arguments=self._safe_arguments(tool_name, arguments),
            attempt=attempt,
        )
        self.store.append_event(
            state,
            EventType.TOOL_ATTEMPTED,
            f"{agent.value} attempted {tool_name}.",
            agent=agent,
            tool_name=tool_name,
            effect_class=proposal.effect_class,
            details={"proposal_id": proposal.proposal_id, "attempt": attempt, "arguments": proposal.arguments},
            idempotency_key=f"proposal:{proposal.proposal_id}:attempted",
        )

        started = perf_counter()
        request = self._build_request(state, proposal, definition, arguments)
        if definition is None:
            signals = (
                PolicySignal("ownership", "OWN-UNKNOWN", DecisionOutcome.BLOCK, "UNKNOWN_TOOL", f"Tool {tool_name} is not registered."),
            )
        else:
            try:
                signals = self.engine.evaluate(request, state)
                if any(item.reason_code not in REASON_CODES for item in signals):
                    raise ValueError("Policy engine returned an unknown reason code.")
            except Exception:
                signals = (
                    PolicySignal("engine", "ENGINE-FAIL", DecisionOutcome.BLOCK, "POLICY_ENGINE_FAILURE", "The policy engine failed closed."),
                )
        decision = self._make_decision(state, proposal, request, signals, perf_counter() - started)
        if decision.applied_outcome == DecisionOutcome.GUIDE and attempt >= self.max_guided_attempts:
            decision = self._retry_block(decision)
        self.store.append_decision(state, decision)
        self._record_decision(state, decision)

        if decision.applied_outcome == DecisionOutcome.GUIDE:
            self.store.append_event(
                state, EventType.TOOL_GUIDED, decision.because,
                agent=agent, tool_name=tool_name, effect_class=proposal.effect_class,
                details={"decision_id": decision.decision_id, "guidance": decision.guidance or {}},
                idempotency_key=f"proposal:{proposal.proposal_id}:guided",
            )
            return GovernedToolResult(decision=decision, guidance=decision.guidance)

        if decision.applied_outcome == DecisionOutcome.BLOCK:
            self.store.append_event(
                state, EventType.TOOL_BLOCKED, decision.because,
                agent=agent, tool_name=tool_name, effect_class=proposal.effect_class,
                details={"decision_id": decision.decision_id, "reason_code": decision.reason_code},
                idempotency_key=f"proposal:{proposal.proposal_id}:blocked",
            )
            return GovernedToolResult(decision=decision)

        if decision.applied_outcome == DecisionOutcome.ESCALATE:
            approval = self._create_approval(state, arguments, decision)
            self.store.append_event(
                state, EventType.APPROVAL_REQUIRED, decision.because,
                agent=agent, tool_name=tool_name, effect_class=proposal.effect_class,
                details={
                    "decision_id": decision.decision_id,
                    "approval_id": approval.approval_id,
                    "prepared_action_id": approval.prepared_action_id,
                    "action_hash": approval.action_hash,
                    "state_hash": approval.state_hash,
                    "policy_version": approval.policy_version,
                    "reason_code": approval.reason_code,
                },
                idempotency_key=f"approval:{approval.approval_id}:required",
            )
            return GovernedToolResult(decision=decision, pending_approval=approval)

        if definition is None:
            return GovernedToolResult(decision=decision)
        try:
            value = self._execute_with_durable_receipt(
                state, tool_name, definition.effect_class, arguments
            )
        except ManifestError as exc:
            self._record_failure(
                state, agent, tool_name, proposal.effect_class, exc.message,
                proposal.proposal_id,
            )
            raise
        except Exception as exc:
            message = f"Tool {tool_name} failed unexpectedly."
            self._record_failure(
                state, agent, tool_name, proposal.effect_class, message,
                proposal.proposal_id,
            )
            raise ToolExecutionError(message) from exc
        self.store.append_event(
            state, EventType.TOOL_SUCCEEDED, f"{tool_name} completed successfully.",
            agent=agent, tool_name=tool_name, effect_class=proposal.effect_class,
            details={"result": self._safe_result(tool_name, value)},
            idempotency_key=f"proposal:{proposal.proposal_id}:succeeded",
        )
        if tool_name == "confirm_freight_booking":
            self._apply_confirmation(state, arguments, value)
        elif tool_name == "cancel_freight_booking":
            self._apply_cancellation(state, arguments)
        state.effect_history.append(EffectRecord(tool_name, proposal.effect_class, request.resource_id, agent.value))
        return GovernedToolResult(decision=decision, value=value)

    def _execute_with_durable_receipt(
        self,
        state: TrajectoryState,
        tool_name: str,
        effect_class,
        arguments: dict[str, Any],
    ) -> Any:
        """Replay synthetic writes from durable storage across process restarts."""
        idempotency_key = arguments.get("idempotency_key")
        if effect_class == EffectClass.READ or not isinstance(idempotency_key, str):
            return self.registry.execute(tool_name, arguments)
        key_hash = opaque_key_hash(idempotency_key)
        fingerprint = hashlib.sha256(
            canonical_json(
                {"tool_name": tool_name, "arguments": to_primitive(arguments)}
            ).encode("utf-8")
        ).hexdigest()
        existing = self.store.get_effect_receipt(state.trace_id, key_hash)
        if existing is not None:
            if existing.fingerprint != fingerprint:
                from packages.domain.errors import EffectReceiptConflictError

                raise EffectReceiptConflictError(
                    "An effect idempotency key was reused with different arguments."
                )
            return dict(existing.result)
        result = self.registry.execute(tool_name, arguments)
        if not isinstance(result, dict):
            raise ToolExecutionError(
                f"Write tool {tool_name} returned a non-object result."
            )
        stored = self.store.put_effect_receipt(
            EffectReceipt(
                trace_id=state.trace_id,
                tool_name=tool_name,
                key_hash=key_hash,
                fingerprint=fingerprint,
                result=to_primitive(result),
            )
        )
        return dict(stored.result)

    def _build_request(self, state, proposal, definition, raw_arguments) -> PolicyRequest:
        # Policy evaluation receives typed raw arguments; only trace output is redacted.
        args = to_primitive(raw_arguments)
        context: dict[str, Any] = {
            "tool_owner": definition.owner.value if definition else None,
            "effect_class": definition.effect_class.value if definition else None,
            "arguments": args,
            "resource": self._resource_context(state, proposal.tool_name, args),
        }
        if proposal.tool_name in {"confirm_freight_booking", "cancel_freight_booking"}:
            context["approval"] = self._approval_context(state)
        resource_id = state.order_id
        if proposal.tool_name == "create_dispatch_plan":
            resource_id = str(args.get("vehicle_id", state.order_id))
        elif proposal.tool_name in {"select_carrier_quote", "prepare_freight_booking"}:
            resource_id = str(args.get("quote_id", state.order_id))
        elif proposal.tool_name == "confirm_freight_booking":
            resource_id = str(args.get("prepared_action_id", state.order_id))
        elif proposal.tool_name == "cancel_freight_booking":
            resource_id = str(args.get("prepared_action_id", state.order_id))
        return PolicyRequest(
            request_id=f"REQ-{uuid4()}",
            principal=proposal.agent,
            action=proposal.tool_name,
            resource_type="shipment_action",
            resource_id=resource_id,
            context=context,
        )

    def _resource_context(self, state, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        if tool_name == "create_dispatch_plan":
            vehicle_id = args.get("vehicle_id")
            for vehicle in self.loader.list_vehicles():
                if vehicle.vehicle_id == vehicle_id:
                    return to_primitive(vehicle)
        if tool_name in {"select_carrier_quote", "prepare_freight_booking"}:
            quote_id = args.get("quote_id")
            order = state.order or self.loader.get_order(state.order_id)
            for quote in self.loader.list_carrier_quotes(order.destination_zone):
                if quote.quote_id == quote_id:
                    return to_primitive(quote)
        if tool_name in {"confirm_freight_booking", "cancel_freight_booking"}:
            prepared_id = str(args.get("prepared_action_id", ""))
            prepared = state.prepared_actions.get(prepared_id)
            if prepared is not None:
                return to_primitive(prepared)
        return {}

    def _approval_context(self, state: TrajectoryState) -> dict[str, Any]:
        if not state.pending_approval_id:
            return {}
        try:
            approval = self.store.get_approval(state.pending_approval_id)
        except ManifestError:
            return {}
        value = to_primitive(approval)
        value["is_expired"] = utc_now() >= approval.expires_at
        value.pop("comment", None)
        value.pop("decision_idempotency_key", None)
        return value

    def _make_decision(self, state, proposal, request, signals, elapsed) -> Decision:
        if not signals:
            signals = (
                PolicySignal("default", "DEFAULT-ALLOW", DecisionOutcome.ALLOW, "ALLOW_POLICY_CHECKS_PASSED", "All applicable policy checks passed."),
            )
        primary = max(signals, key=lambda item: _PRECEDENCE[item.outcome])
        guidance: dict[str, Any] = {}
        for item in signals:
            if item.guidance:
                guidance.update(item.guidance)
        enforced = state.mode == GovernanceMode.ENFORCE
        applied = primary.outcome if enforced else DecisionOutcome.ALLOW
        return Decision(
            decision_id=f"DEC-{uuid4()}", request_id=request.request_id,
            trace_id=state.trace_id, proposal_id=proposal.proposal_id,
            agent=proposal.agent, tool_name=proposal.tool_name,
            effect_class=proposal.effect_class, policy_outcome=primary.outcome,
            applied_outcome=applied, enforced=enforced,
            reason_code=primary.reason_code, because=primary.because,
            reasons=tuple(signals), guidance=guidance or None,
            policy_version=state.policy_version, engine_name=self.engine.name,
            evaluation_ms=round(elapsed * 1000, 3),
            policy_bundle_hash=getattr(self.engine, "bundle_hash", None),
        )

    @staticmethod
    def _retry_block(old: Decision) -> Decision:
        return Decision(
            decision_id=old.decision_id, request_id=old.request_id, trace_id=old.trace_id,
            proposal_id=old.proposal_id, agent=old.agent, tool_name=old.tool_name,
            effect_class=old.effect_class, policy_outcome=DecisionOutcome.BLOCK,
            applied_outcome=DecisionOutcome.BLOCK, enforced=True,
            reason_code="GUIDE_RETRY_EXHAUSTED",
            because=f"{old.tool_name} remained invalid after the permitted guided retry.",
            reasons=old.reasons, guidance=old.guidance, policy_version=old.policy_version,
            engine_name=old.engine_name, evaluation_ms=old.evaluation_ms,
            policy_bundle_hash=old.policy_bundle_hash, created_at=old.created_at,
        )

    def _record_decision(self, state: TrajectoryState, decision: Decision) -> None:
        prefix = "Would " if not decision.enforced and decision.policy_outcome != DecisionOutcome.ALLOW else ""
        self.store.append_event(
            state, EventType.POLICY_DECIDED,
            f"{prefix}{decision.policy_outcome.value}: {decision.because}",
            agent=decision.agent, tool_name=decision.tool_name, effect_class=decision.effect_class,
            details={
                "decision_id": decision.decision_id,
                "request_id": decision.request_id,
                "proposal_id": decision.proposal_id,
                "policy_outcome": decision.policy_outcome.value,
                "applied_outcome": decision.applied_outcome.value,
                "enforced": decision.enforced,
                "reason_code": decision.reason_code,
                "because": decision.because,
                "guidance": decision.guidance or {},
                "signals": [
                    {
                        "family": signal.family,
                        "policy_id": signal.policy_id,
                        "outcome": signal.outcome.value,
                        "reason_code": signal.reason_code,
                    }
                    for signal in decision.reasons
                ],
                "policy_version": decision.policy_version,
                "engine_name": decision.engine_name,
                "policy_bundle_hash": decision.policy_bundle_hash,
                "evaluation_ms": decision.evaluation_ms,
            },
            idempotency_key=f"proposal:{decision.proposal_id}:decision",
        )

    def _create_approval(self, state, args, decision) -> PendingApproval:
        prepared_id = str(args.get("prepared_action_id"))
        prepared = state.prepared_actions[prepared_id]
        prepared.status = CommitmentStatus.PENDING_APPROVAL
        approval = PendingApproval(
            approval_id=f"APR-{uuid4()}", trace_id=state.trace_id,
            prepared_action_id=prepared_id, action_hash=prepared.action_hash,
            state_hash=prepared.state_hash, policy_version=state.policy_version,
            reason_code=decision.reason_code, status=ApprovalStatus.PENDING_APPROVAL,
            created_at=utc_now(), expires_at=prepared.expires_at,
        )
        state.pending_approval_id = approval.approval_id
        self.store.add_approval(state, approval)
        return approval

    @staticmethod
    def _apply_confirmation(state: TrajectoryState, arguments: dict[str, Any], value: Any) -> None:
        prepared = state.prepared_actions[str(arguments["prepared_action_id"])]
        if prepared.status == CommitmentStatus.CONFIRMED:
            return
        if state.spend_reserved_minor < prepared.amount_minor:
            raise ToolExecutionError("Reserved spend cannot become negative during confirmation.")
        prepared.status = CommitmentStatus.CONFIRMED
        state.confirmed_booking_id = str(value["confirmation_id"])
        state.spend_reserved_minor -= prepared.amount_minor
        state.spend_committed_minor += prepared.amount_minor
        state.pending_approval_id = None
        state.workflow_stage = WorkflowStage.BOOKING_CONFIRMED

    @staticmethod
    def _apply_cancellation(state: TrajectoryState, arguments: dict[str, Any]) -> None:
        prepared = state.prepared_actions[str(arguments["prepared_action_id"])]
        if prepared.status == CommitmentStatus.CANCELLED:
            return
        if prepared.status == CommitmentStatus.CONFIRMED:
            raise ToolExecutionError("A confirmed booking cannot be cancelled.")
        if state.spend_reserved_minor < prepared.amount_minor:
            raise ToolExecutionError("Reserved spend cannot become negative during cancellation.")
        prepared.status = CommitmentStatus.CANCELLED
        state.spend_reserved_minor -= prepared.amount_minor
        state.pending_approval_id = None

    def _record_failure(
        self, state, agent, tool_name, effect_class, message, proposal_id
    ) -> None:
        self.store.append_event(
            state,
            EventType.TOOL_FAILED,
            message,
            agent=agent,
            tool_name=tool_name,
            effect_class=effect_class,
            details={"error": message},
            idempotency_key=f"proposal:{proposal_id}:failed",
        )

    @staticmethod
    def _safe_arguments(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        safe = to_primitive(arguments)
        if tool_name == "write_tracking_outbox":
            for key in ("message", "phone", "email", "address", "name", "payment"):
                safe.pop(key, None)
        return safe

    @staticmethod
    def _safe_result(tool_name: str, value: Any) -> Any:
        safe = to_primitive(value)
        if tool_name == "write_tracking_outbox" and isinstance(safe, dict):
            safe.pop("rendered_message", None)
            safe.pop("message", None)
        return safe
