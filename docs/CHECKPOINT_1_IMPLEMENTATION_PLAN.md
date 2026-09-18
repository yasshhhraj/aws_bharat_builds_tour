# Checkpoint 1 Implementation Plan

## 1. Objective

Build the first complete, deterministic Manifest journey with plain Python.
One benign synthetic shipment must travel through four agent roles, every tool
attempt must be registered and recorded, and the completed trace must be
available from both a CLI command and a small HTTP API.

Checkpoint 1 is a **walking skeleton**. It proves that all major components can
communicate before policy enforcement, model inference, cloud storage, or a
dashboard are introduced.

## 2. User-visible result

Running:

```bash
python3 -m apps.runtime.run --order ORD-8842
```

must produce a successful journey resembling:

```text
Manifest trace: <trace-id>
1. Inventory Agent verified 500 kg of available stock.
2. Dispatch Agent selected refrigerated vehicle VEH-COLD-01.
3. Carrier Agent selected certified carrier CARRIER-COLD-01 for INR 900.
4. Customer Communications Agent wrote a simulated tracking message.
Run status: COMPLETED
```

The same journey must be startable through `POST /v1/runs`, and its summary and
ordered events must be retrievable through HTTP.

## 3. Scope

### Included

- One deterministic order fixture: `ORD-8842`.
- Supporting SKU, vehicle, carrier, quote, and inventory fixtures.
- Four plain-Python agent classes.
- A bounded sequential orchestrator.
- A registry of every tool and its effect class.
- Deterministic mock logistics tools.
- One trace-scoped mutable state object per run.
- Observation-only governor hook around every tool call.
- An in-memory run and event store.
- An ordered structured event trace.
- CLI entry point.
- Minimal FastAPI service.
- Unit, integration, API, and end-to-end tests.
- Clear errors for invalid fixtures, unknown orders, unknown tools, and failed
  runs.

### Explicitly excluded

- Strands Agents SDK or any other agent framework.
- Amazon Bedrock or any LLM call.
- Cedar policy evaluation or blocking decisions.
- Weight-drift enforcement.
- Cold-chain enforcement and guide-back.
- Commitment-budget enforcement.
- Prepare, approve, and confirm state.
- Hash chaining and tamper verification.
- DynamoDB or any AWS deployment.
- React dashboard.
- Real WMS, TMS, carrier, payment, or messaging calls.

Those features belong to later checkpoints. Checkpoint 1 should make them easy
to add without pretending they already work.

## 4. Architectural rule

Agents may not read fixture files directly and may not call mock functions
directly. All operational work must pass through the tool registry and the
observation-only governor.

```text
CLI or API
    |
    v
RunService / Orchestrator
    |
    +--> Inventory Agent
    +--> Dispatch Agent
    +--> Carrier Agent
    +--> Communications Agent
              |
              v
       Governor.execute_tool()
              |
              v
          ToolRegistry
              |
              v
     Deterministic mock adapter
              |
              v
       TrajectoryState + TraceStore
```

This boundary is important: later checkpoints can replace the observer with
Cedar-backed enforcement and replace agent rules with model-generated tool
choices without rewriting the mock tools or API.

## 5. Planned project structure

```text
project/
  apps/
    runtime/
      agents/
        __init__.py
        base.py
        inventory.py
        dispatch.py
        carrier.py
        communications.py
      orchestrator.py
      service.py
      run.py
    api/
      main.py
      schemas.py
      dependencies.py
  packages/
    domain/
      enums.py
      models.py
      errors.py
    tools/
      definitions.py
      registry.py
      mocks.py
    governor/
      observer.py
    ledger/
      memory_store.py
  fixtures/
    orders/
      ORD-8842.json
    inventory/
      inventory.json
    vehicles/
      vehicles.json
    carriers/
      carriers.json
    expected/
      ORD-8842-events.json
    loader.py
  tests/
    unit/
      test_fixture_loader.py
      test_tool_registry.py
      test_mock_tools.py
      test_agents.py
      test_memory_store.py
    integration/
      test_orchestrator.py
      test_trace_isolation.py
    e2e/
      test_cli_journey.py
      test_api_journey.py
  scripts/
    run_checkpoint_1.sh
```

