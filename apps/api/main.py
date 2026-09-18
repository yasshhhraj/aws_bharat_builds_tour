"""FastAPI application exposing the deterministic Checkpoint 1 journey."""

from __future__ import annotations

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from apps.runtime.service import RunService
from packages.domain.enums import RunStatus
from packages.domain.errors import (
    FixtureError,
    ManifestError,
    OrderNotFoundError,
    TraceNotFoundError,
    UnsupportedModeError,
)
from packages.domain.models import to_primitive

from .dependencies import get_run_service
from .schemas import (
    EventsResponse,
    HealthResponse,
    OrdersResponse,
    ResetResponse,
    RunRequest,
    RunResponse,
)

app = FastAPI(
    title="Manifest Checkpoint 1 API",
    version="0.1.0",
    description="Deterministic four-agent logistics walking skeleton.",
)


def _error_status(exc: ManifestError) -> int:
    if isinstance(exc, (OrderNotFoundError, TraceNotFoundError)):
        return 404
    if isinstance(exc, UnsupportedModeError):
        return 422
    if isinstance(exc, FixtureError):
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
        "version": "0.1.0",
        "runtime_mode": "deterministic",
        "governor_mode": "observe_only",
        "storage_mode": "memory",
        "fixture_count": fixture_count,
    }


@app.get("/v1/fixtures/orders", response_model=OrdersResponse)
async def list_orders(service: RunService = Depends(get_run_service)) -> dict:
    return {"items": [to_primitive(order) for order in service.list_orders()]}


@app.post("/v1/runs", response_model=RunResponse, status_code=201)
async def start_run(
    request: RunRequest,
    service: RunService = Depends(get_run_service),
):
    summary = service.start_run(request.order_id, request.mode)
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


@app.post("/v1/demo/reset", response_model=ResetResponse)
async def reset_demo(service: RunService = Depends(get_run_service)) -> dict:
    return to_primitive(service.reset_demo())
