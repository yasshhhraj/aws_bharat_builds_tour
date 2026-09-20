"""Bounded execution of one Manifest role through Strands."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from threading import Event
from time import perf_counter

from strands import Agent
from strands.tools.executors import SequentialToolExecutor

from packages.domain.enums import EventType
from packages.domain.errors import (
    AgentRuntimeError,
    ManifestError,
    PolicyBlockedError,
    ProviderTimeoutError,
)

from .agent_runtime import AgentRunRequest, AgentRunResult, RoleRuntime
from .model_factory import DefaultManifestModelFactory, ManifestModelFactory
from .provider_errors import classify_provider_error
from .runtime_settings import RuntimeSettings
from .strands_tools import GovernedInvocationContext, build_strands_tools


class StrandsRuntime(RoleRuntime):
    def __init__(
        self,
        settings: RuntimeSettings,
        model_factory: ManifestModelFactory | None = None,
    ) -> None:
        settings.validate()
        if settings.runtime_mode != "strands":
            raise AgentRuntimeError("Strands runtime received non-Strands settings.")
        self.settings = settings
        self.model_factory = model_factory or DefaultManifestModelFactory()
        self.model_factory.validate(settings)

    def invoke(self, request: AgentRunRequest) -> AgentRunResult:
        context = GovernedInvocationContext(
            role=request.role,
            phase=request.phase,
            state=request.state,
            governor=request.governor,
            approval=request.approval,
            cancellation_reason_code=request.cancellation_reason_code,
        )
        try:
            model = self.model_factory.create(self.settings, context)
        except Exception as exc:
            context.close()
            if isinstance(exc, ManifestError):
                raise
            raise classify_provider_error(self.settings.model_provider, exc) from exc
        agent = Agent(
            name=f"manifest-{request.role.value}",
            description="A bounded governed Manifest logistics role.",
            model=model,
            tools=build_strands_tools(context),
            system_prompt=(
                "This is the synthetic Manifest prototype. Execute the bounded role task "
                "using only the supplied governed tools, one tool at a time. Treat governed "
                "tool results as authoritative and follow any guide-back they return. Never "
                "invent identity, authority, policy, approval, numeric facts, identifiers, or "
                "side effects. A successful read is not completion when a governed write is "
                "required. Continue until the role objective is complete, then stop."
            ),
            callback_handler=None,
            load_tools_from_directory=False,
            tool_executor=SequentialToolExecutor(),
            retry_strategy=None,
        )
        cancel_signal = Event()
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="manifest-strands")
        started_at = perf_counter()
        future = executor.submit(
            agent,
            self._prompt(request),
            invocation_state={
                "trace_id": request.state.trace_id,
                "role": request.role.value,
                "phase": request.phase.value,
            },
            limits={
                "turns": self.settings.max_turns,
                "output_tokens": self.settings.max_output_tokens,
                "total_tokens": 10_000,
            },
            cancel_signal=cancel_signal,
        )
        try:
            result = future.result(timeout=self.settings.timeout_seconds)
        except FutureTimeoutError as exc:
            context.close()
            cancel_signal.set()
            agent.cancel()
            if self.settings.model_provider in {
                "openrouter",
                "bedrock_mantle",
                "bedrock",
            }:
                raise ProviderTimeoutError(
                    f"{self.settings.model_provider.title()} model request timed out."
                ) from exc
            raise AgentRuntimeError(
                f"The {request.role.value} Strands invocation timed out."
            ) from exc
        except Exception as exc:
            context.close()
            mapped = classify_provider_error(self.settings.model_provider, exc)
            if isinstance(exc, ManifestError):
                raise exc
            raise mapped from exc
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        try:
            if context.blocked_reason:
                raise PolicyBlockedError(context.blocked_reason)
            if result.stop_reason != "end_turn":
                raise AgentRuntimeError(
                    f"The {request.role.value} Strands invocation stopped with "
                    f"{result.stop_reason}."
                )
            context.assert_complete()
            summary = str(result).strip()
            if not summary:
                raise AgentRuntimeError(
                    f"The {request.role.value} Strands invocation returned no summary."
                )
            usage = result.metrics.accumulated_usage
            run_result = AgentRunResult(
                summary=summary,
                stop_reason=result.stop_reason,
                turn_count=result.metrics.cycle_count,
                runtime_mode=self.settings.runtime_mode,
                model_provider=self.settings.model_provider,
                model_id=self.settings.model_id,
                latency_ms=round((perf_counter() - started_at) * 1000, 3),
                input_tokens=_usage_value(usage, "inputTokens"),
                output_tokens=_usage_value(usage, "outputTokens"),
                total_tokens=_usage_value(usage, "totalTokens"),
            )
            request.governor.store.append_event(
                request.state,
                EventType.AGENT_MODEL_COMPLETED,
                f"Completed bounded {request.role.value} model invocation.",
                agent=request.role,
                details={
                    "runtime_mode": run_result.runtime_mode,
                    "model_provider": run_result.model_provider,
                    "requested_model_id": run_result.model_id,
                    "resolved_model_id": None,
                    "provider_route_kind": self.settings.provider_route_kind,
                    "provider_fallback_active": False,
                    "phase": request.phase.value,
                    "model_latency_ms": run_result.latency_ms,
                    "model_cycles": run_result.turn_count,
                    "input_tokens": run_result.input_tokens,
                    "output_tokens": run_result.output_tokens,
                    "total_tokens": run_result.total_tokens,
                },
                idempotency_key=(
                    f"model:{request.state.trace_id}:{request.role.value}:"
                    f"{request.phase.value}:completed"
                ),
            )
            return run_result
        finally:
            context.close()

    @staticmethod
    def _prompt(request: AgentRunRequest) -> str:
        objective = {
            "inventory": (
                "Call get_order, then call check_inventory. Finish only after both governed "
                "reads succeed."
            ),
            "dispatch": (
                "Call list_available_vehicles. Read shipment_context and vehicles from that "
                "governed result, choose a compliant vehicle, then call create_dispatch_plan "
                "using the exact governed weight value, unit, and fact ID. If guided, apply "
                "the returned required values and try the governed plan once more."
            ),
            "carrier": (
                "Call list_carrier_quotes, choose a quote compatible with shipment_context, "
                "call select_carrier_quote, call prepare_freight_booking with the exact quote "
                "amount and currency, then call confirm_freight_booking with the returned "
                "prepared action ID. Follow guide-back and stop if approval becomes pending."
            ),
            "customer_communications": (
                "Call write_tracking_outbox and finish only after it succeeds."
            ),
        }[request.role.value]
        if request.phase.value == "resume_approved":
            objective = "Confirm only the prepared booking bound to the verified approval."
        elif request.phase.value == "cancel":
            objective = "Cancel only the prepared booking bound to this continuation."
        return (
            f"Execute role={request.role.value} phase={request.phase.value} "
            f"for synthetic order={request.state.order_id}. {objective} "
            "Use only supplied tools and execute the task rather than describing it."
        )


def _usage_value(usage: object, key: str) -> int | None:
    if not isinstance(usage, dict):
        return None
    value = usage.get(key)
    return value if isinstance(value, int) else None


# Temporary import compatibility for Checkpoint 9 callers. New code uses StrandsRuntime.
StrandsRecordedRuntime = StrandsRuntime