The files should be introduced in the implementation order in Section 14.

## 6. Domain contracts

Use standard-library `dataclasses`, `Enum`, and type hints for the core runtime.
Pydantic should be used only at the FastAPI boundary. This keeps the first
workflow understandable without requiring framework knowledge.

### 6.1 Enums

`AgentName`:

- `INVENTORY`
- `DISPATCH`
- `CARRIER`
- `CUSTOMER_COMMUNICATIONS`

`EffectClass`:

- `READ`
- `REVERSIBLE_WRITE`
- `FINANCIAL_COMMIT`
- `PHYSICAL_COMMIT`
- `EXTERNAL_DISCLOSURE`

`RunStatus`:

- `PENDING`
- `RUNNING`
- `COMPLETED`
- `FAILED`

`EventType`:

- `RUN_STARTED`
- `AGENT_STARTED`
- `TOOL_ATTEMPTED`
- `GOVERNANCE_OBSERVED`
- `TOOL_SUCCEEDED`
- `TOOL_FAILED`
- `AGENT_COMPLETED`
- `RUN_COMPLETED`
- `RUN_FAILED`

### 6.2 Core models

`Order`:

```text
order_id: str
sku_id: str
quantity: int
cargo_class: str
destination_zone: str
currency: str
spend_ceiling_minor: int
```

`InventoryFact`:

```text
fact_id: str
sku_id: str
available_quantity: int
shipment_weight_kg: int
source_id: str
```

`Vehicle`:

```text
vehicle_id: str
capacity_kg: int
refrigerated: bool
available: bool
```

`CarrierQuote`:

```text
quote_id: str
carrier_id: str
amount_minor: int
currency: str
cold_chain_certified: bool
lane_supported: bool
```

`ToolDefinition`:

```text
name: str
owner: AgentName
effect_class: EffectClass
description: str
idempotent: bool
```

`TraceEvent`:

```text
trace_id: str
sequence: int
event_type: EventType
agent: AgentName | None
tool_name: str | None
effect_class: EffectClass | None
summary: str
details: dict
occurred_at: UTC datetime
```

`TrajectoryState`:

```text
trace_id: str
order_id: str
status: RunStatus
current_agent: AgentName | None
inventory_fact: InventoryFact | None
selected_vehicle: Vehicle | None
selected_quote: CarrierQuote | None
notification_id: str | None
events: list[TraceEvent]
next_sequence: int
error: str | None
```

`RunSummary`:

```text
trace_id: str
order_id: str
status: RunStatus
current_agent: AgentName | None
selected_vehicle_id: str | None
selected_carrier_id: str | None
selected_amount_minor: int | None
notification_id: str | None
event_count: int
error: str | None
```

### 6.3 Modeling rules

- Money is always stored in integer minor units. INR 900 is `90000`.
- Weight is an integer number of kilograms in Checkpoint 1.
- IDs are strings and must never be inferred from list positions.
- Runtime models do not contain FastAPI objects.
- `TrajectoryState` exists once per trace and is never global.
- Events are append-only from the runtime's point of view.
- API responses return enum values as lowercase strings.
- Timestamps are UTC ISO 8601 strings in API output.

## 7. Deterministic fixtures

### 7.1 Primary order

`ORD-8842.json`:

```json
{
  "order_id": "ORD-8842",
  "sku_id": "SKU-17",
  "quantity": 10,
  "cargo_class": "perishable",
  "destination_zone": "BLR-SOUTH",
  "currency": "INR",
  "spend_ceiling_minor": 400000
}
```

### 7.2 Inventory

The inventory fixture must establish:

- `SKU-17` has sufficient stock.
- The authoritative shipment weight is 500 kg.
- The stable source is `WMS-SNAPSHOT-001`.
- The resulting fact ID is `WEIGHT-ORD-8842`.

### 7.3 Vehicles

Include at least:

- `VEH-COLD-01`: 1,000 kg capacity, refrigerated, available.
- `VEH-SMALL-01`: 100 kg capacity, not refrigerated, available.

