# Checkpoint 8 Implementation Plan — Durable Storage and DynamoDB Parity

**Plan version:** 1.0  
**Created:** 19 September 2026  
**Checkpoint state:** Complete  
**Depends on:** Completed Checkpoints 1–7  
**Verified baseline commit:** `e8e8ab4`  
**Next checkpoint after completion:** Checkpoint 9 — Offline Strands Runtime

### Implementation progress — 19 September 2026

- Added database-independent snapshot, transition, replay, effect-receipt, and repository contracts.
- Added explicit versioned codecs for state, events, decisions, approvals, ledger heads, replay records, and effect receipts.
- Added validated deterministic DynamoDB key construction.
- Changed the memory store to own detached copies and enforce optimistic state revisions.
- Injected the repository protocol into the governor, orchestrator, observer, and run service while retaining the memory adapter.
- Added 27 storage/model/keyspace/codec/snapshot tests.
- Verified `161 passed, 2 skipped` without a live Cedar sidecar.
- Verified the complete live-Cedar gate: `163 passed`, 2 Rust tests, three hero journeys, and unchanged 22/22 functional digest.

DynamoDB Local 2.5.4 is now pinned by digest, the single-table adapter and
effect-receipt path are implemented, and restart/concurrency tests are green.
The final live-Cedar evaluation and release evidence gate passed on 19 September 2026.

## 1. Objective

Replace process-local run, approval, effect, and ledger storage with a durable DynamoDB-compatible repository while preserving every behavior established by Checkpoints 1–7.

At completion:

- pending and completed runs survive application restart;
- approvals survive restart and resolve against the original trace;
- two service instances cannot both win the same approval or append the same ledger sequence;
- event sequence and hash-head updates are atomic;
- approval and tool idempotency survive restart;
- synthetic confirmation, cancellation, and notification effects execute exactly once across retries;
- clean and tampered ledger verification behaves exactly as before;
- the in-memory store remains available for fast unit tests and offline fallback;
- the active storage mode is selected at startup and disclosed in health, evaluation, dashboard, and release evidence; and
- Cedar remains authoritative and all Checkpoint 1–7 behavior remains green.

This checkpoint changes persistence and concurrency semantics. It must not change product decisions, policies, API paths, dashboard behavior, or the demonstrated logistics journey.

## 2. Verified starting state

The repository is clean at commit `e8e8ab4` and Checkpoint 7 is complete.

Local verification without a running Cedar sidecar:

```text
python3 -m pytest -q
134 passed, 2 skipped in 8.58s
```

Checkpoint 7 completion evidence records the full live-Cedar gate:

```text
Python tests with live Cedar: 136 passed
Rust tests:                  2 passed
Evaluation:                 22/22 passed
Attack detection:           10/10
Benign/boundary:             12/12
False positives:             0/12
Functional digest:          sha256:99d44f22a833007bd2caa5121c2330b7222537633501590b1b43266c04b11120
```

Current environment discovery:

| Component | Current state |
|---|---|
| Docker | Installed, version 29.7.2 |
| Docker Compose | Installed, version 5.5.0 |
| Java | Installed, OpenJDK 25 |
| Python | Installed, 3.14.6 |
| Cargo | Installed, 1.98.1 |
| AWS CLI | Not installed |
| `boto3` | Not installed |

The absence of AWS CLI is not a blocker. Checkpoint 8 should use repository-owned Python setup scripts and the AWS SDK.

## 3. Non-negotiable compatibility with Checkpoints 1–7

| Existing checkpoint | Contract Checkpoint 8 must preserve |
|---|---|
| 1 — Walking skeleton | Four agents, ten registered tools, bounded orchestration, trace isolation, CLI/API paths and outputs |
| 2 — Governed MVP | One decision per tool attempt, stable outcomes and reason codes, guide-back, shadow/enforce behavior |
| 3 — Approval | Binding to trace/action/state/policy, approve/reject/expiry, fresh authorization, exact-once confirmation/cancellation/notification |
| 4 — Ledger | Canonical hash payload, ordered append, stored head, idempotency, verification, first bad sequence |
| 5 — Dashboard | Existing endpoint paths and field meanings, projection data, approval and integrity controls |
| 6 — Evaluation | 22-case catalogue, functional digest, exact denominators, deterministic output and release evidence |
| 7 — Cedar | Cedar-authoritative decisions, bundle identity, fail-closed behavior, Python reference fallback, policy parity |

### Compatibility rules

