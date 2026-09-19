# Checkpoint 4 Implementation Plan — Tamper-Evident Ledger and Verification

## 1. Objective

Extend the working Checkpoint 3 application with a local, ordered,
tamper-evident hash-chain ledger.

Checkpoint 3 already records every important workflow transition as an ordered
`TraceEvent`. Checkpoint 4 must make those events independently verifiable by
linking each event to the hash of the previous event, preserving a separate
trusted head for each trace, and exposing a verification endpoint.

The primary journey becomes:

```text
start adversarial enforce run
    -> all Checkpoint 1-3 behavior remains unchanged
    -> each trace event is canonically serialized
    -> each event receives previous_hash and event_hash
    -> run pauses for approval with a valid ledger

approve exact pending action
    -> approval and resumed workflow append to the same chain
    -> booking confirms exactly once
    -> notification is written exactly once
    -> completed trace verifies from sequence 1 through the stored head

create a separate disposable run
    -> verify reports VALID
    -> demo-only tamper operation changes one stored event without rehashing
    -> verify reports INVALID and the first bad sequence
```

This checkpoint remains local, deterministic, beginner-readable, and usable
without AWS. DynamoDB is a later storage adapter; it must not be introduced
until the local hash-chain behavior and its tests are green.

## 2. Baseline and integration with Checkpoints 1-3

### 2.1 Verified starting state

At plan creation, the repository has:

```text
59 passed in 1.60s
```

The first Checkpoint 4 gate is to preserve all 59 tests. Existing tests may
gain additive assertions, but established workflow outcomes must not be changed
to make the ledger easier to implement.

### 2.2 Existing integration seam

The current application already sends trace events through one method:

```text
agents/orchestrator/governor/approval service
                    |
                    v
       MemoryTraceStore.append_event(...)
                    |
                    v
          TrajectoryState.events
```

Checkpoint 4 must keep this seam. Hash generation belongs in the ledger/store,
not in agents, policy rules, or API handlers. An agent should describe an event;
the ledger should decide its sequence, previous hash, and final event hash.

### 2.3 Capabilities that must remain intact

- Four deterministic agent roles and bounded sequential orchestration.
- Shadow and enforce modes.
- Benign and adversarial scenarios.
- Six deterministic policy families.
- Weight-provenance and cold-chain guide-back.
- Commitment-budget escalation.
- Prepare, approve/reject/expire, confirm/cancel state transitions.
- Exact-once mock confirmation, cancellation, and notification.
- Approval versioning, binding, authentication, and idempotency.
- Existing CLI commands and HTTP endpoints.
- Existing event order and event meanings.
- Trace isolation and approval concurrency behavior.

### 2.4 Required compatibility behavior

- Existing endpoint paths remain unchanged.
- Existing response fields retain their meanings.
- New event and health fields are additive.
- An approval resumes the original trace and extends its existing chain.
- Inventory and Dispatch do not rerun after approval.
- Shadow mode still executes counterfactual actions while recording decisions.
- A ledger failure must stop the affected transition; it must never silently
  switch to an unhashed event list.
- Demo tampering must never target a trace used for the main approval demo.

## 3. Scope

### 3.1 Included

- SHA-256 event hashing.
- Deterministic canonical JSON serialization for ledger payloads.
- A versioned ledger-event schema.
- Per-event `event_id`, `previous_hash`, `event_hash`, and optional
  `idempotency_key`.
- A per-trace ledger head stored separately from the event payloads.
- Atomic sequence/head/event updates under the existing in-memory lock.
- Idempotent event append when the caller provides an idempotency key.
- Conflict detection when a key is reused with a different event payload.
- Full-chain verification from the genesis hash to the stored head.
- Reporting the first invalid sequence and a controlled failure code.
- `GET /v1/traces/{trace_id}/verify`.
- Hash metadata in the existing trace-event API.
- A disabled-by-default, demo-only tamper operation.
- Verification before and after the Checkpoint 3 approval resume path.
- Tests for clean, modified, deleted, reordered, duplicated, and truncated
  in-memory chains.
- Documentation, manual smoke steps, and a Checkpoint 4 verification script.

### 3.2 Explicitly excluded

- DynamoDB, transactions, global tables, or LocalStack.
- S3, Object Lock, external signatures, or independent checkpoints.
- Claims that the ledger is immutable.
- Protection against an attacker who can rewrite both every event and the
  separately stored head.
- Distributed writers or multi-process locking.
- EventBridge, Lambda, API Gateway, Step Functions, or Amplify.
- React dashboard work.
- Cedar, Strands, or Bedrock integration.
- A general-purpose event editing API.
- Real operational or personal data.
- Backfilling old persisted traces; storage is in-memory and resets on restart.

### 3.3 Scope guard

Checkpoint 4 is complete when the current local journeys produce valid chains,
the approval continuation extends the same chain, the verifier identifies the
first changed sequence, and all previous tests still pass.

Do not begin DynamoDB or dashboard work while any ledger acceptance test is
red.

## 4. User-visible results

### 4.1 Clean run

