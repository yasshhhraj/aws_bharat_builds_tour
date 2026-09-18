# Checkpoint 2 Implementation Plan — Governed Functional MVP

## 1. Objective

Extend the working Checkpoint 1 walking skeleton into the first credible
Manifest governance demonstration.

The same deterministic shipment must run in either `shadow` or `enforce`
mode. Every registered tool attempt must be converted into a typed policy
request, evaluated by a deterministic policy engine, recorded as a decision,
and either executed, guided to a corrected proposal, blocked, or paused for
approval.

The primary adversarial fixture must demonstrate three trajectory-level
controls:

1. Dispatch changes a sourced weight from 500 kg to 50 kg. Manifest guides it
   back to the authoritative 500 kg fact before a vehicle is assigned.
2. Carrier chooses the cheapest uncertified carrier for a perishable shipment.
   Manifest guides it to the certified cold-chain alternative.
3. A proposed INR 900 booking, combined with INR 3,650 of prior committed
   spend, exceeds the INR 4,000 mandate ceiling. Manifest prepares the action
   but pauses confirmation as `PENDING_APPROVAL`.

Checkpoint 2 remains deterministic and synthetic. An LLM is not required to
prove that the governance lifecycle works.

## 2. Relationship to Checkpoint 1

Checkpoint 1 is implemented and green. It already provides:

- four sequential plain-Python agent roles;
- seven registered and effect-classified tools;
- deterministic logistics fixtures and mock adapters;
- one isolated `TrajectoryState` per trace;
- an observation-only governor around all tool calls;
- a thread-safe in-memory trace store;
- CLI and FastAPI entry points; and
- 26 passing tests.

Checkpoint 2 must extend those contracts. It must not introduce a second
orchestrator, bypass the tool registry, or place policy logic directly inside
FastAPI route functions.

## 3. User-visible result

### 3.1 Shadow run

```bash
python3 -m apps.runtime.run \
  --order ORD-8842 \
  --mode shadow \
  --scenario adversarial
```

The run records that the weight, carrier, and spend actions would have been
interrupted, but permits the synthetic mock journey to continue:

```text
500 kg -> attempted 50 kg       WOULD_GUIDE
uncertified cheap carrier       WOULD_GUIDE
INR 3,650 + INR 900             WOULD_ESCALATE
synthetic booking               CONFIRMED (shadow only)
run status                      COMPLETED
```

### 3.2 Enforce run

```bash
python3 -m apps.runtime.run \
  --order ORD-8842 \
  --mode enforce \
  --scenario adversarial
```

The run must produce:

```text
Dispatch attempted 50 kg.
Manifest GUIDE: use WEIGHT-ORD-8842, whose value is 500 kg.
Dispatch replanned with 500 kg and a refrigerated vehicle.
Carrier attempted CARRIER-CHEAP-01.
Manifest GUIDE: perishable cargo requires cold-chain certification.
Carrier replanned to CARRIER-COLD-01 for INR 900.
The freight booking was prepared.
Manifest ESCALATE: projected spend is INR 4,550; ceiling is INR 4,000.
Run status: PENDING_APPROVAL
```

Approval resolution and resume are explicitly deferred to Checkpoint 3. This
checkpoint creates and exposes a correctly bound pending approval record; it
does not yet let an HTTP caller approve it.

## 4. Scope

### 4.1 Included

- `shadow` and `enforce` governance modes.
- `benign` and `adversarial` deterministic scenarios.
- A shipment mandate pinned to every trace.
- A typed policy request and decision contract.
- A policy-engine interface and a small Python reference implementation.
- Six baseline policy families.
- Stable reason codes and safe human-readable explanations.
- Decision aggregation and outcome precedence.
- Structured guide-back with bounded retries.
- Weight fact provenance, including a stable source hash.
- Cumulative committed/reserved/proposed spend calculation.
- Prepare-before-confirm for the synthetic freight booking.
- A pending approval record bound to the exact trace and prepared action.
- New decision and pending-approval read endpoints.
- CLI/API support for choosing mode and scenario.
- Unit, policy, integration, API, and end-to-end tests.
- A Cedar adapter spike and parity contract after the Python engine is green.

### 4.2 Explicitly excluded

- Human approval resolution and run resumption.
- Step Functions, Cognito, Lambda, API Gateway, or other AWS deployment.
- DynamoDB and hash-chained ledger verification.
- React dashboard.
- Bedrock or Strands integration.
- Real logistics, payment, carrier, notification, or PII handling.
- Policy CRUD or a policy-authoring UI.
- Route optimization, general planning, or unbounded agent loops.
- Quantity, price, ETA, and temperature provenance beyond fields needed for
  the primary scenario.

### 4.3 Scope guard

Checkpoint 2 is complete when the local deterministic hero flow passes. Cedar
integration may not delay the Python reference path. If Cedar cannot be
integrated in the timebox, retain the port, policy bundle, and parity tests,
label the active adapter `python_reference`, and do not claim Cedar is active.

## 5. Architecture

```text
CLI / FastAPI
     |
     v
RunService.start_run(order_id, mode, scenario)
     |
     v
ShipmentOrchestrator
     |
     +-- Inventory Agent
     +-- Dispatch Agent <---- structured guidance + retry limit
     +-- Carrier Agent  <---- structured guidance + retry limit
     +-- Customer Communications Agent
              |
              v
ManifestGovernor.execute_tool(proposal)
     |
     +--> ToolRegistry metadata and ownership
     +--> PolicyContextBuilder
     +--> PolicyEngine.evaluate(request, state)
     |       +-- ownership/mandate
     |       +-- cold chain
     |       +-- provenance
     |       +-- commitment budget
     |       +-- separation of duties
     |       +-- PII boundary
     |
     +--> DecisionAggregator
     |
     +--> shadow: record counterfactual, then execute mock
     |
     +--> enforce:
             ALLOW     -> execute mock
             GUIDE     -> do not execute; return guidance to agent
             BLOCK     -> do not execute; stop the run safely
             ESCALATE  -> do not confirm; create pending approval
     |
     v
MemoryTraceStore + DecisionStore + ApprovalStore
```

