# Checkpoint 3 Implementation Plan — Approval, Resume, and Exact-Once Commit

## 1. Objective

Extend the working Checkpoint 2 governed shipment into a complete local human-
approval journey.

Checkpoint 2 can already stop the adversarial enforce run at
`PENDING_APPROVAL`. Checkpoint 3 must let a synthetic human approver approve or
reject that exact prepared action. An approval must cause the policy engine to
re-evaluate the commitment, confirm it exactly once, continue with Customer
Communications, and complete the existing trace. A rejection or expiry must
cancel the prepared reservation, release reserved spend exactly once, and end
the run without confirmation or notification.

The primary successful journey is:

```text
POST adversarial enforce run
    -> weight is guided from 50 kg to 500 kg
    -> carrier is guided to the certified option
    -> INR 900 booking is prepared
    -> projected INR 4,550 exceeds INR 4,000
    -> run pauses at PENDING_APPROVAL

POST approve exact pending action
    -> approval binding is validated
    -> confirm is re-evaluated by the policy engine
    -> approved exception is allowed
    -> booking confirms exactly once
    -> reserved spend becomes committed spend
    -> Customer Communications writes one synthetic outbox item
    -> the same trace becomes COMPLETED
```

This checkpoint remains local, deterministic, and beginner-readable. It does
not require an LLM or AWS account.

## 2. Baseline and relationship to earlier checkpoints

### 2.1 Checkpoint 1 capabilities that must remain intact

- Four plain-Python agent roles.
- One bounded sequential orchestrator.
- All operational effects pass through the tool registry and governor.
- Deterministic fixtures and mock tools.
- One isolated `TrajectoryState` per trace.
- Ordered trace events.
- CLI and FastAPI entry points.

### 2.2 Checkpoint 2 capabilities that must remain intact

- `shadow` and `enforce` modes.
- `benign` and `adversarial` scenarios.
- Six deterministic policy families.
- Weight-provenance and cold-chain guide-back.
- Cumulative spend evaluation.
- Prepare-before-confirm booking state.
- Exact action and state hashes on a prepared action.
- A pending approval bound to the trace, action, state, and policy version.
- Decision, event, run, fixture, and approval read APIs.

### 2.3 Verified starting state

At plan creation, the current repository has 39 passing tests:

```text
39 passed in 2.41s
```

The first Checkpoint 3 implementation gate is to preserve that result before
adding new behavior. Existing tests may receive additive assertions, but their
established outcomes must not be rewritten to hide regressions.

### 2.4 Required compatibility behavior

- A benign enforce run must still complete immediately.
- An adversarial shadow run must still complete without creating an approval.
- An adversarial enforce run must still return `pending_approval` before a
  decision is submitted.
- Existing read endpoints retain their paths and fields.
- New response fields are additive.
- A resumed run uses the original `trace_id`; it is not a new run.
- Inventory and Dispatch must not run again during approval resume.

## 3. Scope

### 3.1 Included

- Approve and reject decisions for one synthetic pending approval.
- An approval read-by-ID endpoint.
- An approval decision endpoint protected by a demo-only shared secret.
- Optimistic version checking for stale approval screens.
- Request idempotency for approval decisions.
- Approval records for pending, approved, rejected, and expired outcomes.
- Validation of trace, prepared action, action hash, state hash, policy version,
  expiry, run status, workflow stage, and separation of duties.
- Re-evaluation by the policy engine after approval.
- Resuming only the unfinished portion of the existing workflow.
- Exact-once synthetic booking confirmation.
- Customer Communications after successful confirmation.
- Rejection and expiry cancellation of the prepared reservation.
- Exact-once release of reserved spend.
- New approval and resume trace events.
- Injected clock support for deterministic expiry tests.
- CLI/demo support that performs start and decision in the same process.
- Unit, policy, integration, API, concurrency, and end-to-end tests.
- Updated README, `.env.example`, and a Checkpoint 3 verification script.

### 3.2 Explicitly excluded

- DynamoDB, a hash-chained ledger, tamper verification, and `/verify`.
- Step Functions or callback task tokens.
- Cognito or production identity.
- Lambda, API Gateway, EventBridge, Amplify, or any AWS deployment.
- React dashboard work.
- Cedar activation.
- Strands or Bedrock integration.
- A background scheduler or durable job queue.
- Multi-approver voting, approval assignment, or approval delegation.
- Editing a prepared action after it is submitted for approval.
- Multiple pending commitments in one trace.
- Real carrier, payment, messaging, or customer data.

### 3.3 Scope guard

Checkpoint 3 is complete when approve, reject, expiry, duplicate request, and
concurrent request paths are correct in one process using the in-memory store.
Do not begin the ledger, dashboard, or AWS work while any Checkpoint 3
acceptance test is red.

## 4. User-visible results

### 4.1 Approve path

1. Start an adversarial enforce run.
2. Read the returned `pending_approval_id`.
3. Read the approval and show the exact amount, action, hashes, expiry, and
   version.
4. Submit `approve` using a demo approver identity.
5. Receive the updated approval and completed run.
6. Read the trace and see approval, resume, re-evaluation, confirmation,
   notification, and completion in order.

Expected final values:

```text
run status                 COMPLETED
approval status            APPROVED
prepared action status     CONFIRMED
spend committed            INR 4,550
spend reserved             INR 0
booking confirmations      1
customer notifications     1
```

### 4.2 Reject path

1. Start a fresh adversarial enforce run.
2. Submit `reject` for its pending approval.
3. Manifest cancels the synthetic reservation through a registered tool.
4. The run ends as `CANCELLED` without confirmation or notification.

Expected final values:

```text
run status                 CANCELLED
approval status            REJECTED
prepared action status     CANCELLED
spend committed            INR 3,650
spend reserved             INR 0
booking confirmations      0
customer notifications     0
```

### 4.3 Expiry path

When the injected clock is later than `expires_at`, the approval can no longer
be approved. It becomes `EXPIRED`, the reservation is cancelled, and the run
ends as `CANCELLED`. No background scheduler is claimed in this checkpoint.
Expiry is checked whenever the approval service processes a decision or runs
its explicit `expire_due_approvals()` operation.

## 5. Architecture

```text
FastAPI approval endpoint
        |
        v
RunService.resolve_approval(...)
        |
        +--> demo approver authentication at HTTP boundary
        +--> ApprovalService validation and idempotency
        +--> MemoryTraceStore approval/run transition lock
        |
        +-- approve ---------------------------------------+
        |                                                  |
        |   mark approval APPROVED                         |
        |   mark prepared action APPROVED                  |
        |   append approval/resume events                  |
        |   CarrierAgent.resume_booking()                  |
        |       -> ManifestGovernor.execute_tool()         |
        |       -> policy re-evaluation                    |
        |       -> confirm_freight_booking                 |
        |   CustomerCommunicationsAgent.run()              |
        |   mark same trace COMPLETED                      |
        |                                                  |
        +-- reject or expire ------------------------------+
            mark approval REJECTED or EXPIRED
            CarrierAgent.cancel_booking()
                -> ManifestGovernor.execute_tool()
                -> cancel_freight_booking
            release reserved spend exactly once
            mark same trace CANCELLED
```

The human decision is not itself a logistics tool. It is a control-plane state
transition. Any resulting logistics effect—confirmation, cancellation, or
notification—must still pass through the existing governor and registered
tool boundary.

## 6. State machines

### 6.1 Approval state

Add a dedicated `ApprovalStatus` enum:

```text
PENDING_APPROVAL
APPROVED
REJECTED
EXPIRED
```

Allowed transitions:

```text
PENDING_APPROVAL -> APPROVED
PENDING_APPROVAL -> REJECTED
PENDING_APPROVAL -> EXPIRED
```

No other transition is allowed. An already resolved approval is immutable.
An identical idempotent replay returns the stored result; a conflicting replay
returns a conflict.

### 6.2 Prepared-action state

Retain `CommitmentStatus` and enforce:

```text
PREPARED -> PENDING_APPROVAL -> APPROVED -> CONFIRMED
                              -> REJECTED -> CANCELLED
                              -> EXPIRED  -> CANCELLED
```

`CONFIRMED` and `CANCELLED` are terminal.

### 6.3 Run state

Extend `RunStatus` with:

```text
CANCELLED
```

The relevant transitions are:

```text
RUNNING -> PENDING_APPROVAL -> RUNNING -> COMPLETED
                            -> CANCELLED
```

Use `FAILED` only for an unexpected implementation or mock-tool failure.
Rejection and expiry are normal governed outcomes, not failures.

### 6.4 Workflow cursor

Add `WorkflowStage` to prevent the resume path from rerunning completed work:

```text
STARTED
INVENTORY_COMPLETE
DISPATCH_COMPLETE
BOOKING_PREPARED
AWAITING_APPROVAL
BOOKING_CONFIRMED
NOTIFICATION_SENT
COMPLETE
CANCELLED
BLOCKED
FAILED
```

Store it in `TrajectoryState` and expose it in `RunSummary`. Resume is accepted
only when both are true:

```text
state.status == PENDING_APPROVAL
state.workflow_stage == AWAITING_APPROVAL
```

This is safer than guessing the resume position from which optional fields are
non-null.

## 7. Domain-model changes

### 7.1 New enums

`ApprovalDecision`:

```text
APPROVE
REJECT
```

`ApprovalStatus` and `WorkflowStage` are defined above.

### 7.2 ApprovalRecord

Replace the narrow meaning of `PendingApproval` with `ApprovalRecord`. Keep a
temporary alias or compatible export named `PendingApproval` so Checkpoint 2
imports do not break during the migration.

```text
approval_id: str
trace_id: str
prepared_action_id: str
action_hash: str
state_hash: str
policy_version: str
reason_code: str
status: ApprovalStatus
version: int
created_at: UTC datetime
expires_at: UTC datetime
decided_at: UTC datetime | None
decision: ApprovalDecision | None
approver_label: str | None
comment: str | None
decision_idempotency_key: str | None
```

Rules:

- `version` starts at `1`.
- A successful resolution increments it to `2`.
- `decided_at`, `decision`, and `approver_label` are all absent while pending.
- `comment` is optional, bounded, and never used as policy input.
- The idempotency key is stored but never copied into trace summaries.
- The stored record is replaced as one value rather than partially mutated.