- Existing API paths remain unchanged.
- Existing response fields retain their meaning; storage disclosures may be additive.
- Event hash calculation and canonical JSON remain byte-for-byte compatible.
- Existing event order and human-readable summaries remain stable.
- Cedar request construction and result mapping do not gain storage-specific logic.
- Agents and the governor depend on a storage protocol, not on `boto3` or DynamoDB types.
- The DynamoDB adapter must not silently fall back to memory after startup failure.
- A storage error during a protected effect fails closed and returns a controlled service error.
- The in-memory adapter must pass the same storage contract tests as DynamoDB.
- Checkpoint 6 and 7 evidence files are never overwritten. Checkpoint 8 writes separate artifacts.

## 4. Scope

### Included

- A storage/repository protocol independent of DynamoDB.
- Removal of correctness dependence on shared live Python object references.
- Explicit optimistic revisions for trajectory state.
- Versioned serializers/deserializers for all persisted domain types.
- A refactored in-memory adapter conforming to the new protocol.
- A DynamoDB adapter using official AWS SDK calls.
- Official DynamoDB Local through a pinned Docker image for integration tests.
- Atomic event, head, state, decision, approval, replay, and effect-receipt writes.
- Strongly consistent authoritative reads.
- Distributed approval concurrency using DynamoDB conditions rather than a process-local lock.
- Durable synthetic effect receipts for exact-once retry behavior.
- Restart/recovery and failure-injection tests.
- Storage configuration, readiness reporting, evaluation evidence, and release evidence.
- A complete `scripts/run_checkpoint_8.sh` gate.

### Explicitly excluded

- Strands Agents or Bedrock.
- Lambda, API Gateway, Amplify, Step Functions, or EventBridge.
- Multi-Region/global tables.
- DynamoDB Streams.
- Production tenant management or data migration tooling.
- Real logistics effects.
- S3 archive, Object Lock, or an immutability claim.
- Runtime table creation by the application process.
- Manual production database administration.

## 5. Architecture decision

### 5.1 Runtime shape

```text
CLI / FastAPI / dashboard
          |
          v
      RunService
          |
          v
     TraceRepository protocol
       /                 \
      v                   v
MemoryTraceRepository   DynamoTraceRepository
fast/offline/tests      local Docker or managed AWS
                             |
                             v
                    one DynamoDB table
```

The hash-chain functions remain in `packages/ledger`. Persistence moves into a new `packages/storage` package. `packages.ledger.MemoryTraceStore` may remain as a compatibility re-export during this checkpoint, but new application code must type against the protocol.

### 5.2 Critical refactor: no live mutable store objects

The current memory store returns a live `TrajectoryState` through `get_state_for_update`. That works only because all callers share one process and one object. A durable repository cannot provide those semantics safely.

Introduce an explicit stored snapshot:

```python
@dataclass(frozen=True, slots=True)
class StoredTrace:
    state: TrajectoryState
    revision: int


class TraceRepository(Protocol):
    def create_run(self, state: TrajectoryState) -> StoredTrace: ...
    def load_trace(self, trace_id: str, *, consistent: bool = True) -> StoredTrace: ...
    def commit_transition(self, transition: TraceTransition) -> StoredTrace: ...
    def get_events(self, trace_id: str) -> list[TraceEvent]: ...
    def get_decisions(self, trace_id: str) -> list[Decision]: ...
    def get_head(self, trace_id: str) -> LedgerHead: ...
    def verify_trace(self, trace_id: str) -> VerificationResult: ...
    def get_approval(self, approval_id: str) -> ApprovalRecord: ...
    def list_approvals(...) -> list[ApprovalRecord]: ...
    def reset_demo_namespace(self) -> int: ...
```

`TraceTransition` stages one atomic business transition:

```text
trace ID and expected revision
updated state snapshot
zero or more new ordered events
zero or more decisions
zero or more approval mutations
zero or more idempotency/replay records
zero or more durable synthetic effect receipts
```

The memory adapter must clone inputs and enforce the same revision conditions. No caller may keep a store-owned mutable object.

### 5.3 Why the refactor comes before DynamoDB

Adding a DynamoDB class while retaining `get_state_for_update` would create hidden lost-update and restart bugs. The service must first make its mutation boundaries explicit; only then can DynamoDB conditions enforce them across processes.

## 6. DynamoDB single-table design

### 6.1 Table

Recommended logical name:

```text
manifest-traces-<environment>
```

Primary key:

```text
PK  string partition key
SK  string sort key
```