All policy evaluation happens before the mock handler is invoked. Reads are
governed just like writes, although most valid reads will be allowed.

## 6. Governance semantics

### 6.1 Modes

`GovernanceMode`:

- `SHADOW`: preserve the policy outcome as a counterfactual result, but apply
  `ALLOW` to the synthetic tool execution. The event and decision must clearly
  say that enforcement was not applied.
- `ENFORCE`: apply the actual policy outcome.

Store both values to avoid ambiguity:

```text
policy_outcome: ALLOW | GUIDE | BLOCK | ESCALATE
applied_outcome: ALLOW | GUIDE | BLOCK | ESCALATE
```

For example, a shadow-mode weight drift has `policy_outcome=GUIDE` and
`applied_outcome=ALLOW`.

### 6.2 Outcome meanings

`ALLOW`:

- The proposal may execute.
- The tool result updates trajectory state.

`GUIDE`:

- The exact proposal must not execute in enforce mode.
- The decision contains machine-readable constraints the same agent can use to
  make one corrected proposal.
- A guide is not an automatic mutation by the governor. The agent owns the
  corrected second attempt.

`BLOCK`:

- The proposal must not execute.
- The problem is not safely correctable by the current bounded agent step, or
  it violates a hard boundary.
- The run normally ends with status `BLOCKED`.

`ESCALATE`:

- The proposal must not execute in enforce mode.
- A `PendingApproval` is created for the exact prepared action.
- The run ends this checkpoint with status `PENDING_APPROVAL`.

### 6.3 Outcome precedence

More than one policy family may evaluate the same request. Aggregate signals
using this order:

```text
BLOCK > ESCALATE > GUIDE > ALLOW
```

All triggered signals are retained in `decision.reasons`; the highest-precedence
signal becomes the decision outcome. This prevents a weak allow from hiding a
hard violation.

### 6.4 Fail-closed rules

Return `BLOCK`, with a decision record, when any of these occur:

- unknown tool;
- missing tool owner or effect class;
- unsupported action/resource/context shape;
- missing mandate or policy version;
- policy-engine error or timeout;
- missing required provenance reference;
- malformed money or unit values; or
- an effect class absent from the mandate.

Unexpected programming failures still raise typed exceptions after a safe
failure event is recorded.

## 7. Domain-model changes

Continue using standard-library dataclasses and enums internally. FastAPI
Pydantic models remain API-only.

### 7.1 New enums

`GovernanceMode`:

```text
SHADOW
ENFORCE
```

`ScenarioName`:

```text
BENIGN
ADVERSARIAL
```

`DecisionOutcome`:

```text
ALLOW
GUIDE
BLOCK
ESCALATE
```

`CommitmentStatus`:

```text
PREPARED
PENDING_APPROVAL
APPROVED       # reserved for Checkpoint 3
REJECTED       # reserved for Checkpoint 3
CONFIRMED
CANCELLED      # reserved for Checkpoint 3
EXPIRED        # reserved for Checkpoint 3
```

Extend `RunStatus` with:

```text
BLOCKED
PENDING_APPROVAL
```

Extend `EventType` with:

```text
POLICY_DECIDED
TOOL_GUIDED
TOOL_BLOCKED
APPROVAL_REQUIRED
RUN_PAUSED
```

Keep `GOVERNANCE_OBSERVED` readable for old Checkpoint 1 traces, but do not
emit it for new Checkpoint 2 runs.

### 7.2 ShipmentMandate

```text
mandate_id: str
order_id: str
mode: GovernanceMode
currency: str
spend_ceiling_minor: int
approval_threshold_minor: int
cargo_class: str
allowed_effect_classes: frozenset[EffectClass]
policy_version: str
```

Validation:

- ceiling and threshold are non-negative integers;
- currencies are uppercase and match the order;
- order and mandate IDs are stable fixture values;
- allowed effect classes are non-empty;
- mode is copied from the run request, not trusted from a tool argument; and
- the mandate and policy version cannot change during a trace.

### 7.3 NumericFact

Replace the weight-only meaning of `InventoryFact` with a referenced numeric
fact while retaining inventory fields needed by the agent:

```text
fact_id: str
name: str                    # shipment_weight
value: int                   # 500
unit: str                    # kg
source_id: str               # WMS-SNAPSHOT-001
source_hash: str             # sha256 of canonical source fields
created_by_tool: str         # check_inventory
```

`TrajectoryState.facts` stores facts by `fact_id`. The existing
`inventory_fact` field may remain temporarily for compatibility, but all policy
checks must resolve facts through `facts`.

### 7.4 ToolProposal

```text
proposal_id: str
trace_id: str
agent: AgentName
tool_name: str
effect_class: EffectClass
arguments: dict[str, JSON-safe value]
attempt: int
```

The proposal ID is unique per attempt. Retrying after guidance creates a new
proposal ID and increments `attempt`.

### 7.5 PolicyRequest

```text
request_id: str
principal: AgentName
action: str
resource_type: str
resource_id: str
context: PolicyContext
```

`PolicyContext` contains only typed, authorization-relevant data:

```text
trace_id
mode
scenario
mandate_id
policy_version
cargo_class
tool_owner
effect_class
allowed_effect_classes
proposed arguments
referenced facts
selected vehicle/quote attributes
spend_committed_minor
spend_reserved_minor
proposed_amount_minor
currency
quote_issuer
prepared_by
approved_by
recipient/template metadata
```

Do not place raw Python objects, exception text, prompts, or arbitrary trace
history in the context.

### 7.6 PolicySignal and Decision

Each policy family returns zero or more `PolicySignal` values:

```text
family: str
policy_id: str
outcome: DecisionOutcome
reason_code: str
because: str
guidance: dict[str, JSON-safe value] | None
```

The aggregate `Decision` contains:

```text
decision_id: str
request_id: str
trace_id: str
proposal_id: str
policy_outcome: DecisionOutcome
applied_outcome: DecisionOutcome
enforced: bool
reason_code: str             # primary reason
because: str                 # primary safe explanation
reasons: tuple[PolicySignal, ...]
policy_version: str
engine_name: str
evaluation_ms: float
created_at: UTC datetime
```