### 7.3 PreparedAction additions

The current action hash is retained. Add enough explicit preparation context
to recompute and validate its state binding:

```text
mandate_id: str
policy_version: str
spend_committed_at_prepare_minor: int
spend_reserved_before_minor: int
spend_reserved_after_minor: int
```

The canonical state hash must cover at least:

```text
trace_id
order_id
mandate_id
policy_version
prepared_action_id
quote/resource ID
amount and currency
spend committed at prepare
reserved spend before and after prepare
selected carrier quote ID
```

The hash input must use canonical JSON with sorted keys and fixed separators.

### 7.4 TrajectoryState additions

```text
workflow_stage: WorkflowStage
terminal_reason: str | None
```

Retain `approved_by` for policy context, but source it only from a successfully
resolved `ApprovalRecord`.

### 7.5 RunSummary additions

```text
workflow_stage: str
confirmed_booking_id: str | None
terminal_reason: str | None
```

These fields are additive to the current response.

## 8. Approval binding and validation

Create `packages/approvals/service.py`. It should contain small validation and
transition functions rather than placing approval logic in FastAPI routes.

Before an approval decision changes any state, validate in this order:

1. The approval exists.
2. The referenced trace exists.
3. The approval is still `PENDING_APPROVAL`.
4. `expected_version` equals the stored version.
5. The run is `PENDING_APPROVAL` at `AWAITING_APPROVAL`.
6. `state.pending_approval_id` equals this approval ID.
7. The prepared action exists in the same trace.
8. The prepared action ID matches the approval.
9. The action hash recomputes and matches both records.
10. The state hash recomputes and matches both records.
11. The mandate and policy versions still match.
12. The selected quote, amount, and currency still match the prepared action.
13. Current committed and reserved spend match the preparation snapshot.
14. The approval has not expired.
15. The approver is not the action preparer.

If an approval is expired, process the expiry/cancellation path instead of
silently creating a new approval.

### 8.1 Stale or tampered binding behavior

- A changed `expected_version` is an HTTP 409 conflict.
- A changed internal action/state/policy binding is a fail-closed policy or
  approval error and the booking must not confirm.
- An expired decision request is HTTP 410 after expiry cleanup succeeds.
- A missing approval or trace is HTTP 404.
- A malformed decision request is HTTP 422.

### 8.2 Separation of duties

The demo approver label must not equal `prepared_by.value`. The API validates
an allowlisted label shape such as `DEMO-APPROVER-OPS-1`; it does not trust the
label as production identity. The README and API health response must disclose
`approval_auth_mode=demo_shared_secret`.

## 9. Store and concurrency design

The current `get_state()` returns a deep copy, which is correct for readers but
cannot be used to resume a live trace. Add a deliberate internal update path;
do not weaken the public read method.

Recommended in-memory design:

- Keep `get_state()` and approval reads as copies.
- Add an internal store operation that resolves one approval while holding the
  store's `RLock`.
- Let `RunService.resolve_approval()` also hold a service-level resolution
  lock for the complete local approve/reject workflow.
- Validate and claim one pending decision before executing confirmation or
  cancellation.
- Store the decision idempotency key and payload fingerprint.

Checkpoint 3 promises process-local serialization only. The plan must state
that a future DynamoDB adapter requires conditional writes on approval version,
run status, and effect idempotency keys.

### 9.1 Idempotency behavior

For `POST /v1/approvals/{approval_id}`:

- Same idempotency key and identical normalized request: return the original
  response with `idempotent_replay=true`.
- Same key with different request fields: HTTP 409.
- Different key after the approval was resolved: HTTP 409.
- Concurrent approve and reject: exactly one succeeds; the other conflicts.
- A network retry must never create a second confirmation, cancellation, spend
  update, or notification.

The logistics tool idempotency keys remain deterministic:

```text
<trace_id>:confirm:<prepared_action_id>
<trace_id>:cancel:<prepared_action_id>
<trace_id>:tracking-outbox
```

## 10. Agent functionality

### 10.1 Inventory Agent

No approval-specific logic. Its Checkpoint 1 and 2 behavior must remain
unchanged. It must not run again during resume.

### 10.2 Dispatch Agent

No approval-specific logic. Its provenance and vehicle guide-back behavior
must remain unchanged. It must not run again during resume.

### 10.3 Carrier Agent initial path

Retain the current responsibilities:

1. List and select a carrier quote.
2. Follow structured cold-chain guidance when necessary.
3. Prepare the booking.
4. Add the prepared amount to reserved spend.
5. Attempt confirmation through the governor.
6. Return normally when the governor creates a pending approval.

Update workflow stages at preparation and pause.

### 10.4 Carrier Agent resume path

Add a focused method such as:

```text
resume_booking(state, governor, approval_record) -> str
```

Responsibilities:

1. Require `APPROVED` approval and `APPROVED` prepared action.
2. Reuse the original prepared action and action hash.
3. Call `confirm_freight_booking` through the governor.
4. Use the original deterministic confirmation idempotency key.
5. Require a fresh policy decision; do not bypass policy because a human
   clicked Approve.