Use on-demand billing for the managed demo table. Checkpoint 8 needs no secondary index if pointer items are used as described below.

### 6.2 Item layout

| PK | SK | Purpose |
|---|---|---|
| `TRACE#<trace_id>` | `META` | Versioned state snapshot, revision, run status, mode, policy/storage identity |
| `TRACE#<trace_id>` | `HEAD` | Latest event sequence, count, and hash |
| `TRACE#<trace_id>` | `EVENT#000000000001` | One canonical ledger event |
| `TRACE#<trace_id>` | `DECISION#<created_at>#<decision_id>` | One full typed decision |
| `TRACE#<trace_id>` | `APPROVAL#<approval_id>` | Approval record and version |
| `TRACE#<trace_id>` | `REPLAY#EVENT#<key_hash>` | Event idempotency fingerprint and result reference |
| `TRACE#<trace_id>` | `REPLAY#APPROVAL#<key_hash>` | Approval command fingerprint and result reference |
| `TRACE#<trace_id>` | `EFFECT#<key_hash>` | Durable synthetic effect fingerprint and stored result |
| `APPROVAL#<approval_id>` | `POINTER` | Strongly readable pointer to the owning trace |
| `DEMO#<namespace>` | `TRACE#<trace_id>` | Namespace-scoped trace pointer for safe reset/listing |
| `DEMO#<namespace>` | `APPROVAL#<created_at>#<approval_id>` | Namespace-scoped approval pointer for listing |

Sequence values are zero-padded so lexical order matches numeric order.

### 6.3 State document

`META` stores a JSON document for current trajectory state but excludes `events` and `decisions`; those collections are separate items. `load_trace` hydrates the state with queried events and decisions so existing summaries and projections keep working.

Required metadata:

```text
record_type = TRACE_META
state_schema_version = trace-state-v1
revision
trace_id
order_id
status
mode
scenario
policy_version
policy_engine
policy_bundle_hash
created_at
updated_at
state_json
```

### 6.4 Serialization rules

- Never use pickle.
- Use explicit versioned codecs.
- Encode datetimes as UTC ISO-8601 strings.
- Encode enums as their stable string values.
- Encode `frozenset` values as sorted lists.
- Reconstruct nested dataclasses explicitly and reject unknown schema versions.
- Preserve integers as integers; currency remains minor-unit integer values.
- Store JSON strings rather than arbitrary DynamoDB nested numbers to avoid accidental `Decimal` behavior changing hashes or models.
- Validate every item against a conservative size limit before calling DynamoDB.
- Never include secrets, Cedar transport details, raw PII, or approval authentication headers.

The event document must reconstruct the exact `TraceEvent` used by the existing canonical hash function. Checkpoint 8 must not introduce a second event canonicalization format.

## 7. Atomic operations and invariants

### 7.1 Create trace

One transaction creates:

1. `META` at revision 0, conditioned on absence.
2. `HEAD` at genesis, conditioned on absence.
3. The demo namespace trace pointer, conditioned on absence.

Duplicate trace IDs fail with the existing domain error.

### 7.2 Append event and update state

One `TransactWriteItems` request:

1. Puts the new event if its key does not exist.
2. Updates `HEAD` only if the stored sequence/hash equal the caller's expected sequence/hash.
3. Updates `META` only if its revision equals the caller's expected revision, then increments the revision.
4. Puts the event replay record if an idempotency key exists.
5. Adds any decision or approval mutation belonging to the same transition.

The event sequence, previous hash, event hash, state revision, and replay record either all commit or none commit.

### 7.3 Event idempotency

Do not rely only on DynamoDB's transaction client token. The service retains a permanent replay item containing:

```text
idempotency key hash
caller-field fingerprint
event sequence
event ID
event hash
```

The same key and fingerprint return the original event. The same key with different content raises `LedgerIdempotencyConflictError`.

### 7.4 Approval claim

Approval correctness must no longer depend on `RunService._approval_resolution_lock`.

The winning approval request atomically:

1. Checks approval status is `pending_approval`.
2. Checks approval version equals `expected_version`.
3. Checks the command replay key is absent or identical.
4. Updates approval status/version/decision metadata.
5. Updates the bound trace snapshot with an optimistic revision condition.
6. Appends the approval decision event and advances the hash head.
7. Writes the approval replay record.

Only one approve/reject request may satisfy the conditions. A second service instance receives a typed version/not-pending result or an idempotent replay result.

### 7.5 Recovery after approval claim