After any successful run:

```http
GET /v1/traces/{trace_id}/verify
```

returns a result shaped like:

```json
{
  "trace_id": "TR-...",
  "valid": true,
  "checked_event_count": 42,
  "first_bad_sequence": null,
  "failure_code": null,
  "stored_head_sequence": 42,
  "stored_head_hash": "sha256:...",
  "computed_head_hash": "sha256:...",
  "algorithm": "sha256",
  "schema_version": "ledger-event-v1",
  "verified_at": "2026-09-19T00:00:00Z"
}
```

### 4.2 Pending approval and resume

The adversarial enforce trace must verify twice:

1. While the run is `PENDING_APPROVAL`.
2. After approval extends the same trace to `COMPLETED`.

The second verification must have a greater head sequence, and the first event
after the earlier head must reference the earlier head hash.

Expected business state after approval remains:

```text
run status                 COMPLETED
approval status            APPROVED
prepared action status     CONFIRMED
spend committed            INR 4,550
spend reserved             INR 0
booking confirmations      1
customer notifications     1
ledger valid               true
```

### 4.3 Disposable tamper demonstration

Use a separate completed trace:

1. Verify the trace and show `valid: true`.
2. Change the summary of one chosen event using the guarded demo operation.
3. Verify again.
4. Receive `valid: false` and the changed event's sequence as
   `first_bad_sequence`.
5. Reset the demo state after the demonstration.

The operation changes stored event content without recomputing hashes. It is
not a production administration feature.

## 5. Architecture

```text
ManifestGovernor / ShipmentOrchestrator / RunService
                         |
                         | append_event(description)
                         v
                 MemoryTraceStore
                         |
                         +--> assign sequence
                         +--> read current LedgerHead
                         +--> canonicalize event payload
                         +--> SHA-256(previous hash + event payload)
                         +--> append immutable TraceEvent
                         +--> replace LedgerHead atomically
                         |
                         +--> get_events(trace_id)
                         +--> verify_trace(trace_id)
                                      |
                                      v
                         recompute from genesis to head

FastAPI
  GET  /v1/traces/{trace_id}/events
  GET  /v1/traces/{trace_id}/verify
  POST /v1/demo/traces/{trace_id}/tamper   # disabled by default
```

The store remains the owner of ordering and hashing. The service owns use-case
coordination. The API only validates input and serializes results.

## 6. Integrity model and precise claims

### 6.1 What the prototype proves

For a retained trace and retained head, verification detects:

- modified event fields;
- a changed event hash;
- a changed previous hash;
- a missing event in the middle;
- reordered events;
- duplicated events;
- unexpected sequence numbers; and
- tail truncation when the separately stored head is left unchanged.

### 6.2 What the prototype does not prove

This is a tamper-evident hash chain, not immutable storage. A sufficiently
privileged attacker who can rewrite the entire event sequence and the stored
head can create a new internally consistent chain.

Use this wording in documentation and demonstrations:

> Manifest creates an ordered, tamper-evident hash chain and verifies retained
> events against a separately stored trace head.

Do not use:

```text
immutable ledger
blockchain
cryptographic proof that no administrator changed data
production audit certification
```

### 6.3 Trust boundary

The prototype trusts:

- the running Python process;
- the hash implementation;
- the canonicalization implementation;
- the per-trace stored head; and
- the absence of direct internal store mutation except during the labelled
  tamper demonstration and tests.

Future independent signatures or Object-Locked checkpoints are outside this
checkpoint.

## 7. Domain-model changes

### 7.1 `TraceEvent`

Extend `TraceEvent` additively:

```python
@dataclass(frozen=True, slots=True)
class TraceEvent:
    event_id: str
    trace_id: str
    sequence: int
    event_type: EventType
    summary: str
    details: dict[str, Any]
    agent: AgentName | None
    tool_name: str | None
    effect_class: EffectClass | None
    occurred_at: datetime
    schema_version: str
    previous_hash: str
    event_hash: str
    idempotency_key: str | None = None
```

Rules:

- `event_id` is unique and generated by the ledger.
- `sequence` begins at 1 for each trace.
- `schema_version` is exactly `ledger-event-v1` for this checkpoint.
- `previous_hash` is the genesis hash for sequence 1.
- `event_hash` is calculated only by the ledger.
- `idempotency_key` is safe metadata, not a secret.
- The dataclass remains frozen so normal code cannot mutate stored events.

Field ordering in the dataclass does not define hash ordering. Canonical JSON
does that.

### 7.2 `LedgerHead`

Add:

```python
@dataclass(frozen=True, slots=True)
class LedgerHead:
    trace_id: str
    sequence: int
    event_count: int
    event_hash: str
    schema_version: str
    updated_at: datetime
```

New traces begin with an internal head:

```text
sequence       0
event_count    0
event_hash     sha256:0000000000000000000000000000000000000000000000000000000000000000
```

The genesis head is internal and is not returned as a normal event.

### 7.3 `VerificationResult`

Add:

```python
@dataclass(frozen=True, slots=True)
class VerificationResult:
    trace_id: str
    valid: bool
    checked_event_count: int
    first_bad_sequence: int | None
    failure_code: str | None
    stored_head_sequence: int
    stored_head_hash: str
    computed_head_hash: str
    algorithm: str
    schema_version: str
    verified_at: datetime
```

Controlled `failure_code` values:

```text
SEQUENCE_MISMATCH
TRACE_ID_MISMATCH
SCHEMA_VERSION_MISMATCH
PREVIOUS_HASH_MISMATCH
EVENT_HASH_MISMATCH
EVENT_COUNT_MISMATCH
HEAD_SEQUENCE_MISMATCH
HEAD_HASH_MISMATCH
```

Verification failures are results, not exceptions. Missing traces and invalid
API requests remain exceptions.

### 7.4 `TamperResult`

Add a small demo-only result:

```python
@dataclass(frozen=True, slots=True)
class TamperResult:
    trace_id: str
    sequence: int
    field: str
    status: str = "tampered_for_demo"
```

It must not expose previous sensitive content.

## 8. Canonical serialization and hashing

### 8.1 Constants

Define in `packages/ledger/canonical.py`:

```python
HASH_ALGORITHM = "sha256"
HASH_PREFIX = "sha256:"
LEDGER_SCHEMA_VERSION = "ledger-event-v1"
GENESIS_HASH = "sha256:" + ("0" * 64)
```

### 8.2 Canonical payload

The hash input includes every field that gives the event meaning except
`event_hash` itself:

```json
{
  "agent": "carrier",
  "details": {},
  "effect_class": "financial_commit",
  "event_id": "EVT-...",
  "event_type": "policy_decided",
  "idempotency_key": null,
  "occurred_at": "2026-09-19T00:00:00.000000Z",
  "previous_hash": "sha256:...",
  "schema_version": "ledger-event-v1",
  "sequence": 17,
  "summary": "escalate: Projected spend exceeds the ceiling.",
  "tool_name": "confirm_freight_booking",
  "trace_id": "TR-..."
}
```

Hashing procedure:

```python
primitive = event_payload_without_event_hash(...)
canonical = json.dumps(
    primitive,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
    allow_nan=False,
)
event_hash = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

### 8.3 Normalization rules

- Enums become their `.value` strings.
- Datetimes are converted to UTC and end in `Z`.
- Dictionary keys become strings and are sorted by JSON serialization.
- Lists retain order.
- Integers remain integers.
- Booleans remain booleans and must never be treated as integers.
- `None` becomes JSON `null`.
- NaN and infinity are rejected.
- Sets are not accepted in ledger details; callers must provide an ordered
  representation.
- Secrets, raw PII, and approval authentication headers never enter the
  payload.

This is a deliberately small Python canonicalization contract, not a claim of
RFC 8785 compliance. A fixed-vector test pins its behavior before a future
non-Python or DynamoDB implementation is added.

### 8.4 Fixed-vector test

Commit one fixed event input and expected hash. This protects against an
accidental serializer change that would invalidate every existing chain.

Any future canonicalization change requires a new `schema_version`; do not
silently change `ledger-event-v1`.

## 9. Store design

### 9.1 Internal structures

Extend `MemoryTraceStore` with:

```python
self._heads: dict[str, LedgerHead]
self._event_replays: dict[tuple[str, str], tuple[str, TraceEvent]]
```

The second tuple value contains:

```text
payload fingerprint
previously appended event
```

All run, head, event, approval, and replay maps continue to use the existing
`RLock`.

### 9.2 Run creation

`create_run(state)` must atomically:

1. Reject an existing trace ID.
2. Require `state.events` to be empty.
3. Require `state.next_sequence == 1`.
4. Store the live state.
5. Create the sequence-0 genesis `LedgerHead`.

If head initialization fails, the run must not be stored.

### 9.3 Append contract

Change the method additively:

```python
append_event(
    state,
    event_type,
    summary,
    *,
    details=None,
    agent=None,
    tool_name=None,
    effect_class=None,
    idempotency_key=None,
) -> TraceEvent
```

Append steps under one lock:

1. Confirm the trace exists.
2. Confirm `state` is the store's live state object.
3. Read the current `LedgerHead`.
4. Confirm `state.next_sequence == head.sequence + 1`.
5. Build a safe unhashed event description.
6. If `idempotency_key` exists, calculate its payload fingerprint.
7. If the key was seen with the same fingerprint, return a deep copy of the
   earlier event without incrementing sequence or count.
8. If the key was seen with a different fingerprint, raise
   `LedgerIdempotencyConflictError`.
9. Generate `event_id` and one `occurred_at` value.
10. Set `previous_hash = head.event_hash`.
11. Calculate `event_hash` from the complete canonical payload.
12. Append the frozen event.
13. Increment `state.next_sequence`.
14. Replace the `LedgerHead`.
15. Record the replay entry when a key was provided.
16. Return a defensive copy.

No `await`, tool invocation, callback, or external operation may occur while
the store lock is held.

### 9.4 Event idempotency use

An omitted idempotency key means “this call is a new event.” That preserves the
current call sites during the first integration pass.

Use explicit stable keys for transitions where replay is meaningful:

```text
run:{trace_id}:started
approval:{approval_id}:required
approval:{approval_id}:approved:v{version}
approval:{approval_id}:rejected:v{version}
approval:{approval_id}:expired:v{version}
run:{trace_id}:resumed:{approval_id}
run:{trace_id}:completed
run:{trace_id}:cancelled:{reason_code}
```

Tool attempt/decision/outcome keys can be based on the generated
`proposal_id`:

```text
proposal:{proposal_id}:attempted
proposal:{proposal_id}:decision
proposal:{proposal_id}:guided
proposal:{proposal_id}:blocked
proposal:{proposal_id}:succeeded
proposal:{proposal_id}:failed
```

Do not use list length, current time, or a mutable state hash as an idempotency
key.

### 9.5 Read behavior

- `get_events()` returns defensive copies in ascending sequence order.
- `get_head()` returns a defensive copy.
- Normal read methods never repair or recalculate stored hashes.
- Verification recalculates hashes but does not mutate the trace.

### 9.6 Reset behavior

`reset()` must clear:

- runs;
- approvals;
- approval replay fingerprints;
- heads; and
- event replay fingerprints.

Its existing returned run count remains unchanged.

## 10. Verification algorithm

Implement the verifier as a pure service in
`packages/ledger/verifier.py`. It receives a trace ID, the retained events, and
the retained head.

Pseudo-code:

```python
expected_sequence = 1
expected_previous_hash = GENESIS_HASH
computed_head_hash = GENESIS_HASH

