"""FastAPI application exposing the governed Checkpoint 2 journey."""

from __future__ import annotations

from typing import Literal

from fastapi import Depends, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from apps.runtime.service import RunService
from packages.domain.enums import RunStatus
from packages.domain.errors import (
    ApprovalAuthNotConfiguredError,
    ApprovalBindingError,
    ApprovalExpiredError,
    ApprovalIdempotencyConflictError,
    ApprovalNotFoundError,
    ApprovalNotPendingError,
    ApprovalVersionConflictError,
    ApproverConflictError,
    ApproverUnauthorizedError,
    FixtureError,
    ManifestError,
    OrderNotFoundError,
    TraceNotFoundError,
    UnsupportedModeError,
    UnsupportedScenarioError,
)
from packages.domain.models import to_primitive

from .dependencies import approval_mutation_ready, get_run_service, verify_demo_approver_secret
from .schemas import (
    ApprovalDecisionRequest,
    ApprovalDecisionResponse,
    ApprovalResponse,
    EventsResponse,
    DecisionsResponse,
    ApprovalsResponse,
    HealthResponse,
    OrdersResponse,
    ResetResponse,
    RunRequest,
    RunResponse,
)

app = FastAPI(
    title="Manifest Checkpoint 3 API",
    version="0.5.0",
    description="Deterministic governed logistics workflow with approval and resume.",
)


def _error_status(exc: ManifestError) -> int:
    if isinstance(exc, (OrderNotFoundError, TraceNotFoundError, ApprovalNotFoundError)):
        return 404
    if isinstance(exc, ApproverUnauthorizedError):
        return 401
    if isinstance(exc, ApprovalExpiredError):
        return 410
    if isinstance(
        exc,
        (
            ApprovalBindingError,
            ApprovalIdempotencyConflictError,
            ApprovalNotPendingError,
            ApprovalVersionConflictError,
            ApproverConflictError,
        ),
    ):
        return 409
    if isinstance(exc, (UnsupportedModeError, UnsupportedScenarioError)):
        return 422
    if isinstance(exc, (FixtureError, ApprovalAuthNotConfiguredError)):
        return 503
    return 400


@app.exception_handler(ManifestError)
async def manifest_error_handler(_request: Request, exc: ManifestError) -> JSONResponse:
    return JSONResponse(
        status_code=_error_status(exc),
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    _request: Request, _exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "The request is not valid for this endpoint.",
            }
        },
    )


@app.get("/health/ready", response_model=HealthResponse)
async def health_ready():
    try:
        service = await get_run_service()
        fixture_count = len(service.list_orders())
    except ManifestError as exc:
        return JSONResponse(
            status_code=503,
            content={"error": {"code": exc.code, "message": exc.message}},
        )
    return {
        "status": "ready",
        "version": "0.5.0",
        "runtime_mode": "deterministic",
        "governor_mode": "policy_enforced",
        "policy_engine": service.policy_engine.name,
        "policy_version": service.policy_engine.policy_version,
        "storage_mode": "memory",
        "fixture_count": fixture_count,
        "supported_modes": ["shadow", "enforce"],
        "supported_scenarios": ["benign", "adversarial"],
        "approval_mode": "local",
        "approval_auth_mode": "demo_shared_secret",
        "approval_mutation_ready": approval_mutation_ready(),
    }


@app.get("/v1/fixtures/orders", response_model=OrdersResponse)
async def list_orders(service: RunService = Depends(get_run_service)) -> dict:
    return {"items": [to_primitive(order) for order in service.list_orders()]}


@app.post("/v1/runs", response_model=RunResponse, status_code=201)
async def start_run(
    request: RunRequest,
    service: RunService = Depends(get_run_service),
):
    summary = service.start_run(request.order_id, request.mode, request.scenario)
    content = to_primitive(summary)
    if summary.status == RunStatus.FAILED:
        return JSONResponse(status_code=500, content=content)
    return content


@app.get("/v1/runs/{trace_id}", response_model=RunResponse)
async def get_run(trace_id: str, service: RunService = Depends(get_run_service)) -> dict:
    return to_primitive(service.get_run(trace_id))


@app.get("/v1/traces/{trace_id}/events", response_model=EventsResponse)
async def get_events(trace_id: str, service: RunService = Depends(get_run_service)) -> dict:
    return {
        "trace_id": trace_id,
        "items": [to_primitive(event) for event in service.get_events(trace_id)],
    }


@app.get("/v1/traces/{trace_id}/decisions", response_model=DecisionsResponse)
async def get_decisions(trace_id: str, service: RunService = Depends(get_run_service)) -> dict:
    return {
        "trace_id": trace_id,
        "items": [to_primitive(decision) for decision in service.get_decisions(trace_id)],
    }


@app.get("/v1/approvals", response_model=ApprovalsResponse)
async def list_approvals(
    trace_id: str | None = None,
    status: Literal["pending_approval", "approved", "rejected", "expired"] | None = None,
    service: RunService = Depends(get_run_service),
) -> dict:
    return {"items": [to_primitive(item) for item in service.list_approvals(trace_id, status)]}


@app.get("/v1/approvals/{approval_id}", response_model=ApprovalResponse)
async def get_approval(
    approval_id: str,
    service: RunService = Depends(get_run_service),
) -> dict:
    return to_primitive(service.get_approval(approval_id))


@app.post("/v1/approvals/{approval_id}", response_model=ApprovalDecisionResponse)
async def decide_approval(
    approval_id: str,
    request: ApprovalDecisionRequest,
    approver_secret: str | None = Header(default=None, alias="X-Demo-Approver-Secret"),
    service: RunService = Depends(get_run_service),
) -> dict:
    verify_demo_approver_secret(approver_secret)
    resolution = service.resolve_approval(
        approval_id,
        decision=request.decision,
        approver_label=request.approver_label,
        comment=request.comment,
        expected_version=request.expected_version,
        idempotency_key=request.idempotency_key,
    )
    return to_primitive(resolution)


@app.post("/v1/demo/reset", response_model=ResetResponse)
async def reset_demo(service: RunService = Depends(get_run_service)) -> dict:
    return to_primitive(service.reset_demo())