Checkpoint 1's deterministic dispatch rule selects `VEH-COLD-01`. The smaller
vehicle exists for the later adversarial checkpoint.

### 7.4 Carriers

Include at least:

- `CARRIER-COLD-01`: INR 900, cold-chain certified, lane supported.
- `CARRIER-CHEAP-01`: INR 700, not cold-chain certified, lane supported.

Checkpoint 1 deterministically selects `CARRIER-COLD-01`. The cheaper carrier
exists for later policy-enforcement work.

### 7.5 Fixture loader requirements

The loader must:

- Resolve fixtures from the project directory, not the current shell directory.
- Reject missing required fields.
- Reject duplicate IDs.
- Return fresh objects so one run cannot mutate another run's fixtures.
- Raise a typed `FixtureError` with a safe, understandable message.
- Never silently invent missing data.

## 8. Tool registry and mock tools

### 8.1 Tool registry behavior

The registry maps each tool name to both metadata and a Python callable.

Required operations:

```text
register(definition, handler)
get_definition(tool_name)
execute(tool_name, arguments)
list_definitions()
validate_startup()
```

Startup validation fails if:

- A handler has no definition.
- A definition has no handler.
- Tool names are duplicated.
- Owner or effect class is missing.

Unknown tools raise `UnknownToolError`; they are never ignored.

### 8.2 Required tools

| Tool | Owner | Effect class | Input | Output |
|---|---|---|---|---|
| `get_order` | Inventory | Read | `order_id` | `Order` |
| `check_inventory` | Inventory | Read | `order_id`, `sku_id`, `quantity` | `InventoryFact` |
| `list_available_vehicles` | Dispatch | Read | `destination_zone` | `list[Vehicle]` |
| `create_dispatch_plan` | Dispatch | Reversible write | `order_id`, `vehicle_id`, `weight_kg` | plan ID |
| `list_carrier_quotes` | Carrier | Read | `order_id`, `destination_zone` | `list[CarrierQuote]` |
| `select_carrier_quote` | Carrier | Reversible write | `order_id`, `quote_id` | selection ID |
| `write_tracking_outbox` | Customer Communications | External disclosure | `order_id`, safe message | notification ID |

Although `write_tracking_outbox` is classified as external disclosure, it only
writes a synthetic record in memory. It sends no message and contains no real
PII.

### 8.3 Determinism rules

- Tool output is derived only from fixtures and explicit arguments.
- Tools do not sleep, call networks, read environment secrets, or generate
  random operational values.
- Stable IDs should be generated from the trace/order and operation name.
- Repeating an idempotent write with the same idempotency key returns the same
  result.
- Invalid inputs raise typed domain errors.

## 9. Observation-only governor

Checkpoint 1 does not authorize or block actions. It proves that every action
crosses a single future enforcement point.

`ObserverGovernor.execute_tool(...)` performs this sequence:

1. Confirm the tool exists.
2. Confirm the calling agent matches the tool owner.
3. Append `TOOL_ATTEMPTED`.
4. Append `GOVERNANCE_OBSERVED` with:
   - `outcome: "ALLOW"`
   - `enforced: false`
   - `reason_code: "CHECKPOINT_1_OBSERVE_ONLY"`
5. Invoke the registered mock handler.
6. Append `TOOL_SUCCEEDED` with a redacted result summary.
7. If the handler raises, append `TOOL_FAILED` and re-raise a typed error.

Even in observation-only mode, an agent must not invoke another agent's tool.
That is treated as a programming/configuration error, not as a business-policy
decision.

No raw fixture dump should be stored in events. Event details should contain
only fields needed to explain the demo.

## 10. Agent skeletons

Every agent implements the same small interface:

```text
name: AgentName
run(state, governor) -> None
```

Agents update the supplied trace-scoped state and return normally on success.
They do not create traces, catch unexpected exceptions, or decide which agent
runs next. The orchestrator owns those responsibilities.

### 10.1 Inventory Agent

Responsibilities:

1. Read `ORD-8842` with `get_order`.
2. Check inventory with `check_inventory`.
3. Store the returned `InventoryFact` in trajectory state.
4. Finish with a summary that includes 500 kg and the source ID.