6. Store the confirmation only after the mock tool succeeds.
7. Move the workflow stage to `BOOKING_CONFIRMED`.

It must not list quotes, select a quote, or prepare a second booking.

### 10.5 Carrier Agent cancel path

Add a method such as:

```text
cancel_booking(state, governor, approval_record, reason) -> str
```

Responsibilities:

1. Call the new registered `cancel_freight_booking` tool.
2. Reference the exact prepared action and action hash.
3. Use a deterministic cancellation idempotency key.
4. Release reserved spend exactly once after tool success.
5. Set the prepared action to `CANCELLED`.
6. Never change committed spend.

### 10.6 Customer Communications Agent

Its tool contract remains unchanged. It runs after a resumed confirmation only
when:

- a confirmation ID exists;
- the prepared action is `CONFIRMED`;
- the run is active, not cancelled or blocked; and
- no notification already exists.

Its existing outbox idempotency key prevents a duplicate notification on a
safe replay.

## 11. Tool changes

### 11.1 New `cancel_freight_booking` tool

```text
owner: Carrier
effect class: reversible_write
input:
  prepared_action_id
  action_hash
  cancellation_reason_code
  idempotency_key
output:
  cancellation_id
  prepared_action_id
  status = cancelled
```

The mock adapter must verify that the prepared booking exists. The governor and
policy engine validate the action hash against `PreparedAction` before the mock
handler is called. A cancellation of an already confirmed action must fail.
Replaying the same cancellation key and arguments returns the original result.

### 11.2 Mock observability helpers

Add read-only test helpers or counters for:

- number of confirmed bookings;
- number of cancelled bookings; and
- number of outbox notifications.

These helpers support exact-once tests and are not exposed as production APIs.

### 11.3 Governor state updates

Move commitment state mutations into small named helpers rather than growing
more `if tool_name == ...` branches inline.

On successful confirmation:

```text
prepared status: APPROVED -> CONFIRMED
reserved spend: subtract amount once
committed spend: add amount once
confirmed_booking_id: set once
```

On successful cancellation:

```text
prepared status: REJECTED/EXPIRED/PENDING_APPROVAL -> CANCELLED
reserved spend: subtract amount once
committed spend: unchanged
```

Any subtraction that would make reserved spend negative fails closed.

## 12. Policy changes

Approval does not skip the policy engine. The resumed confirm creates a new
`ToolProposal`, `PolicyRequest`, and `Decision`.

For a resumed confirmation, `ManifestGovernor._build_request()` must add a
typed, redacted `approval` object to policy context. The governor obtains the
record from the store using `state.pending_approval_id`; agents must not supply
approval fields as tool arguments. The context contains only:

```text
approval_id
prepared_action_id
status
action_hash
state_hash
policy_version
approver_label
created_at
expires_at
decided_at
```

The policy engine evaluates this context against the prepared action and live
trace state. The free-form comment and decision idempotency key are excluded.
`pending_approval_id` remains set through re-evaluation and is cleared only
after successful confirmation or cancellation.

### 12.1 Commitment-budget policy

For an above-ceiling confirmation:

- No approval: `ESCALATE` with `SPEND_APPROVAL_REQUIRED`.
- Exact pending approval: `ESCALATE`.
- Exact valid approved approval: `ALLOW` with
  `SPEND_EXCEPTION_APPROVED`.
- Expired approval: `BLOCK` with `APPROVAL_EXPIRED`.
- Action/state/policy mismatch: `BLOCK` with the matching fail-closed reason.
- Rejected approval: `BLOCK` with `APPROVAL_REJECTED`.

At-or-below-ceiling confirmation remains allowed without human approval.

### 12.2 Commitment-state and separation-of-duties policy

For resumed confirmation, require:

- prepared status `APPROVED` when an above-ceiling exception is involved;
- matching approved approval record;
- action, state, and policy hashes match;
- approval is unexpired;
- approver differs from preparer; and
- action is neither confirmed nor cancelled.

For cancellation, allow the Carrier Agent only when the prepared action is
pending, rejected, or expired and the action hash matches. Block cancellation
after confirmation.

### 12.3 New controlled reason codes

Add safe catalogue entries:

```text
SPEND_EXCEPTION_APPROVED
APPROVAL_NOT_FOUND
APPROVAL_NOT_PENDING
APPROVAL_VERSION_CONFLICT
APPROVAL_ACTION_MISMATCH
APPROVAL_STATE_MISMATCH
APPROVAL_POLICY_MISMATCH
APPROVAL_EXPIRED
APPROVAL_REJECTED
APPROVER_CONFLICT
APPROVAL_IDEMPOTENCY_CONFLICT
CANCELLATION_ALLOWED
CANCELLATION_ALREADY_APPLIED
```

Do not put the free-form approval comment into `because`.

## 13. Orchestrator and application-service changes

### 13.1 Initial run

Keep `ShipmentOrchestrator.run()` behavior stable. It now also maintains the
workflow cursor. When the current governor returns an approval:

```text
run status      = PENDING_APPROVAL
workflow stage  = AWAITING_APPROVAL
current agent   = None
```

The Carrier invocation is not fully complete at this point. Append
`AGENT_PAUSED` instead of `AGENT_COMPLETED` for that invocation. This prevents
the trace from claiming that the Carrier Agent completed before the financial
effect was resolved.