Reasons come from a controlled catalogue. Never expose source code,
credentials, stack traces, or untrusted free-form text in `because`.

### 7.7 Commitment and approval models

`PreparedAction`:

```text
prepared_action_id: str
trace_id: str
tool_name: str               # confirm_freight_booking
resource_id: str             # quote or booking ID
amount_minor: int
currency: str
prepared_by: AgentName
arguments: redacted canonical dict
action_hash: str
state_hash: str
status: CommitmentStatus
expires_at: UTC datetime
```

`PendingApproval`:

```text
approval_id: str
trace_id: str
prepared_action_id: str
action_hash: str
state_hash: str
policy_version: str
reason_code: str
status: PENDING_APPROVAL
created_at: UTC datetime
expires_at: UTC datetime
```

Checkpoint 2 only creates and reads these records. Approval mutation belongs
to Checkpoint 3.

### 7.8 TrajectoryState additions

```text
mode: GovernanceMode
scenario: ScenarioName
mandate: ShipmentMandate
policy_version: str
facts: dict[str, NumericFact]
decisions: list[Decision]
spend_committed_minor: int
spend_reserved_minor: int
prepared_actions: dict[str, PreparedAction]
pending_approval_id: str | None
guide_attempts: dict[str, int]
effect_history: list[EffectRecord]
quoted_by: str | None
prepared_by: AgentName | None
approved_by: str | None
```

Money remains in minor units. Never use floats for spend calculations.

## 8. Tools and effect boundaries

### 8.1 Existing tools retained

| Tool | Owner | Effect | Checkpoint 2 purpose |
|---|---|---|---|
| `get_order` | Inventory | Read | Load synthetic order |
| `check_inventory` | Inventory | Read | Emit authoritative weight fact |
| `list_available_vehicles` | Dispatch | Read | Provide candidates, including unsafe option |
| `create_dispatch_plan` | Dispatch | Reversible write | Exercise provenance and refrigeration rules |
| `list_carrier_quotes` | Carrier | Read | Return cheap uncertified and compliant quotes |
| `select_carrier_quote` | Carrier | Reversible write | Exercise cold-chain guide-back |
| `write_tracking_outbox` | Communications | External disclosure | Exercise PII boundary |

### 8.2 New tools

`prepare_freight_booking`

```text
owner: Carrier
effect: reversible_write
input: order_id, quote_id, amount_minor, currency, idempotency_key
output: PreparedAction reference
```

It creates a reversible in-memory reservation. It does not make a financial
commitment and must not increment committed spend.

`confirm_freight_booking`

```text
owner: Carrier
effect: financial_commit
input: prepared_action_id, action_hash, idempotency_key
output: synthetic confirmation ID
```

It may run only after a matching prepared action exists. In enforce mode the
primary fixture escalates before this mock handler executes.

### 8.3 Tool argument changes

`create_dispatch_plan` must accept:

```text
order_id
vehicle_id
weight_value
weight_unit
weight_fact_id
idempotency_key
```

`write_tracking_outbox` should stop accepting an arbitrary message as its
authorization contract. Prefer:

```text
order_id
recipient_ref            # synthetic token, not a phone/email
template_id              # TRACKING_UPDATE_V1
template_variables       # allowlisted order_id and carrier_id
idempotency_key
```

The mock may render a synthetic display string after authorization.

### 8.4 Idempotency

- A second call with the same key and identical arguments returns the first
  mock result.
- Reusing a key with different arguments fails with a typed conflict.
- A guided retry uses a new idempotency key because it is a new proposal.
- `confirm_freight_booking` can produce at most one synthetic financial effect.

## 9. Agent functionality

Agents remain deterministic Python classes. Policy rules belong to the policy
engine; agents only propose, interpret structured guidance, and retry within a
small bound.

### 9.1 Inventory Agent

Responsibilities:

1. Load the order through `get_order`.
2. Load inventory through `check_inventory`.
3. Create/store the authoritative `NumericFact` for 500 kg.
4. Verify the fact source hash was returned and recorded.
5. Never select a vehicle, carrier, or booking.

Both scenarios behave identically at this stage.

### 9.2 Dispatch Agent

Benign scenario:

1. Use the authoritative 500 kg fact.
2. Choose `VEH-COLD-01`.
3. Propose `create_dispatch_plan` with the fact ID and exact value/unit.

Adversarial scenario:

1. First propose 50 kg with the authoritative fact ID and choose
   `VEH-SMALL-01`.
2. Receive `GUIDE` with constraints such as:

   ```json
   {
     "required_fact_id": "WEIGHT-ORD-8842",
     "required_value": 500,
     "required_unit": "kg",
     "required_vehicle": {
       "minimum_capacity_kg": 500,
       "refrigerated": true
     }
   }
   ```

3. Re-evaluate the already-listed vehicles.
4. Make exactly one corrected proposal using 500 kg and `VEH-COLD-01`.

The agent must not parse the human-readable `because` string. It uses only
structured guidance.

### 9.3 Carrier Agent

Benign scenario:

1. List quotes.
2. Choose the lowest-priced lane-supported cold-chain quote.

Adversarial scenario:

1. Sort by price and first propose `CARRIER-CHEAP-01`.
2. Receive `GUIDE` requiring cold-chain certification.
3. Choose `CARRIER-COLD-01` on the one permitted retry.

After selection in either scenario:

4. Call `prepare_freight_booking`.
5. Store the returned prepared action.
6. Propose `confirm_freight_booking`.
7. In the primary enforce path, receive `ESCALATE` and leave the run pending.
8. In shadow mode, record `WOULD_ESCALATE`; allow the synthetic confirmation
   and continue.

### 9.4 Customer Communications Agent

Preconditions:

- A confirmed synthetic booking exists; and
- the run is not pending approval or blocked.

Responsibilities:

1. Build the fixed `TRACKING_UPDATE_V1` template request.
2. Use only a synthetic `recipient_ref` and allowlisted variables.
3. Call `write_tracking_outbox` through the governor.

It does not run after an enforce-mode escalation in Checkpoint 2.

### 9.5 Retry and loop limits

- Maximum two proposals per agent/tool step: original plus one guided retry.
- Only `GUIDE` is retryable.
- `BLOCK` terminates the run.
- `ESCALATE` pauses the run.
- Repeated invalid guidance attempts terminate as `BLOCKED` with
  `GUIDE_RETRY_EXHAUSTED`.
- The existing global tool-call limit remains active.

## 10. Policy-engine design

### 10.1 Interface

```python
class PolicyEngine(Protocol):
    name: str
    policy_version: str

    def evaluate(
        self,
        request: PolicyRequest,
        state: TrajectoryState,
    ) -> tuple[PolicySignal, ...]: ...
```

`ManifestGovernor` owns aggregation, mode translation, event recording, and
tool execution. A policy engine only evaluates the request.

### 10.2 Beginner-safe implementation strategy

Build in two stages:

1. `PythonReferencePolicyEngine`: six small evaluators using explicit Python
   conditions. This makes every rule visible, testable, and debuggable.
2. `CedarPolicyEngine`: maps the same typed request into Cedar and must pass the
   same table-driven cases. Activate it only after differential tests show
   parity.

The Python engine is not prompt-based. It is deterministic authorization code.
It is an executable specification for the later Cedar policies.

### 10.3 Evaluation sequence

For every tool proposal:

1. Resolve tool metadata from the registry.
2. Build and validate `PolicyRequest`.
3. Run all applicable policy-family evaluators.
4. If no evaluator emits a signal, add a default `ALLOW` signal.
5. Aggregate signals with the documented precedence.
6. Translate to `applied_outcome` according to mode.
7. Record the complete `Decision` before executing any tool.
8. Execute, guide, block, or escalate.
9. Record the resulting event and update state only after a successful tool
   call.

### 10.4 Reason catalogue

Create a fixed mapping from reason code to safe explanation template. Initial
codes include:

```text
ALLOW_POLICY_CHECKS_PASSED
UNKNOWN_TOOL
TOOL_OWNER_MISMATCH
EFFECT_NOT_ALLOWED_BY_MANDATE
MISSING_POLICY_CONTEXT
COLD_CHAIN_VEHICLE_REQUIRED
COLD_CHAIN_CARRIER_REQUIRED
PROVENANCE_REFERENCE_MISSING
PROVENANCE_VALUE_MISMATCH
PROVENANCE_UNIT_MISMATCH
SPEND_WITHIN_CEILING
SPEND_APPROVAL_REQUIRED
PREPARED_ACTION_REQUIRED
PREPARED_ACTION_MISMATCH
SEPARATION_OF_DUTIES_VIOLATION
PII_FIELD_NOT_ALLOWED
DISCLOSURE_TEMPLATE_NOT_ALLOWED
GUIDE_RETRY_EXHAUSTED
POLICY_ENGINE_FAILURE
```

Dynamic values are inserted only after type validation.

## 11. Six policy families

### 11.1 Tool ownership and mandate boundary

**Purpose:** Ensure an agent can use only registered tools it owns and only
effect classes permitted by the trace's immutable shipment mandate.

**Applies to:** Every proposal.

**Required context:** principal, action/tool name, registered owner, effect
class, mandate ID, allowed effects, policy version.

**Rules:**

- The tool must exist in the registry.
- The principal must equal the registered owner.
- The effect class must be present and known.
- The mandate must allow the effect class.
- The request mandate/policy version must equal the trace-pinned versions.
- Physical and financial commits must reference a prepared action.

**Outcomes:**

- Valid request: no restrictive signal.
- Ownership/effect/version/preparation violation: `BLOCK`.

**Core tests:**

- Inventory may call `get_order`.
- Dispatch may not call `select_carrier_quote`.
- Unknown tool blocks.
- Missing effect class blocks.
- `financial_commit` absent from allowed effects blocks.
- Direct confirm without prepare blocks.

### 11.2 Cold-chain policy

**Purpose:** Prevent perishable cargo from using an unsuitable vehicle or
uncertified carrier.

**Applies to:** `create_dispatch_plan`, `select_carrier_quote`,
`prepare_freight_booking`, and `confirm_freight_booking`.

**Required context:** cargo class, vehicle capacity/refrigeration, quote lane
support, carrier cold-chain certification.

**Rules:**

- If cargo is not perishable, this family does not impose refrigeration.
- Perishable dispatch requires an available refrigerated vehicle.
- Vehicle capacity must be at least the authoritative shipment weight.
- Perishable carrier selection requires `cold_chain_certified=true`.
- The quote must support the destination lane.
- Missing certification or vehicle attributes fail closed.

**Outcomes:**

- Known unsuitable candidate with available correction: `GUIDE`.
- Missing safety metadata or no safe correction: `BLOCK`.

**Core tests:**

- Perishable plus refrigerated 1,000 kg vehicle allows.
- Perishable plus non-refrigerated 100 kg vehicle guides.
- Perishable plus uncertified carrier guides.
- Certified carrier on unsupported lane guides or blocks if no alternative.
- Non-perishable order does not require cold-chain certification.
- Missing `cold_chain_certified` blocks.

### 11.3 Numeric provenance policy

**Purpose:** Ensure commitment-relevant numbers come from a recorded source and
do not silently change during agent handoffs.

**Applies to:** `create_dispatch_plan` and later physical/financial effects
that carry shipment weight.

**Required context:** fact ID, proposed value/unit, stored fact value/unit,
source ID, source hash, creating tool.

**Rules:**

- A weight fact reference is mandatory.
- The fact must exist in the current trace.
- The fact must describe `shipment_weight`.
- Proposed unit must exactly match the fact unit.
- Proposed value must exactly match 500 kg for the primary fixture.
- The recomputed source hash must match the stored source hash.
- Facts from another trace or order are invalid.

**Outcomes:**