It must not choose a vehicle, carrier, or notification.

### 10.2 Dispatch Agent

Precondition: `state.inventory_fact` exists.

Responsibilities:

1. Call `list_available_vehicles`.
2. Deterministically choose the first available refrigerated vehicle that can
   carry the authoritative 500 kg weight.
3. Call `create_dispatch_plan` using the fact's weight.
4. Store the selected vehicle and plan ID.

If no suitable vehicle exists, raise `NoSuitableVehicleError` and let the
orchestrator fail the run.

### 10.3 Carrier Agent

Precondition: a dispatch plan exists.

Responsibilities:

1. Call `list_carrier_quotes`.
2. Deterministically choose the lowest-priced quote that is cold-chain
   certified and supports the lane.
3. Call `select_carrier_quote`.
4. Store the selected quote and selection ID.

This is a simple Python selection rule, not Cedar enforcement. The later
adversarial checkpoint will deliberately attempt the cheaper uncertified quote
and let the governor correct it.

### 10.4 Customer Communications Agent

Precondition: a carrier quote has been selected.

Responsibilities:

1. Build a message from fixed safe fields: order ID, carrier ID, and synthetic
   tracking label.
2. Call `write_tracking_outbox`.
3. Store the returned notification ID.

No name, phone number, street address, email address, or real message provider
is introduced.

## 11. Orchestrator and run service

### 11.1 Orchestrator

The orchestrator owns the fixed Checkpoint 1 sequence:

```text
Inventory -> Dispatch -> Carrier -> Customer Communications
```

Algorithm:

1. Create a unique `trace_id`.
2. Create a fresh `TrajectoryState` with status `RUNNING`.
3. Append `RUN_STARTED`.
4. For each agent:
   - set `current_agent`;
   - append `AGENT_STARTED`;
   - call `agent.run(...)`;
   - append `AGENT_COMPLETED`.
5. Set status to `COMPLETED`.
6. Clear `current_agent`.
7. Append `RUN_COMPLETED`.
8. Persist and return a `RunSummary`.

On any expected or unexpected exception:

1. Set status to `FAILED`.
2. Store a safe error message.
3. Append `RUN_FAILED`.
4. Keep all prior events available for diagnosis.
5. Return or raise a typed service error depending on the caller.

### 11.2 Bounds

- Exactly four agents run in Checkpoint 1.
- Each agent may make only its documented tool calls.
- No retry loop is allowed yet.
- A maximum tool-call count is configured defensively; exceeding it fails the
  run.
- The orchestrator contains no FastAPI code.

### 11.3 Run service

`RunService` is the application-facing interface used by both CLI and API:

```text
start_run(order_id) -> RunSummary
get_run(trace_id) -> RunSummary
get_events(trace_id) -> list[TraceEvent]
list_orders() -> list[OrderSummary]
reset_demo() -> ResetResult
```

For Checkpoint 1, `start_run` is synchronous: the response is returned only
after the four-agent journey completes or fails. This avoids background-task
complexity. The contract can become asynchronous later without changing the
orchestrator.

## 12. In-memory trace store

`MemoryTraceStore` holds runs and events keyed by trace ID.

Required behavior:

- Append an event only when its sequence equals the next expected sequence.
- Return events ordered by sequence.
- Return copies/read-only representations to callers.
- Keep two traces fully isolated.
- Raise `TraceNotFoundError` for unknown IDs.
- Reset only demo memory state.
- Be protected by a simple lock so two API requests cannot corrupt its maps.

This is not yet the tamper-evident ledger. Its interface should make replacing
it with a DynamoDB hash-chain implementation possible later.

## 13. HTTP API contract

Use FastAPI only after the CLI and orchestrator tests pass.

### 13.1 Health

`GET /health/ready`

Successful response, HTTP 200:

```json
{
  "status": "ready",
  "version": "0.1.0",
  "runtime_mode": "deterministic",
  "governor_mode": "observe_only",
  "storage_mode": "memory",
  "fixture_count": 1
}
```

Return HTTP 503 if fixtures or the tool registry fail startup validation.

### 13.2 List demo orders