A process can fail after the approval record commits but before the resumed carrier/communications steps finish. Add an explicit resolution phase, for example:

```text
claimed -> effect_applied -> workflow_completed
```

On a replay or recovery request:

- approved plus incomplete run resumes idempotently;
- rejected/expired plus incomplete run finishes cancellation idempotently;
- completed resolution returns the stored result without running effects again.

The recovery path uses the original trace, prepared action, action hash, state hash, policy version, approval version, and deterministic idempotency keys.

### 7.6 Durable synthetic effects

The current mock tools keep effects in Python dictionaries. That is insufficient after restart. Introduce an `EffectReceiptStore` used by `MockLogisticsTools`.

For each reversible or commitment effect, persist:

```text
trace_id
tool_name
idempotency_key hash
argument fingerprint
result JSON
created_at
```

Behavior:

- absent key: create the result once;
- identical replay: return the stored result;
- different fingerprint: raise `IdempotencyConflictError`;
- confirmation and cancellation for the same prepared action remain mutually exclusive.

This proves exact-once behavior for the prototype's synthetic effects. It is not a claim that arbitrary real carrier APIs can participate in a DynamoDB transaction.

### 7.7 Read consistency

Use strongly consistent reads for `META`, `HEAD`, events, decisions, approval pointer, and approval records in authorization, approval, resume, and verification paths. Dashboard polling may later use weaker reads only if it is explicitly labelled stale; Checkpoint 8 should keep all existing API reads strong for simplicity and correctness.

### 7.8 Verification

`verify_trace` must:

1. Strongly read `HEAD`.
2. Strongly query all `EVENT#` items in ascending sort-key order.
3. Deserialize events.
4. Run the existing read-only `verify_chain` function.

The verifier never repairs, rehashes, or updates the chain.

### 7.9 Disposable tamper demo

The guarded tamper operation may update only one terminal disposable event payload without updating its event hash or `HEAD`. It remains disabled by default. It must reject non-terminal traces and cross-namespace targets.

### 7.10 Safe reset

Reset operates only on the configured `MANIFEST_DEMO_NAMESPACE`:

1. Query the `DEMO#<namespace>` pointer collection.
2. Resolve only the referenced traces and approvals.
3. Delete their items in bounded batches.
4. Delete the namespace pointers.
5. Return the exact removed run count.

Reject an empty namespace and reserved names such as `prod` unless an explicit test-only override is set. Never scan and delete an entire table as part of the API reset route.

## 8. Error handling and retry policy

Add domain-level errors so AWS details do not leak into API responses:

```text
StorageConfigurationError
StorageUnavailableError
TraceRevisionConflictError
TracePersistenceError
ApprovalPersistenceConflictError
EffectReceiptConflictError
SerializationVersionError
ItemSizeLimitError
```

Map DynamoDB failures deliberately:

| DynamoDB condition | Manifest behavior |
|---|---|
| Conditional check or transaction cancellation caused by stale revision | Typed conflict; reload before any bounded retry |
| Approval status/version condition fails | Approval version/not-pending result; never retry as a new decision |
| Idempotency fingerprint differs | Existing idempotency conflict error |
| Throttle or transient transport failure | Bounded SDK retry, then controlled storage-unavailable error |
| Invalid item or serialization | Fail closed before the write |
| Missing table or invalid credentials | Readiness fails; service must not switch to memory silently |

Use bounded standard SDK retries with jitter. Never retry an unknown protected-effect outcome without first reading its durable effect receipt.

## 9. Configuration and dependency changes

### 9.1 Environment variables

Add to `.env.example`:

```text
MANIFEST_STORAGE_BACKEND=memory
MANIFEST_TRACE_TABLE_NAME=manifest-traces-local
MANIFEST_DEMO_NAMESPACE=checkpoint8-local
MANIFEST_DYNAMODB_ENDPOINT_URL=http://127.0.0.1:8000
MANIFEST_DYNAMODB_REGION=us-east-1
MANIFEST_DYNAMODB_CONNECT_TIMEOUT_MS=500
MANIFEST_DYNAMODB_READ_TIMEOUT_MS=1000
MANIFEST_DYNAMODB_MAX_ATTEMPTS=3
```

Rules:

- `MANIFEST_STORAGE_BACKEND` accepts only `memory` or `dynamodb`.
- An endpoint override is for local/test use and is displayed in health as local, without exposing credentials.
- Managed AWS mode uses the normal AWS credential provider chain and omits endpoint override.
- Do not add real AWS access keys to `.env`.