for event in events:
    if event.sequence != expected_sequence:
        fail("SEQUENCE_MISMATCH", expected_sequence)
    if event.trace_id != requested_trace_id:
        fail("TRACE_ID_MISMATCH", event.sequence)
    if event.schema_version != LEDGER_SCHEMA_VERSION:
        fail("SCHEMA_VERSION_MISMATCH", event.sequence)
    if event.previous_hash != expected_previous_hash:
        fail("PREVIOUS_HASH_MISMATCH", event.sequence)

    recomputed = hash_event(event without event_hash)
    if event.event_hash != recomputed:
        fail("EVENT_HASH_MISMATCH", event.sequence)

    computed_head_hash = recomputed
    expected_previous_hash = recomputed
    expected_sequence += 1

if len(events) != head.event_count:
    fail("EVENT_COUNT_MISMATCH", expected_sequence)
if head.sequence != len(events):
    fail("HEAD_SEQUENCE_MISMATCH", expected_sequence)
if head.event_hash != computed_head_hash:
    fail("HEAD_HASH_MISMATCH", head.sequence)

return valid result
```

### 10.1 Failure priority

For predictable tests, use this priority while scanning an event:

1. sequence;
2. trace ID;
3. schema version;
4. previous hash;
5. event hash.

After scanning, check count, head sequence, then head hash.

### 10.2 Meaning of `checked_event_count`

- On success: number of all events.
- On failure: number of events fully verified before the bad event.

### 10.3 Verification must be read-only

The verifier must never:

- fix hashes;
- rewrite sequence numbers;
- replace the stored head;
- remove invalid events; or
- append a “verification event” to the chain being verified.

Appending a verification result to that same chain would change the head and
make repeated verification confusing. Verification can be logged separately
later if needed.

## 11. Integration with the existing governor and approval flow

### 11.1 Governor decisions

Keep this critical order:

```text
TOOL_ATTEMPTED event
policy evaluation
Decision stored
POLICY_DECIDED event successfully appended
only then apply GUIDE/BLOCK/ESCALATE or execute the mock tool
```

The `POLICY_DECIDED` event should add these currently available fields so the
chain contains a useful decision receipt:

```text
decision_id
request_id
proposal_id
policy_outcome
applied_outcome
enforced
reason_code
because
guidance
policy_version
engine_name
evaluation_ms
policy signal IDs and families
```

Do not include unredacted policy input.

### 11.2 Tool effects

The existing mock tools remain idempotent. Preserve the rule that the policy
decision event must append successfully before a physical, financial, or
disclosure mock executes.

`TOOL_SUCCEEDED` continues to contain only the existing redacted result. Do not
add raw messages, contact values, secrets, or headers to improve the ledger.

### 11.3 Approval creation

The `APPROVAL_REQUIRED` event should include:

```text
approval_id
prepared_action_id
action_hash
state_hash
policy_version
reason_code
```

This binds the ledger receipt to the exact prepared action without exposing
approval authentication material.

### 11.4 Approval resolution

For approve/reject/expire:

- append the control-plane transition to the existing chain;
- use a stable idempotency key based on approval ID and version;
- never record `DEMO_APPROVER_SECRET`;
- retain the approver label because it is synthetic and already part of the
  Checkpoint 3 contract;
- do not place the free-form approval comment in the ledger; and
- continue the existing exact-once effect behavior.

### 11.5 Approval resume chain continuity

An integration test must capture the pending head, approve the action, and
assert:

```text
new head sequence > pending head sequence
first resumed event.previous_hash == pending head.event_hash
all pre-approval event IDs and hashes are unchanged
full chain verification == valid
```

### 11.6 Failure behavior

If hashing or append fails before a tool effect, propagate a controlled
`LedgerAppendError` and do not execute the tool.

If a ledger append unexpectedly fails after a mock effect, the run becomes
`FAILED`; the existing tool idempotency key allows safe diagnosis/retry. Do not
pretend the ledger and effect are atomic in an in-memory prototype.

This limitation must be noted in the README. DynamoDB transactions and an
outbox pattern are later work.

## 12. API contract

### 12.1 Existing event endpoint

Keep:

```http
GET /v1/traces/{trace_id}/events
```

Add these fields to each event response:

```json
{
  "event_id": "EVT-...",
  "schema_version": "ledger-event-v1",
  "previous_hash": "sha256:...",
  "event_hash": "sha256:...",
  "idempotency_key": null
}
```

### 12.2 Verify endpoint

Add:

```http
GET /v1/traces/{trace_id}/verify
```

Behavior:

- `200` with `valid: true` for a clean chain.
- `200` with `valid: false` for a retained but invalid chain.
- `404 TRACE_NOT_FOUND` for an unknown trace.
- Never mutate or repair the trace.

The invalid-chain case is a successful verification request, so it is not an
HTTP 500 or 409.

### 12.3 Demo-only tamper endpoint

Add only if all verification tests are already green:

```http
POST /v1/demo/traces/{trace_id}/tamper
```

Request:

```json
{
  "sequence": 5,
  "replacement_summary": "Altered only for the disposable demo trace."
}
```

Controls:

- `ENABLE_DEMO_TAMPER=true` must be present.
- `DEMO_TAMPER_SECRET` must be configured.
- Request requires `X-Demo-Tamper-Secret`.
- The trace must be terminal (`COMPLETED`, `CANCELLED`, or `BLOCKED`).
- Sequence must exist.
- Only `summary` may be replaced.
- Hashes and head must not be recomputed.
- Response must not contain the original summary.
- Endpoint documentation labels it disposable and demo-only.

When disabled, return `404` so it is not advertised as an available mutation
surface. If implementing conditional OpenAPI exclusion is distracting, omit
the HTTP endpoint and keep tampering in a local demo script. The service and
verifier are the MUST items; the HTTP tamper trigger is secondary.

### 12.4 Health response additions

Update `/health/ready` additively:

```json
{
  "version": "0.6.0",
  "storage_mode": "memory_hash_chain",
  "ledger_algorithm": "sha256",
  "ledger_schema_version": "ledger-event-v1",
  "verify_ready": true,
  "demo_tamper_enabled": false
}
```

Do not return configured secret values.

## 13. Error model

Add controlled exceptions:

```python
class LedgerError(ManifestError):
    code = "LEDGER_ERROR"