- Value/unit mismatch with a valid source: `GUIDE` with the required fact,
  value, and unit.
- Missing, foreign, or corrupted fact: `BLOCK`.

**Core tests:**

- 500 kg with the correct fact allows.
- 50 kg with the correct fact guides.
- 500 lb guides due to unit mismatch.
- Missing fact ID blocks.
- Unknown or cross-trace fact blocks.
- Altered source hash blocks.

### 11.4 Commitment-budget policy

**Purpose:** Evaluate cumulative exposure across the trajectory instead of
checking only the current booking.

**Applies to:** `confirm_freight_booking` and any future financial commit.

**Required context:** currency, committed spend, reserved spend excluding the
current prepared action, prepared action amount, ceiling, approval state.

**Formula:**

```text
projected_total = committed + other_reserved + proposed_amount
```

The current prepared action must not be counted once as reserved and a second
time as proposed.

**Rules:**

- Values must be non-negative integer minor units.
- Currency must match the mandate.
- `projected_total <= ceiling` is allowed.
- `projected_total > ceiling` requires approval.
- A later approval will be valid only for the exact action/state hashes; that
  resolution is implemented in Checkpoint 3.

**Outcomes:**

- At or below ceiling: allow signal with `SPEND_WITHIN_CEILING`.
- Above ceiling and no valid approval: `ESCALATE`.
- Malformed values, currency mismatch, or integer overflow condition: `BLOCK`.

**Core tests:**

- INR 3,000 + INR 900 allows.
- INR 3,100 + INR 900 (exactly INR 4,000) allows.
- INR 3,650 + INR 900 escalates with projected INR 4,550.
- Negative or floating-point amount blocks.
- Mismatched currency blocks.
- Existing reserved actions are included exactly once.

### 11.5 Separation-of-duties and commitment-state policy

**Purpose:** Prevent one actor from manufacturing a quote, approving its own
exception, or confirming an action that was not prepared and approved.

**Applies to:** quote selection, preparation, approval metadata, and
confirmation.

**Required context:** quote issuer, prepared-by actor, approved-by actor,
prepared action ID/hash/status, confirmation actor.

**Rules:**

- Quote issuer is the synthetic carrier adapter, not the selecting agent.
- The approver must be different from the preparer.
- A confirm must reference an existing exact prepared action.
- An above-ceiling confirm requires a non-expired approval for matching action,
  state, and policy hashes.
- A confirmed action cannot confirm again.
- An altered or stale prepared action cannot reuse an approval.

**Checkpoint 2 behavior:**

- Prepare is supported.
- Missing approval produces the commitment-budget `ESCALATE` result.
- Direct confirm, mismatched action, and duplicate confirm produce `BLOCK`.
- Positive approval/resume cases remain tests/specification until Checkpoint 3.

**Core tests:**

- Prepared action may proceed to policy evaluation.
- Confirm without prepare blocks.
- Changed amount after prepare blocks.
- Same preparer/approver blocks.
- Duplicate confirm blocks.
- Stale action/state hash blocks.

### 11.6 PII and external-disclosure boundary

**Purpose:** Ensure the communications tool receives only synthetic,
allowlisted data and cannot disclose arbitrary fields.

**Applies to:** `write_tracking_outbox` and any future external-disclosure
tool.

**Required context:** recipient reference type, template ID, template-variable
keys, effect class, mandate allowance.

**Rules:**

- `external_disclosure` must be permitted by the mandate.
- Recipient must be a synthetic token such as `DEMO-RECIPIENT-8842`.
- Template must be `TRACKING_UPDATE_V1`.
- Variables may include only `order_id` and `carrier_id`.
- Keys such as `phone`, `email`, `address`, `name`, `payment`, and arbitrary
  free-form message content are forbidden.
- Raw recipient/message fields are never written to trace details.

**Outcomes:**

- Fully allowlisted synthetic request: allow.
- Forbidden field, recipient, template, or effect: `BLOCK`.

**Core tests:**

- Synthetic recipient and allowlisted template allow.
- Phone/email/address field blocks.
- Arbitrary template blocks.
- Free-form message blocks.
- Event output contains only redacted disclosure metadata.

## 12. Governor lifecycle

Replace `ObserverGovernor` with `ManifestGovernor`. A temporary import alias may
keep Checkpoint 1 tests understandable during the transition.

`execute_tool` must perform:

1. Allocate a proposal and append `TOOL_ATTEMPTED` with redacted arguments.
2. Resolve registry metadata; unknown tools become a recorded block.
3. Build and validate the policy request.
4. Evaluate policies and measure policy latency.
5. Aggregate signals and translate shadow/enforce behavior.
6. Append `POLICY_DECIDED` before any mock effect.
7. Branch:
   - `ALLOW`: execute handler, append success/failure.
   - `GUIDE`: append `TOOL_GUIDED`, return a typed guidance result.
   - `BLOCK`: append `TOOL_BLOCKED`, return/raise a typed policy block.
   - `ESCALATE`: create approval record, append `APPROVAL_REQUIRED`, and return
     a typed escalation result.
8. Update trajectory state only from a successful result or explicit prepared
   action.

Define a single return envelope so agents do not catch loosely related
exceptions:

```text
GovernedToolResult:
  decision: Decision
  value: Any | None
  guidance: dict | None
  pending_approval: PendingApproval | None
```

Programmer/configuration failures may still raise typed exceptions. Expected
policy outcomes use the envelope.

## 13. Orchestrator changes

`ShipmentOrchestrator.run` becomes:

```text
run(order_id, mode, scenario) -> TrajectoryState
```

Lifecycle:

1. Validate order, mode, and scenario before creating effects.
2. Create a fresh trace and pin mandate/policy version.
3. Seed prior committed spend from the selected scenario fixture.
4. Run the four agents in fixed order.
5. If a decision blocks, set `BLOCKED`, append terminal event, stop.
6. If a decision escalates, set `PENDING_APPROVAL`, append `RUN_PAUSED`, stop.
7. Only invoke Communications after a confirmed booking.
8. Mark `COMPLETED` after all applicable agents finish.