### 9.2 Dependencies

- Add and pin a tested `boto3`/`botocore` version.
- Keep Docker and DynamoDB Local outside the Python package.
- Do not add a broad AWS framework in this checkpoint.
- Record the DynamoDB Local image version/digest in Checkpoint 8 release evidence.

### 9.3 Startup factory

Add `build_trace_repository_from_env()` and inject the resulting repository and effect store into `build_run_service()`.

Health must report at least:

```text
storage_backend
storage_mode: memory | dynamodb_local | dynamodb_aws
table_name
demo_namespace
storage_ready
consistent_reads
state_schema_version
ledger_schema_version
```

Do not return the endpoint URL, AWS account ID, credential source, or secret values.

## 10. Repository changes

Recommended files:

```text
packages/storage/
  __init__.py
  protocol.py
  models.py
  codec.py
  keyspace.py
  memory.py
  dynamodb.py
  factory.py
  effects.py

packages/ledger/
  canonical.py              # unchanged hashing contract
  verifier.py               # unchanged read-only verifier
  memory_store.py           # compatibility wrapper or moved implementation

infrastructure/local/dynamodb/
  compose.yaml
  README.md

scripts/
  create_checkpoint_8_table.py
  check_dynamodb_ready.py
  reset_checkpoint_8_namespace.py
  run_checkpoint_8.sh

tests/storage/
  test_codec.py
  test_keyspace.py
  test_memory_contract.py
  test_dynamodb_contract.py
  test_dynamodb_concurrency.py
  test_dynamodb_recovery.py
  test_dynamodb_effects.py

tests/integration/
  test_checkpoint_8_restart.py
  test_checkpoint_8_approval_race.py
  test_checkpoint_8_verification.py

docs/results/
  checkpoint-8-dynamodb-evaluation.json
  checkpoint-8-dynamodb-evaluation.md

docs/releases/
  checkpoint-8-dynamodb-local.json
```

The final filenames may vary, but the responsibilities and evidence must remain separated.

## 11. Implementation phases

### Phase 8.0 — Freeze baseline and preflight

1. Confirm `git status` is clean or inventory all user changes.
2. Run `python3 -m pytest -q`.
3. Run `./scripts/run_checkpoint_7.sh` with live Cedar.
4. Record Checkpoint 7 functional digest and bundle hash.
5. Verify `docker info` and `docker compose version`.
6. Add the pinned DynamoDB SDK dependency and local Docker image decision.

**Gate:** No storage refactor begins until the existing baseline is green.

### Phase 8.1 — Define repository and codec contracts

1. Add `StoredTrace`, `TraceTransition`, storage protocol, and effect-receipt protocol.
2. Implement explicit versioned codecs for every persisted type.
3. Add round-trip, invalid-version, UTC datetime, enum, set-order, and size-limit tests.
4. Define the exact DynamoDB key factory and item builders.

**Gate:** All codec and keyspace unit tests pass without DynamoDB.

### Phase 8.2 — Refactor memory storage first

1. Implement the new protocol with cloned snapshots and optimistic revisions.
2. Remove application dependence on `get_state_for_update` and live store identity checks.
3. Convert event/decision/approval writes into explicit transitions.
4. Add durable-style effect receipts to the memory adapter.
5. Run every Checkpoint 1–7 test against memory.

**Gate:** Functional digest remains identical to Checkpoint 7 in memory mode.

### Phase 8.3 — Add DynamoDB Local infrastructure

1. Add pinned Docker Compose configuration with a named data volume.
2. Add a readiness script.
3. Add an idempotent table-creation script for `PK` and `SK` string keys with on-demand billing.
4. Ensure local dummy credentials exist only in the Compose/test environment.
5. Document start, stop, inspect, and reset commands.

**Gate:** The table can be created twice safely and survives container restart.

### Phase 8.4 — Implement core DynamoDB repository

1. Implement configuration validation and bounded client settings.
2. Implement create/load operations with strong reads.
3. Implement conditional transition commits.
4. Implement event/decision queries and state hydration.
5. Implement head reads and verification.
6. Map AWS exceptions to domain errors.

**Gate:** Memory and DynamoDB pass the same core repository contract suite.

### Phase 8.5 — Implement approval and effect durability

1. Add approval pointer and namespace pointer items.
2. Replace lock-based correctness with conditional approval claims.
3. Persist approval replay fingerprints.
4. Add resolution phases and restart recovery.
5. Move mock effect idempotency to the effect-receipt store.
6. Prove confirmation/cancellation mutual exclusion and notification exact-once behavior.