class LedgerAppendError(LedgerError):
    code = "LEDGER_APPEND_ERROR"

class LedgerIdempotencyConflictError(LedgerError):
    code = "LEDGER_IDEMPOTENCY_CONFLICT"

class LedgerTamperDisabledError(LedgerError):
    code = "LEDGER_TAMPER_DISABLED"

class LedgerTamperUnauthorizedError(LedgerError):
    code = "LEDGER_TAMPER_UNAUTHORIZED"
```

Recommended HTTP mapping:

```text
TRACE_NOT_FOUND                  404
LEDGER_TAMPER_DISABLED           404
LEDGER_TAMPER_UNAUTHORIZED       401
LEDGER_IDEMPOTENCY_CONFLICT      409
invalid tamper sequence          422
LEDGER_APPEND_ERROR              500
```

Do not throw `LedgerError` merely because verification found tampering;
verification returns `valid: false`.

## 14. File-by-file implementation map

### 14.1 New files

`packages/ledger/canonical.py`

- constants;
- primitive normalization;
- canonical JSON generation;
- event payload construction;
- SHA-256 calculation;
- payload fingerprint calculation.

`packages/ledger/verifier.py`

- pure chain verification;
- failure priority;
- `VerificationResult` construction.

`tests/unit/test_ledger_canonical.py`

- canonical ordering;
- fixed hash vector;
- timestamp/enum/nested payload behavior;
- NaN rejection.

`tests/unit/test_hash_chain_store.py`

- genesis and multi-event append;
- head updates;
- idempotent replay and conflict;
- trace isolation and reset.

`tests/integration/test_checkpoint_4_verification.py`

- all major Checkpoint 1-3 journeys verify;
- pending and resumed approval continuity;
- reject and expiry continuity;
- tamper cases.

`tests/e2e/test_checkpoint_4_api.py`

- clean verification response;
- invalid verification response;
- unknown trace;
- additive event fields;
- guarded tamper behavior if the HTTP trigger is implemented.

`scripts/run_checkpoint_4.sh`

- full test suite;
- benign enforce run;
- adversarial shadow run;
- adversarial enforce approve run;
- adversarial enforce reject run;
- verification/tamper smoke.

### 14.2 Files to modify

`packages/domain/models.py`

- extend `TraceEvent`;
- add `LedgerHead`, `VerificationResult`, and `TamperResult`.

`packages/domain/errors.py`

- add controlled ledger errors.

`packages/ledger/memory_store.py`

- initialize heads;
- hash all appended events;
- implement event replay handling;
- expose `get_head()` and `verify_trace()`;
- provide a narrowly scoped internal demo-tamper method;
- clear ledger maps on reset.

`packages/ledger/__init__.py`

- export the constants and ledger classes required by application code.

`packages/governor/governor.py`

- add stable proposal event keys;
- expand redacted `POLICY_DECIDED` details;
- expand approval-binding receipt fields;
- preserve pre-effect append ordering.

`apps/runtime/orchestrator.py`

- add stable run/approval lifecycle event keys;
- make no agent-flow changes.

`apps/runtime/service.py`

- add `verify_trace(trace_id)`;
- add guarded demo tamper coordination if selected;
- keep existing approval locking behavior.

`apps/api/schemas.py`

- extend `EventResponse`;
- add `VerificationResponse`;
- optionally add tamper request/response schemas;
- extend `HealthResponse`.

`apps/api/dependencies.py`

- optionally add constant-time demo-tamper secret validation;
- never reuse or expose the approval secret as a ledger secret.

`apps/api/main.py`

- update title/version;
- add verify route;
- optionally add guarded tamper route;
- map new errors;
- add health fields.

`README.md`

- update current checkpoint;
- explain the precise integrity claim;
- document verification commands and disposable tamper steps;
- retain the real/simulated/deferred table.

`.env.example`

- add names only: `ENABLE_DEMO_TAMPER` and `DEMO_TAMPER_SECRET`.

## 15. Detailed implementation order and gates

### Phase 0 — Freeze and verify Checkpoint 3

Actions:

1. Run `python3 -m pytest -q`.
2. Run `./scripts/run_checkpoint_3.sh`.
3. Record the current 59-test baseline.
4. Do not change policies, fixtures, agent choices, or approval semantics.

Gate:

```text
59 existing tests pass
all Checkpoint 3 CLI journeys pass
working tree changes are understood before ledger edits begin
```

### Phase 1 — Build pure canonical hashing

Actions:

1. Add constants and canonical serializer.
2. Add hash calculation for an unhashed event payload.
3. Add a fixed-vector test.
4. Test nested dictionary key-order independence.
5. Test that changing any included field changes the hash.
6. Reject unsupported/non-finite values.

Gate:

```text
pure ledger unit tests pass
no store or workflow code has changed yet
fixed event always produces the pinned hash
```

### Phase 2 — Add ledger domain models

Actions:

1. Extend `TraceEvent` additively.
2. Add `LedgerHead` and `VerificationResult`.
3. Update API schemas only enough for imports to remain green.
4. Keep serialization compatible through `to_primitive()`.

Gate:

```text
domain tests pass
event responses can represent all new fields
no business-state output has changed
```

### Phase 3 — Integrate hashing into `MemoryTraceStore`

Actions:

1. Initialize a genesis head during `create_run()`.
2. Make `append_event()` assign and hash all new fields.
3. Atomically update event list, sequence, and head under the lock.
4. Add `get_head()`.
5. Update reset.
6. Run the entire old test suite.

Gate:

```text
all existing tests pass
every event has a valid previous_hash/event_hash pair
the first event references GENESIS_HASH
each trace owns a separate head
```

### Phase 4 — Add idempotent ledger appends

Actions:

1. Add optional event idempotency keys.
2. Return the original event for an identical replay.
3. Reject a conflicting replay.
4. Add stable keys to critical lifecycle events.
5. Confirm replay does not increment sequence or update the head.

Gate:

```text
same key + same payload => same event, unchanged head
same key + changed payload => controlled conflict
approval and effect exact-once tests remain green
```

### Phase 5 — Build the read-only verifier

Actions:

1. Implement the pure verifier.
2. Expose `MemoryTraceStore.verify_trace()`.
3. Test clean chains.
4. Use test-only mutation helpers to test each failure class.
5. Confirm verification never changes stored data.

Gate:

```text
clean trace reports valid
changed event reports its sequence
middle deletion and reorder are detected
tail deletion is detected against the retained head
repeated verification returns the same result except verified_at
```

### Phase 6 — Verify Checkpoint 3 integration

Actions:

1. Verify benign enforce and adversarial shadow runs.
2. Start adversarial enforce and verify while pending.
3. Record the pending head.
4. Approve and resume.
5. Assert chain continuity and verify the completed chain.
6. Repeat for rejection and expiry.
7. Re-run approval concurrency and replay tests.

Gate:

```text
all business results exactly match Checkpoint 3
approval extends rather than replaces the chain
no event before the pending head changes
all terminal traces verify
```

### Phase 7 — Expose the API

Actions:

1. Add event hash fields to `EventResponse`.
2. Add the verify response schema.
3. Add `GET /v1/traces/{trace_id}/verify`.
4. Update health metadata and application version.
5. Add API tests for valid, invalid, and unknown traces.

Gate:

```text
clean API verification returns 200/valid
tampered retained trace returns 200/invalid
unknown trace returns 404
all previous API payloads remain compatible
```

### Phase 8 — Add the guarded demo tamper path

Actions:

1. Implement the smallest internal summary-replacement method.
2. Require a terminal trace.
3. Do not recompute the event hash or head.
4. Add configuration and secret protection if exposed over HTTP.
5. Test disabled, unauthorized, invalid-sequence, and success paths.

Gate:

```text
tamper path is disabled by default
only a disposable terminal trace can be changed
one changed summary makes verification fail at that sequence
reset removes the disposable trace
```

### Phase 9 — Documentation and checkpoint release

Actions:

1. Add the verification script.
2. Update README commands and precise claims.
3. Run the complete suite twice.
4. Run one manual clean/tampered demo.
5. Review output for secrets and raw PII.

Gate:

```text
Checkpoint 4 acceptance criteria all pass
README commands work from a clean shell
no immutable/blockchain claim appears
```

## 16. Test plan

### 16.1 Canonicalization unit tests

- Same semantic dictionary with different insertion order has the same hash.
- Nested dictionary ordering does not change the hash.
- List order does change the hash.
- Summary, details, trace ID, sequence, timestamp, or previous hash changes the
  hash.
- Enum and UTC datetime serialization is stable.
- NaN and infinity are rejected.
- Fixed-vector hash equals the committed value.

### 16.2 Store unit tests

- New trace has a sequence-0 genesis head.
- First event has sequence 1 and the genesis previous hash.
- Second event references the first event hash.
- Stored head equals the last event.
- Returned events and heads are defensive copies.
- Detached state cannot append.
- Two traces have independent sequences and heads.
- Reset clears runs, heads, and replay keys.
- Concurrent appends under the lock produce a contiguous sequence.

### 16.3 Idempotency tests

- Same key and same payload returns the original event.
- Replay does not increment `next_sequence`.
- Replay does not change event count or head.
- Same key with different summary conflicts.
- Same key with different details conflicts.
- The same key may be used by a different trace without collision.

### 16.4 Verification tests

- Clean one-event chain verifies.
- Clean complete journey verifies.
- Changed summary fails at the changed sequence.
- Changed nested detail fails at the changed sequence.
- Changed event hash fails at the changed sequence.
- Changed previous hash fails at the changed sequence.
- Deleted middle event fails at the first resulting gap.
- Reordered events fail at the first reordered sequence.
- Duplicated event fails at the duplicate position.
- Tail deletion fails against event count/head.
- Replacing stored head hash fails with `HEAD_HASH_MISMATCH`.
- Verifying does not repair any changed field.

### 16.5 Checkpoint 1-3 integration tests

- Benign enforce run completes and verifies.
- Adversarial shadow run completes and verifies.
- Adversarial enforce run pauses and verifies.
- Approved run extends the same trace and verifies.
- Rejected run cancels and verifies.
- Expired run cancels and verifies.
- Duplicate approval remains exact-once and chain-valid.
- Concurrent approval requests retain one terminal effect and a valid chain.
- Secrets do not appear in canonical payloads or event API output.

### 16.6 API tests

- Event response includes the additive hash fields.
- Verify endpoint returns the expected schema.
- Clean verification is `200` with `valid: true`.
- Invalid verification is `200` with `valid: false`.
- Unknown trace is `404`.
- Health exposes algorithm/schema without secrets.
- Demo tamper disabled path is unavailable.
- Wrong tamper secret is rejected.
- Successful disposable tamper causes verification failure.

### 16.7 Full regression gate

Run:

```bash
python3 -m pytest -q
./scripts/run_checkpoint_1.sh
./scripts/run_checkpoint_2.sh
./scripts/run_checkpoint_3.sh
./scripts/run_checkpoint_4.sh
```

No earlier script may be changed to skip behavior that the ledger broke.

## 17. Minimum manual smoke test

Start the API:

```bash
export DEMO_APPROVER_SECRET='local-demo-only-change-me'
export ENABLE_DEMO_TAMPER='true'
export DEMO_TAMPER_SECRET='local-tamper-only-change-me'
python3 -m uvicorn apps.api.main:app --reload
```

Start the hero journey:

```bash
curl -X POST http://127.0.0.1:8000/v1/runs \
  -H 'content-type: application/json' \
  -d '{"order_id":"ORD-8842","mode":"enforce","scenario":"adversarial"}'