An expected block or escalation is not `FAILED`. `FAILED` is reserved for
unexpected runtime/tool faults.

## 14. Fixtures and scenarios

Keep operational facts separate from adversarial behavior.

Add:

```text
fixtures/
  mandates/
    M-8842-1.json
  scenarios/
    ORD-8842-benign.json
    ORD-8842-adversarial.json
```

`ORD-8842-adversarial.json`:

```json
{
  "scenario": "adversarial",
  "prior_committed_minor": 365000,
  "dispatch": {
    "attempted_weight_kg": 50,
    "preferred_vehicle_id": "VEH-SMALL-01"
  },
  "carrier": {
    "preferred_quote_id": "QUOTE-CHEAP-01"
  }
}
```

The benign scenario uses the authoritative value and compliant candidates and
sets prior spend low enough that its INR 900 booking completes without
approval. This gives the policy suite a real non-attack path and prevents the
demo from treating every action as suspicious.

Fixture-loader validation must reject:

- unknown scenario names;
- scenarios referencing missing vehicles/quotes;
- negative/floating spend values;
- mandate/order currency mismatch;
- missing policy version;
- adversarial fact references that do not belong to the order; and
- mutable fixture sharing across traces.

## 15. HTTP API contract

Checkpoint 2 keeps runs synchronous. A response may finish as `completed`,
`blocked`, `failed`, or `pending_approval`.

### 15.1 Health

`GET /health/ready`

Add:

```json
{
  "status": "ready",
  "version": "0.4.0",
  "runtime_mode": "deterministic",
  "governor_mode": "policy_enforced",
  "policy_engine": "python_reference",
  "policy_version": "demo-v1",
  "storage_mode": "memory",
  "supported_modes": ["shadow", "enforce"],
  "supported_scenarios": ["benign", "adversarial"]
}
```

Readiness is false if fixtures, registry, reason catalogue, or the active
policy engine fail startup validation.

### 15.2 List fixtures

Retain `GET /v1/fixtures/orders`. Add available scenario names to each order or
add a top-level `scenarios` field. Do not expose raw adversarial implementation
instructions as executable client input.

### 15.3 Start run

`POST /v1/runs`

Request:

```json
{
  "order_id": "ORD-8842",
  "mode": "enforce",
  "scenario": "adversarial"
}
```

Response, HTTP 201:

```json
{
  "trace_id": "TR-...",
  "order_id": "ORD-8842",
  "mode": "enforce",
  "scenario": "adversarial",
  "status": "pending_approval",
  "selected_vehicle_id": "VEH-COLD-01",
  "selected_carrier_id": "CARRIER-COLD-01",
  "spend_committed_minor": 365000,
  "spend_reserved_minor": 90000,
  "projected_spend_minor": 455000,
  "spend_ceiling_minor": 400000,
  "pending_approval_id": "APR-...",
  "decision_count": 12,
  "event_count": 40,
  "error": null
}
```

The counts above are illustrative; tests should assert relationships and key
events rather than hard-code a fragile total unless the event contract is
deliberately frozen.

Errors:

- HTTP 404: unknown order.
- HTTP 422: unsupported mode/scenario or invalid request.
- HTTP 500: unexpected failure, with trace ID when available.

Policy `BLOCK` and `ESCALATE` are successful run-resource creation outcomes,
not HTTP errors.

### 15.4 Read run and events

Retain:

```text
GET /v1/runs/{trace_id}
GET /v1/traces/{trace_id}/events
```

The run summary adds mode, scenario, policy version, spend totals, decision
count, and pending approval ID.

Policy events expose safe reason codes and redacted context, never complete
fixture records or PII-like inputs.

### 15.5 Read decisions

Add:

```text
GET /v1/traces/{trace_id}/decisions
```

Response:

```json
{
  "trace_id": "TR-...",
  "items": [
    {
      "decision_id": "DEC-...",
      "proposal_id": "PROP-...",
      "agent": "dispatch",
      "tool_name": "create_dispatch_plan",
      "effect_class": "reversible_write",
      "policy_outcome": "guide",
      "applied_outcome": "guide",
      "enforced": true,
      "reason_code": "PROVENANCE_VALUE_MISMATCH",
      "because": "Attempted weight 50 kg differs from sourced weight 500 kg.",
      "policy_version": "demo-v1",
      "evaluation_ms": 0.4,
      "guidance": {
        "required_fact_id": "WEIGHT-ORD-8842",
        "required_value": 500,
        "required_unit": "kg"
      }
    }
  ]
}
```

### 15.6 Read pending approvals

Add:

```text
GET /v1/approvals
```

Optional query: `?trace_id=TR-...`.

Return only pending synthetic approval summaries. Do not return future task
tokens, secrets, or unredacted prepared arguments.

### 15.7 Reset

Retain `POST /v1/demo/reset`. It must clear runs, decisions, pending approvals,
prepared mock reservations, confirmations, notifications, and idempotency
records. It must never modify fixture files.

### 15.8 Deferred endpoints

Do not implement these in Checkpoint 2:

```text
POST /v1/approvals/{approval_id}        # Checkpoint 3
GET  /v1/traces/{trace_id}/verify      # Checkpoint 3
POST /v1/demo/tamper                    # Checkpoint 3, disposable traces only
```

## 16. CLI contract

Extend the CLI:

```text
--order ORD-8842
--mode shadow|enforce
--scenario benign|adversarial
--json                         # optional machine-readable output
```

Defaults should be safe and unsurprising:

```text
mode=enforce
scenario=benign
```

Exit codes:

- `0`: completed or intentionally pending approval;
- `2`: invalid CLI input or unknown fixture;
- `3`: policy-blocked run;
- `1`: unexpected runtime failure.

## 17. Storage changes

Extend the in-memory store or introduce small focused stores behind the same
dependency container:

```text
RunStore
DecisionStore
ApprovalStore
```

For this checkpoint they may share one locked in-memory implementation.

Required behavior:

- decisions are ordered and retrievable by trace;
- decision/proposal IDs are unique;
- pending approvals are retrievable by ID and trace;
- returned data is copied so callers cannot mutate stored state;
- reset clears every synthetic namespace;
- two simultaneous traces never share facts, decisions, spend, or approvals;
- a decision is stored before the corresponding mock effect executes.

Hash chaining is deferred; do not call this store immutable or tamper-proof.

## 18. Cedar adapter plan

Cedar produces binary authorization decisions; Manifest still owns the richer
`ALLOW`, `GUIDE`, `BLOCK`, and `ESCALATE` workflow semantics.

Use this mapping:

```text
principal -> Manifest::Agent::<agent-name>
action    -> Manifest::Action::<tool-name>
resource  -> Manifest::Shipment::<order-id>
context   -> validated PolicyContext record
```

Money and weight remain integers. Avoid optional, polymorphic context fields in
the Cedar schema; construct a stable typed record for each governed action.

Organize the bundle:

```text
policies/
  schema/
    manifest.cedarschema
  demo-v1/
    ownership.cedar
    cold_chain.cedar
    provenance.cedar
    spend.cedar
    separation_of_duties.cedar
    pii_boundary.cedar
    metadata.json
  tests/
    cases.json
```

`metadata.json` maps stable policy IDs to family, reason code, and default
Manifest outcome. For example, denial by the above-ceiling rule maps to
`ESCALATE`, while denial by the PII boundary maps to `BLOCK`.

Run the Cedar engine and Python engine against identical table-driven cases.
Activation requirements:

- all policy cases have the same outcome and reason code;
- unknown/missing context fails closed;
- active policy version appears in every decision;
- the health endpoint reports the actual adapter; and
- the four end-to-end modes/scenarios still pass.

Do not silently fall back from Cedar to Python during a run. Select the adapter
at startup and disclose it in health/run metadata.

## 19. Planned project structure

```text
project/
  apps/
    runtime/
      agents/
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
      governor.py
      context.py
      decisions.py
      reasons.py
    policy/
      protocol.py
      python_engine.py
      ownership.py
      cold_chain.py
      provenance.py
      spend.py
      separation.py
      pii_boundary.py
    cedar_adapter/
      engine.py
      mapper.py
    provenance/
      hashing.py
    commitments/
      service.py
      hashing.py
    ledger/
      memory_store.py
  policies/
    schema/
    demo-v1/
    tests/
  fixtures/
    mandates/
    scenarios/
  tests/
    unit/
    policy/
    integration/
    e2e/
  scripts/
    run_checkpoint_2.sh
```

## 20. Detailed implementation sequence

Each phase should end with green tests before moving to the next. This is the
recommended order for a developer new to agents and policy systems.

### Phase 0 — Protect the baseline

1. Run and record the existing 26-test baseline.
2. Tag or commit the known-good Checkpoint 1 state.
3. Add a new Checkpoint 2 test script without changing behavior.

**Gate:** Checkpoint 1 CLI/API still work.

### Phase 1 — Add contracts only

1. Add new enums and dataclasses.
2. Extend `TrajectoryState` and `RunSummary`.
3. Add mode/scenario/mandate fixtures and loader validation.
4. Add reason-code catalogue.
5. Update API schemas without changing the observer yet.

**Gate:** model and fixture tests pass; no tool behavior has changed.

### Phase 2 — Build the Python policy engine

Implement policy families in this order:

1. Ownership/mandate.
2. Provenance.
3. Cold chain.
4. Commitment budget.
5. Separation of duties.
6. PII boundary.

Use table-driven unit tests for each family. Do not connect agents until the
policy tests are green.

**Gate:** every family passes positive, negative, boundary, and missing-context
tests.

### Phase 3 — Replace the observer governor

1. Implement `PolicyContextBuilder`.
2. Implement decision aggregation and reason rendering.
3. Implement shadow-mode translation.
4. Implement `GovernedToolResult`.
5. Record decisions before effects.
6. Add block/escalate events and store queries.

**Gate:** direct governor tests cover all four outcomes; old benign flow still
completes.

### Phase 4 — Weight provenance and dispatch guide-back

1. Add fact hashing and trace-scoped fact storage.
2. Change dispatch tool arguments.
3. Add adversarial 50 kg first proposal.
4. Add structured guidance handling and one retry.
5. Verify unsafe mock dispatch never executes in enforce mode.

**Gate:** enforced adversarial dispatch corrects to 500 kg and the safe
vehicle; shadow dispatch records `WOULD_GUIDE` and proceeds with the attempted
mock path.

### Phase 5 — Carrier guide-back

1. Make the adversarial carrier choose the cheapest quote first.
2. Apply the cold-chain policy.
3. Handle structured carrier guidance.
4. Retry once with the certified quote.

**Gate:** `CARRIER-CHEAP-01` never reaches the selection mock in enforce mode;
`CARRIER-COLD-01` does.

### Phase 6 — Commitment preparation and spend escalation

1. Add prepare/confirm mock tools.
2. Add action/state hashes and idempotency checks.
3. Seed committed spend per scenario.
4. Evaluate cumulative spend at confirmation.
5. Create a pending approval on escalation.
6. Pause orchestration before Communications.

**Gate:** primary enforce run stops at INR 4,550 projected spend with an exact
pending approval; no confirmation or notification exists.

### Phase 7 — PII boundary and shadow completion

1. Convert communications to the fixed template contract.
2. Add forbidden-field tests.
3. Ensure shadow mode completes its synthetic journey while preserving
   counterfactual decisions.

**Gate:** allowed synthetic notification succeeds; raw contact fields block.

### Phase 8 — API and CLI exposure

1. Add mode/scenario parsing.
2. Extend summaries.
3. Add decision and approval read endpoints.
4. Add safe serialization and error mapping.
5. Verify reset clears all new state.

**Gate:** all four combinations work through API and CLI:

```text
benign + shadow
benign + enforce
adversarial + shadow
adversarial + enforce
```

### Phase 9 — Cedar parity

1. Probe the available Cedar Python integration.
2. Freeze the typed schema and policy-case JSON.
3. Implement the adapter and policy bundle.
4. Run differential tests.
5. Activate Cedar only if parity is green.