**Gate:** Two independently constructed service instances produce one approval winner and one set of effects.

### Phase 8.6 — Wire application, API, health, and dashboard

1. Add storage factory selection.
2. Inject repository/effect store into governor, orchestrator, run service, and tools.
3. Preserve all endpoint paths and response meanings.
4. Add truthful health/storage fields.
5. Ensure a browser refresh after service restart reloads the same trace.
6. Ensure the dashboard clearly reports disconnected/storage-unavailable state.

**Gate:** The complete hero journey works through the API/dashboard with DynamoDB Local.

### Phase 8.7 — Failure injection and regression

Test failures at these boundaries:

- stale state revision before event append;
- competing writers for the same event sequence;
- process stop after approval claim but before resume;
- process stop after effect receipt but before state transition commit;
- duplicate approval after process restart;
- DynamoDB unavailable before a protected effect;
- malformed or oversized stored item;
- tampered event, deleted middle event, reordered event, duplicated event, and truncated tail;
- reset requested with empty or forbidden namespace.

**Gate:** No failure produces duplicate commitment, negative reserved spend, forked head, or silent memory fallback.

### Phase 8.8 — Evaluation and release evidence

1. Run the 22-case evaluation with Cedar plus DynamoDB Local.
2. Compare functional digest with Checkpoint 7.
3. Record storage latency separately from Cedar evaluation latency.
4. Generate Checkpoint 8 JSON/Markdown evidence.
5. Generate a release manifest identifying Cedar, DynamoDB Local image/digest, table schema, state schema, ledger schema, and limitations.
6. Add `scripts/run_checkpoint_8.sh` as the single release gate.

**Gate:** Checkpoint 8 evidence is reproducible and earlier evidence is unchanged.

## 12. Test plan

### 12.1 Unit tests

- Every domain type round-trips through the versioned codec.
- Naive datetimes, unknown enums, unsupported schema versions, and invalid data fail.
- Key construction is deterministic and rejects unsafe identifiers.
- Sequence sort keys preserve numeric order.
- State snapshots exclude event/decision history.
- Event deserialization preserves the existing canonical hash.
- Item size guard rejects oversized writes before the SDK call.
- DynamoDB error mapping produces controlled domain errors.
- Storage factory rejects unknown backend values and missing configuration.

### 12.2 Shared repository contract suite

Run the same tests against memory and DynamoDB Local:

- create and load trace;
- reject duplicate trace;
- append sequential events;
- return identical event replay;
- reject conflicting event replay;
- reject stale revision;
- reject stale head sequence/hash;
- store and list decisions in deterministic order;
- create, retrieve, list, update, and expire approvals;
- persist approval replay;
- persist and replay effect receipts;
- isolate two traces;
- verify clean chain;
- detect all supported tamper cases;
- reset one namespace without touching another.

### 12.3 DynamoDB integration tests

- Table creation is idempotent.
- Container restart retains table data and a pending trace.
- Two repository instances race the same append; exactly one wins.
- Two service instances submit the same approval; one applies and one is an idempotent replay.
- Approve versus reject race has one winner.
- Failure after approval claim recovers through a newly constructed service.
- Failure after durable effect receipt does not duplicate confirmation or notification.
- Reads immediately after successful writes see the committed values.
- Transaction cancellation does not leave partial event/head/state changes.
- Missing table and unavailable endpoint fail readiness and protected effects closed.

### 12.4 API and dashboard tests

- Start adversarial enforce and capture pending approval.
- Destroy/rebuild the application service object without resetting DynamoDB.
- Read the same run, decisions, events, projection, and approval.
- Approve through the API and complete the original trace.
- Rebuild the service again and verify completed state and chain.
- Refresh dashboard using `?trace_id=<id>` and show the persisted trace.
- Test reject and expiry after restart.
- Test guarded disposable tampering and verification.
- Confirm reset affects only the configured namespace.

### 12.5 Security tests

- No AWS credentials or local dummy secrets appear in events, API, logs, health, or evidence.
- Table name and namespace are validated.
- Tamper route remains disabled by default and requires its own secret.
- Approval secret remains server-side.
- State JSON contains no raw PII or Cedar request transport data.
- The app role cannot create/delete tables in managed mode.
- Storage failure cannot turn a deny/escalate into an allow.

## 13. Integration checks with previous checkpoints