### 13.2 Resume approved run

Add a method such as:

```text
resume_approved(state, approval_record) -> TrajectoryState
```

It must:

1. Revalidate the expected run/stage/approval relationship.
2. Set run status to `RUNNING`.
3. Append `RUN_RESUMED`.
4. Invoke only `CarrierAgent.resume_booking()`.
5. Append the Carrier completion event.
6. Invoke only `CustomerCommunicationsAgent.run()`.
7. Append the Communications completion event.
8. Set the workflow stage to `COMPLETE`.
9. Set run status to `COMPLETED`.
10. Append `RUN_COMPLETED`.

If fresh policy evaluation blocks, the run becomes `BLOCKED`; it must not
confirm or notify.

### 13.3 Reject or expire run

Add a method such as:

```text
cancel_pending(state, approval_record, reason) -> TrajectoryState
```

It must:

1. Invoke `CarrierAgent.cancel_booking()` through the governor.
2. Clear `pending_approval_id` after successful cancellation.
3. Set workflow stage to `CANCELLED`.
4. Set run status to `CANCELLED`.
5. Set a controlled `terminal_reason`.
6. Append `RUN_CANCELLED`.
7. Never invoke Customer Communications.

### 13.4 RunService

Add:

```text
get_approval(approval_id)
resolve_approval(approval_id, request)
expire_due_approvals()
```

`resolve_approval()` owns the application workflow. FastAPI routes only parse,
authenticate, invoke this method, and serialize its result.

Return a domain result containing:

```text
approval: ApprovalRecord
run: RunSummary
idempotent_replay: bool
```

## 14. Trace events

Extend `EventType` with:

```text
AGENT_PAUSED
AGENT_RESUMED
APPROVAL_APPROVED
APPROVAL_REJECTED
APPROVAL_EXPIRED
RUN_RESUMED
RUN_CANCELLED
```

The existing `TOOL_ATTEMPTED`, `POLICY_DECIDED`, and `TOOL_SUCCEEDED` events
cover resumed confirmation and cancellation.

### 14.1 Approve event order

The trace must show this relative order:

```text
APPROVAL_REQUIRED
AGENT_PAUSED(carrier)
RUN_PAUSED
APPROVAL_APPROVED
RUN_RESUMED
AGENT_RESUMED(carrier)
TOOL_ATTEMPTED(confirm_freight_booking)
POLICY_DECIDED(SPEND_EXCEPTION_APPROVED)
TOOL_SUCCEEDED(confirm_freight_booking)
AGENT_COMPLETED(carrier)
TOOL_ATTEMPTED(write_tracking_outbox)
POLICY_DECIDED(...)
TOOL_SUCCEEDED(write_tracking_outbox)
AGENT_COMPLETED(customer_communications)
RUN_COMPLETED
```

### 14.2 Reject event order

```text
APPROVAL_REQUIRED
RUN_PAUSED
APPROVAL_REJECTED
TOOL_ATTEMPTED(cancel_freight_booking)
POLICY_DECIDED(...)
TOOL_SUCCEEDED(cancel_freight_booking)
RUN_CANCELLED
```

Approval event details may contain IDs, status, approver label, version, and
decision time. They must not contain the shared secret or an unbounded comment.

## 15. HTTP API contract

### 15.1 Existing endpoints retained

| Method | Path | Checkpoint 3 behavior |
|---|---|---|
| `GET` | `/health/ready` | Adds approval mode and Checkpoint 3 version |
| `POST` | `/v1/runs` | Behavior remains unchanged before approval |
| `GET` | `/v1/runs/{trace_id}` | Adds workflow/confirmation fields |
| `GET` | `/v1/traces/{trace_id}/events` | Includes post-approval events |
| `GET` | `/v1/traces/{trace_id}/decisions` | Includes fresh resume decisions |
| `GET` | `/v1/approvals` | Supports optional status filter; returns resolved records too |
| `POST` | `/v1/demo/reset` | Also clears approval idempotency results |

### 15.2 Get one approval

`GET /v1/approvals/{approval_id}`

Response, HTTP 200:

```json
{
  "approval_id": "APR-...",
  "trace_id": "TR-...",
  "prepared_action_id": "PREP-ORD-8842-QUOTE-COLD-01",
  "action_hash": "sha256:...",
  "state_hash": "sha256:...",
  "policy_version": "demo-v1",
  "reason_code": "SPEND_APPROVAL_REQUIRED",
  "status": "pending_approval",
  "version": 1,
  "created_at": "...Z",
  "expires_at": "...Z",
  "decided_at": null,
  "decision": null,
  "approver_label": null,
  "comment": null
}
```

Unknown approval: HTTP 404 with `APPROVAL_NOT_FOUND`.

### 15.3 Decide an approval

`POST /v1/approvals/{approval_id}`

Required header:

```text
X-Demo-Approver-Secret: <server-configured demo secret>
```

Request:

```json
{
  "decision": "approve",
  "approver_label": "DEMO-APPROVER-OPS-1",
  "comment": "Synthetic exception approved for the demo.",
  "expected_version": 1,
  "idempotency_key": "approval-demo-request-001"
}
```