```

Before approval:

```bash
curl http://127.0.0.1:8000/v1/traces/TR-REPLACE-ME/verify
```

Approve using the existing Checkpoint 3 endpoint, then verify the same trace
again. It must be valid and have a later head.

Create a second disposable benign run, verify it, tamper with one event, and
verify it again:

```bash
curl -X POST http://127.0.0.1:8000/v1/demo/traces/TR-DISPOSABLE/tamper \
  -H 'content-type: application/json' \
  -H 'X-Demo-Tamper-Secret: local-tamper-only-change-me' \
  -d '{"sequence":5,"replacement_summary":"Disposable demo alteration"}'

curl http://127.0.0.1:8000/v1/traces/TR-DISPOSABLE/verify
```

Expected final verification fragment:

```json
{
  "valid": false,
  "first_bad_sequence": 5,
  "failure_code": "EVENT_HASH_MISMATCH"
}
```

Finally reset all disposable state.

## 18. Acceptance criteria

- [ ] The original 59 tests still pass.
- [ ] Every new trace starts with a separate genesis head.
- [ ] Every event has a unique ID, schema version, previous hash, and event
      hash.
- [ ] Event hashes are reproducible from the documented canonical payload.
- [ ] Sequence, append, and head update occur under one store lock.
- [ ] Identical idempotent append returns the stored event without advancing
      the chain.
- [ ] Conflicting idempotent append is rejected.
- [ ] Benign, shadow, pending approval, approved, rejected, and expired traces
      verify successfully.
- [ ] Approval continuation extends the original trace chain.
- [ ] A modified disposable event causes verification to fail at the correct
      sequence.
- [ ] Middle deletion, reorder, duplicate, and tail truncation tests fail
      verification.
- [ ] Verification is read-only.
- [ ] Existing exact-once business effects remain exact-once.
- [ ] No approver/tamper secret or raw PII appears in events or hashes.
- [ ] Demo tampering is disabled by default and clearly labelled.
- [ ] The README says “tamper-evident,” not “immutable.”
- [ ] The complete Checkpoint 4 script passes twice.

## 19. Beginner-oriented work sessions

For a developer with basic Python knowledge, use short sessions and keep one
concept per session.

### Session 1 — Understand hashes (45-60 minutes)

- Hash one ordinary string with `hashlib.sha256`.
- Change one character and observe the new hash.
- Learn why a hash cannot restore the original text.

### Session 2 — Canonical JSON (60-90 minutes)

- Serialize the same dictionary in two insertion orders.
- Add `sort_keys=True` and compact separators.
- Write the fixed-vector test.

### Session 3 — One linked event (60-90 minutes)

- Add event hash fields.
- Append sequence 1 using the genesis hash.
- Confirm it verifies manually.

### Session 4 — Full store chain (90-120 minutes)

- Add heads and multi-event chaining.
- Keep all changes inside `MemoryTraceStore`.
- Run old tests before adding new behavior.

### Session 5 — Verifier (90-120 minutes)

- Implement one verification check at a time.
- Start with sequence, then previous hash, then event hash, then head checks.
- Add one failing test per check.

### Session 6 — Approval integration (60-90 minutes)

- Verify while pending.
- Approve and verify again.
- Check that earlier event hashes did not change.

### Session 7 — API and demo (60-90 minutes)

- Add the read-only endpoint first.
- Add demo tampering only after verification is stable.
- Perform the manual smoke test.

Estimated beginner time: 8-12 focused hours. Stop after any red gate and fix
that layer before moving forward.

## 20. Common mistakes to avoid

- Hashing `str(dictionary)` instead of canonical JSON.
- Including `event_hash` inside its own hash input.
- Generating the timestamp twice—once for storage and once for hashing.
- Recomputing old event hashes during a normal append.
- Using one global chain for all traces.
- Storing only the latest hash without event count or sequence.
- Treating a verification failure as an exception or server crash.
- Automatically repairing a broken chain during verification.
- Recording secrets or raw PII because “hashes hide it.” Hashing sensitive data
  is not the same as removing it.
- Calling the chain immutable.
- Adding DynamoDB before the local algorithm and fixed vector are stable.
- Letting tamper-demo code be enabled by default.
- Changing Checkpoint 3 workflow behavior while implementing storage.

## 21. Suggested commit checkpoints

Keep commits small and independently testable:

```text
test: pin checkpoint 3 regression baseline
feat: add canonical ledger hashing primitives
feat: add ledger event and head contracts
feat: hash memory trace events atomically
feat: add idempotent event append handling
feat: add read-only trace verification
test: verify approval resume chain continuity
feat: expose trace verification API
feat: add guarded disposable tamper demo
docs: document checkpoint 4 integrity claims and smoke test
```

Do not combine policy changes, fixture changes, or agent redesign with these
commits.

## 22. Exit and handoff to Checkpoint 5

Checkpoint 4 hands the next checkpoint:

- an ordered, hash-linked trace API;
- a stable verification response for an integrity badge;
- additive event hashes for decision-detail views;
- a disposable tamper demonstration;
- preserved approval and exact-once behavior; and
- a storage contract ready for a DynamoDB adapter.

Checkpoint 5 can build the API-driven dashboard against these stable contracts.
If cloud durability is prioritized first, the same ledger behavior can instead
be implemented behind a DynamoDB adapter, but its parity suite must reproduce
the local fixed-vector, append, idempotency, concurrency, and verification
tests before it becomes active.
