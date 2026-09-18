# Manifest

Manifest is a learning-focused hackathon prototype for governing autonomous
logistics-agent actions before they create physical or financial effects.

## Current status

**Checkpoint 1 is implemented.** One deterministic shipment travels through
four plain-Python agent roles. Every tool call crosses an observation-only
governor, receives an effect classification, and appears in an ordered trace.

This checkpoint intentionally uses no LLM, agent SDK, cloud service, real PII,
or real logistics integration. The build specification is in
[`docs/CHECKPOINT_1_IMPLEMENTATION_PLAN.md`](docs/CHECKPOINT_1_IMPLEMENTATION_PLAN.md).

## Requirements and setup

- Python 3.10 or newer

From `/home/yashraj/p0/project`:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e '.[dev]'
```

No AWS account or credentials are needed for Checkpoint 1.

## Run the four-agent journey

```bash
python3 -m apps.runtime.run --order ORD-8842
```

Expected result:

```text
Inventory Agent -> sourced 500 kg fact
Dispatch Agent -> refrigerated vehicle VEH-COLD-01
Carrier Agent -> certified carrier CARRIER-COLD-01 for INR 900
Customer Communications Agent -> simulated outbox notification
Run status: COMPLETED
```

An unknown order returns a non-zero exit code:

```bash
python3 -m apps.runtime.run --order UNKNOWN
```

## Run the API

```bash
python3 -m uvicorn apps.api.main:app --reload
```

Open <http://127.0.0.1:8000/docs>, or run:

```bash
curl http://127.0.0.1:8000/health/ready

curl -X POST http://127.0.0.1:8000/v1/runs \
  -H 'content-type: application/json' \
  -d '{"order_id":"ORD-8842","mode":"shadow"}'
```

Use the returned `trace_id` with:

```bash
curl http://127.0.0.1:8000/v1/runs/TR-REPLACE-ME
curl http://127.0.0.1:8000/v1/traces/TR-REPLACE-ME/events
```

| Method | Path | Purpose |
|---|---|---|
| GET | `/health/ready` | Check runtime, governor, storage, and fixture status |
| GET | `/v1/fixtures/orders` | List synthetic demo orders |
| POST | `/v1/runs` | Run `ORD-8842` synchronously in shadow mode |
| GET | `/v1/runs/{trace_id}` | Read a run summary |
| GET | `/v1/traces/{trace_id}/events` | Read ordered trace events |
| POST | `/v1/demo/reset` | Clear in-memory demo runs and mock writes |

## Run tests

```bash
python3 -m pytest -q
```

Or run the full verification script:

```bash
./scripts/run_checkpoint_1.sh
```

## Architecture

```text
CLI / FastAPI
     |
     v
RunService -> ShipmentOrchestrator
                   |
                   +-- Inventory Agent
                   +-- Dispatch Agent
                   +-- Carrier Agent
                   +-- Customer Communications Agent
                              |
                              v
                    ObserverGovernor
                              |
                              v
                    ToolRegistry -> Mock tools
                              |
                              v
                    MemoryTraceStore
```

The governor currently records `ALLOW` with
`CHECKPOINT_1_OBSERVE_ONLY`; it does not enforce business policies yet.

## Layout

```text
apps/runtime/          Four agents, orchestrator, service, and CLI
apps/api/              FastAPI schemas, routes, and dependency wiring
packages/domain/       Shared enums, dataclasses, and typed errors
packages/tools/        Effect-classified registry and mock logistics tools
packages/governor/     Observation-only governed tool boundary
packages/ledger/       Thread-safe in-memory run and event store
fixtures/              Deterministic synthetic data and expected journey
tests/                 Unit, integration, API, and CLI end-to-end tests
```

## Real and simulated behavior

Real in this checkpoint:

- Agent sequencing and state handoffs
- Tool ownership and effect classification
- Governor interception and structured decisions
- Trace IDs, ordered events, failure recording, and isolation
- CLI and API responses

Simulated:

- Inventory/WMS data
- Vehicle planning
- Carrier quotes and selection
- Customer notification outbox

Deferred to later checkpoints:

- Strands and Bedrock inference
- Cedar enforcement and guide-back
- Weight drift and commitment-budget controls
- Approval workflow
- Hash-chained DynamoDB ledger
- Dashboard and AWS deployment

See the full hackathon plan in
[`../docs/Manifest_36_Hour_Hackathon_Prototype_Plan.md`](../docs/Manifest_36_Hour_Hackathon_Prototype_Plan.md).