Response, HTTP 200:

```json
{
  "approval": {
    "approval_id": "APR-...",
    "status": "approved",
    "version": 2,
    "decision": "approve",
    "approver_label": "DEMO-APPROVER-OPS-1"
  },
  "run": {
    "trace_id": "TR-...",
    "status": "completed",
    "workflow_stage": "complete",
    "spend_committed_minor": 455000,
    "spend_reserved_minor": 0,
    "confirmed_booking_id": "CONFIRM-PREP-...",
    "notification_id": "NOTIFY-ORD-8842"
  },
  "idempotent_replay": false
}
```

Reject uses the same contract with `decision=reject` and returns a cancelled
run.

### 15.4 HTTP error mapping

| Condition | Status | Code |
|---|---:|---|
| Missing/wrong demo secret | 401 | `APPROVER_UNAUTHORIZED` |
| Server secret not configured | 503 | `APPROVAL_AUTH_NOT_CONFIGURED` |
| Approval or trace missing | 404 | `APPROVAL_NOT_FOUND` / existing trace code |
| Invalid body or label | 422 | `VALIDATION_ERROR` |
| Stale version | 409 | `APPROVAL_VERSION_CONFLICT` |
| Already resolved with a different request | 409 | `APPROVAL_NOT_PENDING` |
| Idempotency key reused differently | 409 | `APPROVAL_IDEMPOTENCY_CONFLICT` |
| Approval expired | 410 | `APPROVAL_EXPIRED` |
| Binding/policy mismatch | 409 | matching controlled fail-closed code |
| Unexpected runtime fault | 500 | safe existing error envelope |

### 15.5 Health response additions

```json
{
  "version": "0.5.0",
  "approval_mode": "local",
  "approval_auth_mode": "demo_shared_secret",
  "approval_mutation_ready": true
}
```

`approval_mutation_ready` is false when `DEMO_APPROVER_SECRET` is missing, but
read-only endpoints and run creation may remain available.

## 16. Demo authentication and configuration

Add to `.env.example`:

```text
DEMO_APPROVER_SECRET=replace-with-a-local-demo-value
```

The project does not currently load `.env` files automatically. Document the
required shell export when starting the API. Do not add a configuration library
only for this field unless it is already needed elsewhere.

At the HTTP boundary:

- compare secrets with `hmac.compare_digest`;
- never log, trace, return, or hash the supplied header into public events;
- do not send the secret to policy context;
- keep direct service tests independent of HTTP authentication; and
- label the mechanism as demo-only, not production authentication.

## 17. CLI and demo script

Because storage is in memory, a second CLI process cannot resume a trace made
by the first process. Do not create a misleading separate approval CLI that
expects cross-process persistence.

Instead add an optional same-process demonstration flag or a small script:

```bash
python3 -m apps.runtime.run \
  --order ORD-8842 \
  --mode enforce \
  --scenario adversarial \
  --approval approve
```

The program should:

1. Start the run.
2. Print the pause and approval ID.
3. Resolve that approval in the same `RunService` instance.
4. Print the final approval and run statuses.

The normal command without `--approval` must still stop at
`PENDING_APPROVAL`.

## 18. Testing plan

### 18.1 Baseline regression gate

Before implementation:

```bash
python3 -m pytest -q
```

Expected baseline: 39 passing tests. After every implementation phase, run the
full suite. All Checkpoint 1 and 2 tests must remain green.

### 18.2 Unit tests — domain and approval service

Create `tests/unit/test_approval_service.py` and extend commitment tests.

Test:

- pending approval converts to approved with version 2;
- pending approval converts to rejected with version 2;
- only the documented transitions are accepted;
- expected-version mismatch conflicts;
- same decision idempotency key and payload replays safely;
- same key with different payload conflicts;
- different key after resolution conflicts;
- missing approval fails safely;
- expiry uses an injected clock;
- expired approval cannot become approved;
- approver cannot equal preparer;
- action hash mismatch fails;
- state hash mismatch fails;
- policy version mismatch fails;
- run/approval trace mismatch fails;
- current spend differing from the preparation snapshot fails;
- comments longer than the API limit are rejected at the boundary;
- free-form comments are not inserted into policy reasons or event summaries.

### 18.3 Unit tests — commitment effects and mock tools

Test:

- cancel requires an existing prepared booking;
- cancel requires the correct action hash;
- cancel is idempotent for the same key and arguments;
- changed arguments with the same key conflict;
- confirmed booking cannot be cancelled;
- cancelled booking cannot be confirmed;
- confirmation changes reserved to committed exactly once;
- cancellation releases reserved spend exactly once;
- neither path allows reserved spend to become negative;
- notification remains exactly once.

### 18.4 Policy tests

Extend `tests/policy/` with table-driven cases:

- above ceiling without approval escalates;
- exact pending approval still escalates;
- exact approved approval allows with `SPEND_EXCEPTION_APPROVED`;
- approved record with wrong action hash blocks;
- approved record with wrong state hash blocks;
- approved record with wrong policy version blocks;
- expired approval blocks;
- rejected approval blocks;
- preparer/approver identity conflict blocks;
- duplicate confirmation blocks;
- at-ceiling booking still allows without approval;
- cancellation is allowed for rejected/expired prepared action;
- cancellation after confirmation blocks.