| Gate | Required Checkpoint 8 verification |
|---|---|
| Checkpoint 1 | Benign CLI run completes twice; all four agents and ten registered tools remain traceable; two traces remain isolated |
| Checkpoint 2 | Adversarial shadow and enforce outputs remain identical; provenance and cold-chain guide-back still occur before effects |
| Checkpoint 3 | Approve, reject, expiry, stale version, wrong binding, replay, and concurrent decisions preserve exact-once results across restart |
| Checkpoint 4 | Existing event hash vectors remain unchanged; clean/tampered verification and first-bad-sequence behavior pass after persistence |
| Checkpoint 5 | Dashboard uses the existing APIs, survives backend service reconstruction, and displays actual persisted projection/approval/integrity data |
| Checkpoint 6 | All 22 evaluation cases pass; exact denominators and functional digest remain unchanged; new storage latency is reported separately |
| Checkpoint 7 | Live Cedar remains authoritative; 136-test gate and Rust tests pass; policy bundle hash and authorization behavior remain unchanged |

No checkpoint is considered preserved merely because its unit tests pass. The three hero journeys must also pass through DynamoDB Local with live Cedar.

## 14. Checkpoint 8 release script

`scripts/run_checkpoint_8.sh` should perform this bounded sequence:

```text
1. Verify required tools and clean/known repository state.
2. Start pinned DynamoDB Local container.
3. Wait for readiness.
4. Create/validate the Checkpoint 8 table.
5. Build and start the pinned Cedar sidecar.
6. Export Cedar + DynamoDB Local configuration.
7. Run Rust tests.
8. Run the complete Python suite, including live Cedar and DynamoDB tests.
9. Run benign enforce.
10. Run adversarial shadow.
11. Run adversarial enforce with approval.
12. Run restart/recovery and concurrency smoke tests.
13. Run clean/tampered verification.
14. Generate Checkpoint 8 evaluation evidence.
15. Compare functional digest to Checkpoint 7.
16. Generate Checkpoint 8 release manifest.
17. Stop only processes/containers started by the script.
```

The script must use a unique demo namespace so it cannot delete a developer's unrelated local traces.

## 15. External setup guidance for the project owner

### 15.1 What you need to do now

You do **not** need to create an AWS DynamoDB table yet.

Before implementation starts, verify only:

```bash
docker info
docker compose version
```

If `docker info` fails, start the Docker service or Docker Desktop. Do not paste Docker or system credentials into the repository.

The implementation will add the Compose file, Python SDK dependency, and table setup scripts. After those files exist, the normal local workflow will be approximately:

```bash
docker compose -f infrastructure/local/dynamodb/compose.yaml up -d
python3 scripts/check_dynamodb_ready.py
python3 scripts/create_checkpoint_8_table.py
./scripts/run_checkpoint_8.sh
```

Do not run these commands until the referenced files are implemented.

### 15.2 Local credentials

DynamoDB Local requires credential-shaped values but they do not need to be real AWS credentials. The Compose/test environment may use obvious dummy values such as `local` and a local-only region. Never reuse real AWS access keys for DynamoDB Local.

### 15.3 Optional managed AWS smoke test

The local DynamoDB integration is sufficient for Checkpoint 8. A managed AWS smoke test is optional and should happen only after local acceptance is green.

If you want the managed smoke test, you will need to:

1. Choose the same AWS account and Region intended for the later demo stack.
2. Authenticate through AWS SSO, a named profile, or another normal AWS credential-chain source.
3. Confirm the identity can create the development table or ask an administrator to create it from the repository template/script.
4. Provide only the profile name and Region to the process—not credential values.
5. Set a clear development table name such as `manifest-traces-dev`.
6. Keep the table on-demand and tagged as synthetic hackathon data.
7. Run one isolated smoke namespace and then retain or remove it according to the team's cleanup plan.

Do not manually create a differently shaped table in the AWS console. The repository-owned definition must remain the source of truth.

### 15.4 Suggested IAM separation

The setup/deployment identity may need:

```text
dynamodb:CreateTable
dynamodb:DescribeTable
dynamodb:TagResource
dynamodb:UpdateContinuousBackups   # only if managed smoke enables PITR
dynamodb:DeleteTable               # teardown identity only
```

The application runtime should be limited to the exact table ARN and the data-plane operations it uses:

```text
dynamodb:DescribeTable
dynamodb:GetItem
dynamodb:PutItem
dynamodb:UpdateItem
dynamodb:DeleteItem
dynamodb:Query
dynamodb:BatchWriteItem
dynamodb:TransactGetItems
dynamodb:TransactWriteItems
```