**Gate:** adapter is honestly disclosed and no test result depends on an
undocumented fallback.

### Phase 10 — Regression and checkpoint release

1. Run the complete suite twice from reset.
2. Run two simultaneous traces.
3. Inspect trace/decision redaction.
4. Capture the shadow and enforce CLI outputs.
5. Update README with actual engine status and limitations.

**Gate:** all acceptance criteria below pass.

## 21. Test plan

### 21.1 Unit tests

- Enum/model validation and serialization.
- Mandate immutability and currency validation.
- Fact canonicalization and stable source hashing.
- Reason-catalogue completeness.
- Decision precedence.
- Shadow/applied outcome translation.
- Idempotent prepare and confirm behavior.
- Action/state hash changes when protected fields change.
- Store isolation and reset.

### 21.2 Policy tests

Create table-driven cases with:

```text
case_id
family
request fixture
state fixture
expected outcome
expected reason code
expected guidance keys
```

Each family requires:

- valid positive case;
- obvious violation;
- exact boundary;
- missing required context;
- wrong type or unit;
- unrelated action where the family should not interfere.

### 21.3 Integration tests

- Governor records decision before tool success.
- Enforce guide does not invoke the unsafe mock.
- Shadow guide invokes the mock but records the counterfactual.
- Corrected attempt has a new proposal/decision.
- Guide retry limit blocks the third proposal.
- Enforce escalation does not invoke confirmation.
- Prepared action and approval hashes match.
- Communications is skipped while pending approval.
- Two traces have independent facts, spend, decisions, and approvals.
- Unknown tool and engine failure are recorded and fail closed.

### 21.4 API tests

- Health discloses engine and version.
- All mode/scenario combinations validate.
- Run summary contains spend and policy metadata.
- Decisions are ordered and redacted.
- Pending approval lookup supports trace filtering.
- Policy block is represented as run state, not an uncaught HTTP 500.
- Unknown trace returns the standard 404 error.
- Reset clears runs, decisions, approvals, and mock effects.

### 21.5 End-to-end tests

1. Benign enforce run completes and confirms once.
2. Adversarial shadow run completes with `WOULD_GUIDE` and
   `WOULD_ESCALATE` records.
3. Adversarial enforce run corrects weight and carrier, then pauses for
   approval.
4. Direct confirm without prepare is blocked.
5. Duplicate confirm has only one mock effect.
6. Raw PII-like communication fields are blocked.
7. Clean reset followed by the full sequence succeeds twice.

## 22. Acceptance criteria

Checkpoint 2 is done only when all statements are true:

- Every tool attempt produces exactly one stored decision.
- Every decision has outcome, applied outcome, reason code, safe `because`,
  policy version, engine name, trace ID, and timing.
- Unknown tools, effects, and required context fail closed.
- The 50 kg proposal never executes in enforce mode.
- The corrected 500 kg proposal uses the authoritative fact ID.
- The uncertified carrier never executes in enforce mode.
- The certified carrier is selected within one guided retry.
- INR 3,650 + INR 900 deterministically yields INR 4,550.
- INR 4,550 against INR 4,000 creates one pending approval.
- Confirm does not run before preparation or while approval is pending.
- Shadow mode records the same policy findings without enforcing them.
- Benign enforce mode completes without false intervention.
- Communications uses only the synthetic allowlisted template contract.
- Two concurrent traces do not leak policy or commitment state.
- CLI and API expose real stored decisions, not generated display text.
- All Checkpoint 1 regression tests and new Checkpoint 2 tests pass.
- README accurately states whether Python or Cedar is the active engine.

## 23. Definition of done by component

| Component | Done when |
|---|---|
| Domain | New contracts validate and serialize without FastAPI dependencies |
| Fixtures | Benign/adversarial inputs are deterministic and cross-references validate |
| Agents | Agents propose, consume structured guidance, and obey retry bounds |
| Registry/tools | Every tool has owner, effect, schema behavior, and idempotency |
| Governor | It records a decision before every effect and applies mode semantics |
| Policy engine | Six families pass positive/negative/boundary/missing-context tests |
| Provenance | 500 kg passes; 50 kg guides; missing/corrupt source blocks |
| Commitments | Prepare precedes confirm; cumulative spend escalates deterministically |
| Storage | Decisions and approvals are ordered, isolated, copied, and resettable |
| API | Runs, events, decisions, and approvals are inspectable with safe errors |
| CLI | Mode/scenario are selectable and terminal outcomes have stable exit codes |
| Cedar | Adapter parity is tested or fallback is explicitly disclosed |
| Quality | Full suite and two clean end-to-end resets pass |

## 24. Common implementation mistakes to avoid

- Do not put `if cargo_class == "perishable"` inside the agent as the security
  check. The agent may use it to choose candidates, but the policy engine must
  independently enforce it.
- Do not let the governor silently rewrite 50 to 500. Return guidance and make
  Dispatch issue a second proposal.
- Do not count the current prepared amount twice in projected spend.
- Do not treat `ESCALATE` as a failed run or an HTTP error.
- Do not execute the tool before persisting the decision.
- Do not use floating-point money.
- Do not trust mode, owner, effect, policy version, or prior spend from tool
  arguments; derive them from registered and trace-pinned state.
- Do not store raw messages, contact fields, complete fixture dumps, or
  exception representations in events.
- Do not permit unlimited guide/retry loops.
- Do not claim Cedar is active when the Python reference adapter is running.
- Do not implement approval mutation, hash-chain verification, or dashboard
  work before this checkpoint is green.

## 25. Recommended working cadence for a beginner

Treat each phase as a small program:

1. Read one existing file.
2. Add or change one contract.
3. Write one failing test that describes the desired behavior.
4. Implement only enough code to pass it.
5. Run the focused test.
6. Run the complete suite.
7. Commit the green state.

The first implementation target should be the ownership policy on one existing
`get_order` call. Once one real tool attempt produces a stored typed decision,
repeat that same pattern for the remaining policy families instead of building
all agents and policies at once.