### 18.5 Integration tests — approve journey

Create `tests/integration/test_approval_resume.py`.

Test the full domain journey:

1. Start adversarial enforce.
2. Assert one pending approval and INR 90,000 reserved.
3. Approve it.
4. Assert the same trace ID completes.
5. Assert committed spend becomes 455,000.
6. Assert reserved spend becomes zero.
7. Assert one confirmation and one notification.
8. Assert Inventory and Dispatch were not rerun.
9. Assert the approval decision precedes confirmation.
10. Assert fresh confirm policy decision has
    `SPEND_EXCEPTION_APPROVED`.
11. Assert the run finishes with ordered event sequences.

### 18.6 Integration tests — reject and expiry journeys

Test:

- rejection cancels the reservation;
- rejection leaves committed spend at 365,000;
- rejection creates no confirmation or notification;
- rejection ends as normal `CANCELLED`, not `FAILED`;
- expiry produces the same operational cancellation but status `EXPIRED` on
  the approval;
- expiry cannot later be approved;
- cleanup is idempotent.

### 18.7 Concurrency and replay tests

Create `tests/integration/test_approval_concurrency.py`.

Using two threads against the same service:

- two identical approve requests yield one effect and one safe replay;
- approve and reject racing yield one success and one conflict;
- two different idempotency keys cannot confirm twice;
- no race produces negative reserved spend;
- event sequences remain strictly increasing;
- one trace's approval cannot resume another trace.

### 18.8 API tests

Create `tests/e2e/test_checkpoint_3_api.py`.

Test:

- `GET /v1/approvals/{id}` returns the pending record;
- missing approval returns 404;
- missing or wrong secret returns 401;
- missing server secret returns 503 for mutation only;
- approve returns updated approval and completed run;
- reject returns updated approval and cancelled run;
- stale version returns 409;
- conflicting idempotency reuse returns 409;
- expired approval returns 410;
- malformed decision/label/comment returns 422;
- resolved approval remains readable;
- subsequent run/events/decisions reads show final state;
- reset removes runs, approvals, decision replay entries, and mock effects.

### 18.9 Checkpoint 1 and 2 regression tests

Retain explicit assertions that:

- benign enforce still completes without approval;
- adversarial shadow still creates no approval;
- adversarial enforce still pauses before any confirm success;
- every tool attempt still has exactly one decision;
- all old API paths and error envelopes still work;
- two independent traces do not share approvals or state.

## 19. File-by-file implementation map

### New files

```text
packages/approvals/__init__.py
packages/approvals/service.py
tests/unit/test_approval_service.py
tests/integration/test_approval_resume.py
tests/integration/test_approval_concurrency.py
tests/e2e/test_checkpoint_3_api.py
scripts/run_checkpoint_3.sh
```

### Files to modify

```text
packages/domain/enums.py
  ApprovalDecision, ApprovalStatus, WorkflowStage, RunStatus.CANCELLED,
  and new EventType members.

packages/domain/models.py
  ApprovalRecord, prepared-action binding fields, workflow cursor,
  decision result, and additive run-summary fields.

packages/domain/errors.py
  Typed approval/auth/version/expiry/conflict errors.

packages/commitments/service.py
  Canonical action/state hash helpers and transition helpers.

packages/governor/reasons.py
  New controlled reason catalogue entries.

packages/governor/governor.py
  Approval context on resumed confirmation and named confirm/cancel state
  update helpers.

packages/policy/python_engine.py
  Approved-exception validation and cancellation policy behavior.

packages/tools/definitions.py
  Register cancel_freight_booking.

packages/tools/mocks.py
  Cancellation adapter, exact-once bookkeeping, and read-only test counters.

packages/ledger/memory_store.py
  Approval read/update operations, local transition locking, resolved records,
  and approval decision replay storage.

apps/runtime/agents/carrier.py
  Focused resume and cancel methods.

apps/runtime/agents/communications.py
  Stronger resumed-confirmation preconditions; otherwise same tool contract.

apps/runtime/orchestrator.py
  Workflow cursor, resume_approved(), and cancel_pending().

apps/runtime/service.py
  ApprovalService wiring, read-one, resolve, and expire operations.

apps/runtime/run.py
  Optional same-process approval demonstration.

apps/api/schemas.py
  Approval decision request/result schemas and additive response fields.

apps/api/dependencies.py
  Demo approver secret dependency/configuration helper.

apps/api/main.py
  Approval read/decision routes, authentication, and error mapping.

.env.example
  DEMO_APPROVER_SECRET name with a clearly fake placeholder.

README.md
  Checkpoint 3 status, commands, API examples, state diagram, limitations,
  and demo-only authentication disclosure.
```

## 20. Implementation order and gates

### Phase 0 — Freeze and verify the baseline

Tasks:

1. Run all 39 current tests.
2. Run benign enforce, adversarial shadow, and adversarial enforce manually.
3. Record the current public API response shapes.
4. Do not clean or overwrite unrelated working-tree changes.

**Gate 0:** existing suite passes and the adversarial enforce run pauses.

### Phase 1 — Add state contracts only