`GET /v1/fixtures/orders`

HTTP 200:

```json
{
  "items": [
    {
      "order_id": "ORD-8842",
      "cargo_class": "perishable",
      "shipment_weight_kg": 500,
      "currency": "INR"
    }
  ]
}
```

### 13.3 Start a run

`POST /v1/runs`

Request:

```json
{
  "order_id": "ORD-8842",
  "mode": "shadow"
}
```

Checkpoint 1 accepts only `shadow`. The field is present now so later
checkpoints can add `enforce` without redesigning the request.

Successful response, HTTP 201:

```json
{
  "trace_id": "TR-...",
  "order_id": "ORD-8842",
  "status": "completed",
  "selected_vehicle_id": "VEH-COLD-01",
  "selected_carrier_id": "CARRIER-COLD-01",
  "selected_amount_minor": 90000,
  "notification_id": "NOTIFY-...",
  "event_count": 27,
  "error": null
}
```

The exact final event count should be calculated by implementation tests rather
than manually assumed from this illustrative response.

Errors:

- HTTP 404: order ID does not exist.
- HTTP 422: invalid request or unsupported mode.
- HTTP 500: the run failed unexpectedly; a `trace_id` is returned when one was
  created so its events remain inspectable.

### 13.4 Get run summary

`GET /v1/runs/{trace_id}`

- HTTP 200 with `RunSummary`.
- HTTP 404 if the trace does not exist.

### 13.5 Get trace events

`GET /v1/traces/{trace_id}/events`

HTTP 200:

```json
{
  "trace_id": "TR-...",
  "items": [
    {
      "sequence": 1,
      "event_type": "run_started",
      "agent": null,
      "tool_name": null,
      "effect_class": null,
      "summary": "Started deterministic journey for ORD-8842",
      "details": {},
      "occurred_at": "2026-09-18T00:00:00Z"
    }
  ]
}
```

Events must be sorted by sequence. HTTP 404 is returned for an unknown trace.

### 13.6 Reset demo state

`POST /v1/demo/reset`

Successful response, HTTP 200:

```json
{
  "status": "reset",
  "removed_run_count": 2
}
```

This endpoint clears only in-memory synthetic runs. It never edits fixture
files.

### 13.7 Standard error body

All intentional API errors use:

```json
{
  "error": {
    "code": "TRACE_NOT_FOUND",
    "message": "Trace TR-unknown was not found."
  }
}
```

Do not expose stack traces, filesystem locations, environment values, or raw
exception representations in API responses.

## 14. Detailed implementation order

### Step 1 — Dependencies and verification commands

Add runtime dependencies:

- `fastapi`
- `uvicorn`

Add development dependencies:

- `pytest`
- `httpx` for FastAPI tests

Do not add Strands, AWS SDKs, Cedar bindings, databases, or frontend packages.

Verification:

```bash
python3 -m compileall -q apps packages fixtures
python3 -m pytest
```

### Step 2 — Domain enums, models, and errors

Implement and test the contracts in Section 6 before writing agents. Add typed
errors such as:

- `ManifestError`
- `FixtureError`
- `OrderNotFoundError`
- `UnknownToolError`
- `ToolOwnershipError`
- `TraceNotFoundError`
- `NoSuitableVehicleError`
- `NoSuitableCarrierError`

Completion gate: all models can be constructed and serialized without importing
FastAPI.

### Step 3 — Fixtures and loader

Create the JSON fixtures and loader. Test valid loading, missing IDs, duplicates,
missing fields, and isolation between repeated loads.

Completion gate: `ORD-8842` consistently loads as 500 kg with the same vehicle
and carrier candidates.

### Step 4 — In-memory trace store

Implement run creation, summary updates, ordered append, lookup, and reset.

Completion gate: two artificial traces can interleave appends without sharing
events or sequence counters.

### Step 5 — Tool definitions and registry

Register all seven tools, validate metadata, and test unknown and duplicate
tools.

Completion gate: startup validation reports exactly seven classified tools and
zero unregistered handlers.

### Step 6 — Deterministic mock tools

Implement mock reads/writes over fresh fixture data. Test success and invalid
input behavior.