Do not grant table creation/deletion to the runtime role. Final permissions must be generated from the actual implemented calls; remove unused actions.

### 15.5 Table settings for optional managed smoke

- Partition key: `PK` (String).
- Sort key: `SK` (String).
- Capacity: on-demand.
- Encryption: DynamoDB's default encryption is sufficient for synthetic demo data.
- Point-in-time recovery: recommended for the later persistent demo stack, optional for this short Checkpoint 8 smoke.
- TTL: do not enable it for ledger or approval items in this checkpoint.
- Streams: disabled; EventBridge/stream fan-out is a later checkpoint.
- Deletion protection: decide based on whether the table is disposable or retained for the demo; document the choice.

## 16. Operational and security guidance

- Use one Region only for Checkpoint 8.
- Never store credentials, approval secrets, or Cedar service secrets in DynamoDB records.
- Never log full `state_json` or approval comments.
- Use table and namespace prefixes that visibly identify synthetic demo data.
- Keep the tamper demo on a disposable terminal trace.
- Call the ledger "tamper-evident," not immutable.
- Keep DynamoDB Local bound to loopback for local development.
- Pin the Docker image version/digest after the initial compatibility test; do not use a floating `latest` tag in release evidence.
- Do not enable automatic memory fallback in a process configured for DynamoDB.

## 17. Rollback and fallback

### Rollback

- Storage selection is fixed at startup.
- The last known-good Checkpoint 7 memory mode remains untouched.
- If the DynamoDB adapter regresses behavior, revert the adapter/refactor as one checkpoint; do not mix old mutable-state code with new repository code.
- Existing Checkpoint 6/7 evidence remains immutable.

### Fallback

- `MANIFEST_STORAGE_BACKEND=memory` remains the disclosed offline path.
- Local DynamoDB is the authoritative Checkpoint 8 proof if managed AWS access is unavailable.
- A file-backed store does not satisfy Checkpoint 8 and should not be added unless needed for emergency recovery.
- If approval recovery or exact-once effects remain unreliable, Checkpoint 8 is not complete even if basic CRUD works.

## 18. Definition of done

Checkpoint 8 is complete only when all of the following are true:

- [x] Storage protocol and explicit optimistic revisions replace live mutable store semantics.
- [x] Memory and DynamoDB adapters pass the same contract suite.
- [x] A pending run survives container/application restart.
- [x] A new service instance resumes and completes the original approved trace.
- [x] Approve/approve and approve/reject races have one durable winner.
- [x] Confirmation, cancellation, and notification remain exact-once across retries and restart.
- [x] Event append, head update, state update, and replay record are atomic.
- [x] Clean verification passes after restart.
- [x] Edit, delete, reorder, duplicate, and tail truncation cases are detected or rejected.
- [x] Namespace reset cannot affect another namespace.
- [x] Health truthfully reports the selected durable or memory storage mode.
- [x] All Checkpoint 1–7 regression gates pass.
- [x] Live Cedar remains authoritative and its bundle hash is unchanged.
- [x] The 22-case functional digest matches Checkpoint 7.
- [x] Checkpoint 8 evaluation and release evidence are generated separately.
- [x] README and `.env.example` document local start, stop, reset, restart, and fallback.
- [x] No credentials, raw PII, or secret values are committed or persisted.

Suggested explicit operator tag after review: `v0.8.0-dynamodb-local`.

## 19. First implementation task

Begin with **Phase 8.1 only**:

1. Add the storage protocol and transition/snapshot models.
2. Add explicit versioned serialization with round-trip tests.
3. Add deterministic key construction tests.
4. Do not add `boto3` calls until those contracts pass.

This isolates the hardest correctness decision—the persistence boundary—before introducing service configuration or network behavior.

## 20. Official AWS references

- [Deploying DynamoDB locally](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBLocal.DownloadingAndRunning.html)
- [DynamoDB transactions](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transaction-apis.html)
- [TransactWriteItems API](https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_TransactWriteItems.html)
- [DynamoDB condition expressions](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.OperatorsAndFunctions.html)
- [DynamoDB read consistency](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.ReadConsistency.html)
- [DynamoDB composite primary keys](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.CoreComponents.html)
- [DynamoDB data-modeling building blocks](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/data-modeling-blocks.html)
- [DynamoDB encryption at rest](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/EncryptionAtRest.html)