Tasks:

1. Add enums, model fields, error classes, event types, and API schemas.
2. Add workflow-stage updates to the existing initial run.
3. Add canonical hash recomputation tests.
4. Keep approval mutation disabled.

**Gate 1:** all old journeys pass with additive fields and correct workflow
stages.

### Phase 2 — Build approval validation and local store transitions

Tasks:

1. Add `ApprovalService`.
2. Add injected clock behavior.
3. Add approval read-one and version/idempotency storage.
4. Implement validation without yet resuming agents.
5. Complete unit tests for transitions and binding.

**Gate 2:** approval can be safely claimed as approved/rejected/expired in unit
tests; no logistics effect runs yet.

### Phase 3 — Build cancellation first

Tasks:

1. Register and implement `cancel_freight_booking`.
2. Add Carrier cancel method.
3. Add governor cancellation state updates.
4. Add reject and expiry orchestration.
5. Prove reserved spend is released once.

Cancellation is built before approval resume because it is the smaller state
transition and validates the store/agent/governor integration.

**Gate 3:** reject and expiry end in `CANCELLED`, with no confirmation or
notification.

### Phase 4 — Build approval resume

Tasks:

1. Add approved-exception policy behavior.
2. Add Carrier resume method.
3. Add orchestrator resume method.
4. Continue to Communications.
5. Prove confirmation and notification are exact-once.

**Gate 4:** adversarial enforce -> approve completes the same trace at INR
4,550 with zero reserved spend.

### Phase 5 — Expose HTTP and CLI behavior

Tasks:

1. Add demo-secret authentication.
2. Add get-one and decision endpoints.
3. Add status filters and error mapping.
4. Add same-process CLI/demo option.
5. Add API and end-to-end tests.

**Gate 5:** the full hero journey works through HTTP with no direct state
editing.

### Phase 6 — Concurrency, regression, and documentation

Tasks:

1. Add replay and two-thread race tests.
2. Run all Checkpoint 1–3 tests.
3. Add `scripts/run_checkpoint_3.sh`.
4. Update README and configuration disclosure.
5. Capture one approve and one reject sample trace.

**Gate 6:** full suite passes twice from a clean reset and the verification
script succeeds.

## 21. Acceptance criteria

Checkpoint 3 is complete only when all are true:

- The initial adversarial enforce run still stops at `PENDING_APPROVAL`.
- The exact approval can be read by ID.
- Approval mutation requires the configured demo secret over HTTP.
- A valid approval resumes the same trace.
- Policy evaluation runs again before confirmation.
- An approved above-ceiling exception receives
  `SPEND_EXCEPTION_APPROVED`.
- Inventory, Dispatch, quote selection, and preparation are not rerun.
- Confirmation executes exactly once.
- Reserved INR 900 becomes committed exactly once.
- Customer Communications runs exactly once after confirmation.
- Final approved spend is INR 4,550 committed and INR 0 reserved.
- Rejection and expiry cancel the reservation exactly once.
- Rejection and expiry never confirm or notify.
- Duplicate requests are idempotent or conflict predictably.
- A concurrent approve/reject race has one winner.
- Stale, altered, cross-trace, expired, or wrong-policy approvals fail closed.
- Event sequence remains ordered and explains the lifecycle.
- All Checkpoint 1 and 2 tests remain green.
- The full Checkpoint 3 script passes.
- README clearly labels authentication, storage, approvals, and all logistics
  effects as local/demo/synthetic.

## 22. Minimum manual smoke test

Start the API with an explicit local secret:

```bash
export DEMO_APPROVER_SECRET='local-demo-only-change-me'
python3 -m uvicorn apps.api.main:app --reload
```

Start the run:

```bash
curl -X POST http://127.0.0.1:8000/v1/runs \
  -H 'content-type: application/json' \
  -d '{"order_id":"ORD-8842","mode":"enforce","scenario":"adversarial"}'
```

Read the returned approval:

```bash
curl http://127.0.0.1:8000/v1/approvals/APR-REPLACE-ME
```

Approve it:

```bash
curl -X POST http://127.0.0.1:8000/v1/approvals/APR-REPLACE-ME \
  -H 'content-type: application/json' \
  -H 'X-Demo-Approver-Secret: local-demo-only-change-me' \
  -d '{
    "decision":"approve",
    "approver_label":"DEMO-APPROVER-OPS-1",
    "comment":"Synthetic demo approval.",
    "expected_version":1,
    "idempotency_key":"approval-smoke-001"
  }'
```

Finally, read the run, events, and decisions. The run must be completed and the
trace must show the approval before confirmation.

## 23. Beginner implementation guidance

Implement one phase at a time. Do not begin with the endpoint. The endpoint is
the final thin wrapper around already-tested service behavior.

When debugging, inspect these layers in order:

```text
domain state -> approval validator -> store transition -> policy decision
-> governed tool -> agent method -> orchestrator -> RunService -> FastAPI
```

If a test fails, fix the lowest failing layer before continuing upward. Avoid
editing several layers at once merely to make one end-to-end test pass.

The most important rule is: approving an exception does not directly execute
the booking. It only adds a narrowly bound fact that the policy engine must
validate during a fresh confirmation attempt.