Completion gate: the expected vehicle, quote, plan ID, selection ID, and outbox
ID are stable across clean runs.

### Step 7 — Observation-only governor

Wrap tool execution and append attempt, observation, success, or failure events.

Completion gate: a test tool call produces events in the expected order and a
wrong owner is rejected.

### Step 8 — Four agents

Implement one agent at a time in journey order. Unit-test each agent with a
small state and fake/real observer.

Completion gate: every agent calls only its registered tools and writes only its
documented state fields.

### Step 9 — Orchestrator and run service

Compose the agents, add lifecycle events and failure handling, then expose the
service methods.

Completion gate: the in-process benign journey passes twice from a clean store
and two traces have distinct state.

### Step 10 — CLI

Add `argparse` support:

```bash
python3 -m apps.runtime.run --order ORD-8842
python3 -m apps.runtime.run --order UNKNOWN
```

Completion gate: successful execution returns process exit code 0; invalid
orders and failed runs return non-zero exit codes with short safe messages.

### Step 11 — FastAPI boundary

Add the six endpoints in Section 13. Use dependency-provider functions to return
one application-scoped `RunService`. Do not instantiate business components in
each route.

Completion gate: API tests cover success, validation, unknown order, unknown
trace, and reset.

### Step 12 — End-to-end acceptance

Run the CLI and HTTP journeys, inspect the event order, and update documentation
with exact commands and example output.

Completion gate: every Definition of Done item in Section 17 passes.

## 15. Journey specification

### 15.1 Successful journey

1. Caller requests `ORD-8842`.
2. Run service validates that the order exists.
3. Orchestrator creates `TR-<uuid>` and a fresh state.
4. `RUN_STARTED` is appended.
5. Inventory Agent starts.
6. `get_order` crosses the governor and succeeds.
7. `check_inventory` crosses the governor and emits the 500 kg fact.
8. Inventory Agent stores the fact and completes.
9. Dispatch Agent starts.
10. It lists vehicles and selects `VEH-COLD-01`.
11. It creates a reversible dispatch plan using 500 kg.
12. Dispatch Agent stores the plan and completes.
13. Carrier Agent starts.
14. It lists quotes and selects `CARRIER-COLD-01` for INR 900.
15. It stores the reversible selection and completes.
16. Customer Communications Agent starts.
17. It writes a synthetic message to the in-memory outbox.
18. It stores the notification ID and completes.
19. Orchestrator marks the state `COMPLETED`.
20. `RUN_COMPLETED` is appended.
21. Caller receives the summary and can fetch every ordered event.

### 15.2 Expected state at completion

```text
status = COMPLETED
inventory_fact.shipment_weight_kg = 500
selected_vehicle.vehicle_id = VEH-COLD-01
selected_quote.carrier_id = CARRIER-COLD-01
selected_quote.amount_minor = 90000
notification_id is present
current_agent = None
error = None
```

### 15.3 Failure journey

If any agent fails:

- Later agents do not run.
- The already-recorded events remain accessible.
- A `TOOL_FAILED` event exists when a tool caused the failure.
- A final `RUN_FAILED` event exists.
- State status is `FAILED`.
- The error is concise and contains no secret or stack trace.

## 16. Test plan

### Unit tests

- Every fixture loads into the expected model.
- Missing/duplicate fixture data fails clearly.
- Registry rejects missing metadata, duplicate names, and unknown tools.
- Each tool returns stable output and validates its arguments.
- Tool ownership is checked.
- Trace sequences are monotonic.
- Unknown traces fail clearly.
- Each agent selects the expected fixture and updates expected state only.

### Integration tests

- All four agents execute in the required order.
- Every tool attempt has one governance observation and terminal success/failure.
- A benign order reaches `COMPLETED`.
- A missing vehicle fails before Carrier runs.
- A missing carrier fails before Communications runs.
- Two sequential traces have different IDs and independent state.
- Two concurrently started traces do not leak events or selected objects.
- Reset clears runs but does not alter fixtures.

### API tests

- Health returns ready and declares deterministic/observe-only/memory modes.
- Order listing returns `ORD-8842`.
- Starting a run returns HTTP 201 and a completed summary.
- Summary lookup returns the same result.
- Events are ordered and belong to the requested trace.
- Unknown order and trace statuses are correct.
- Invalid mode returns HTTP 422.
- Reset returns the number of removed runs.
- Errors follow the standard envelope.

### CLI end-to-end test

- Invoke the module in a subprocess.
- Assert exit code 0.
- Assert all four agent names appear in order.
- Assert 500 kg, `VEH-COLD-01`, `CARRIER-COLD-01`, INR 900, and `COMPLETED`
  appear.
- Assert an unknown order returns a non-zero exit code.

## 17. Definition of Done

Checkpoint 1 is complete only when all of the following are true:

- [x] `python3 -m apps.runtime.run --order ORD-8842` completes successfully.
- [x] Inventory, Dispatch, Carrier, and Customer Communications appear in order.
- [x] Every operational call uses the registered governor/tool path.
- [x] Every registered tool has an owner, effect class, description, and handler.
- [x] Startup finds no unknown or unclassified tools.
- [x] The authoritative 500 kg fact is carried into the dispatch plan.
- [x] `VEH-COLD-01` and `CARRIER-COLD-01` are selected deterministically.
- [x] A synthetic notification is written only to the local outbox.
- [x] Every run has a unique trace ID and monotonic event sequence.
- [x] Two traces prove state isolation.
- [x] A failed run preserves diagnostic events.
- [x] All six API endpoints behave according to Section 13.
- [x] The API returns real runtime data, not prewritten sample responses.
- [x] Unit, integration, API, and CLI end-to-end tests pass.
- [x] No external network, AWS, LLM, real PII, or real logistics integration is used.
- [x] README contains exact setup, CLI, API, and test commands.

## 18. Beginner-oriented work sessions

Implement in small sessions and stop at each green gate:

1. **Models:** learn dataclasses, enums, and type hints.
2. **Fixtures:** learn JSON loading and validation.
3. **Registry:** learn dictionaries of callables and custom exceptions.
4. **Tools:** learn small pure functions.
5. **State/events:** learn lists, sequence counters, and object ownership.
6. **Agents:** learn classes with one `run` method.
7. **Orchestration:** learn composition and exception handling.
8. **Testing:** learn pytest assertions and fixtures.
9. **API:** learn request/response models and route handlers.
10. **End-to-end:** run the system exactly as a user would.

Do not proceed to the next session while the current session's tests are red.

## 19. Suggested commit checkpoints

No commit is created automatically; these are recommended boundaries:

```text
chore: add checkpoint 1 dependencies and commands
feat: add domain models and deterministic fixtures
feat: add trace store and classified tool registry
feat: add deterministic logistics tools
feat: add observation-only governor
feat: add four-agent sequential workflow
test: cover checkpoint 1 runtime and trace isolation
feat: expose checkpoint 1 API
docs: document checkpoint 1 journey and commands
```

Each commit should pass the tests that exist at that stage.

## 20. Risks and controls

| Risk | Control |
|---|---|
| Too many unfamiliar frameworks | Core journey uses only standard Python; FastAPI comes last |
| Agents feel abstract | Each agent is one small class with one `run` method |
| Global state leaks between runs | Create `TrajectoryState` per trace and test isolation |
| API hides broken business logic | CLI and integration tests must pass before API work |
| Future enforcement requires a rewrite | All tools already cross `ObserverGovernor` |
| Demo output changes randomly | Fixtures and mock outputs are deterministic |
| Real-world side effects occur | No network calls; notification is an in-memory outbox record |
| Scope grows into later checkpoints | Enforce the exclusions in Section 3 |

## 21. Exit and handoff to Checkpoint 2

After Checkpoint 1 is green, Checkpoint 2 can replace observation-only decisions
with actual `ALLOW`, `GUIDE/BLOCK`, and `ESCALATE` behavior. It will introduce
the adversarial 50 kg handoff and uncertified carrier attempt while keeping the
same agents, tool registry, trace store interface, API shapes, and fixture IDs.

No Checkpoint 2 behavior should be implemented early merely because the fixture
already contains unsafe alternatives.
