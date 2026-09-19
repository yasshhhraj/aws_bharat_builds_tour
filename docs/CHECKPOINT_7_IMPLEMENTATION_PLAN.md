# Checkpoint 7 Implementation Plan — Cedar Authorization Parity

**Plan version:** 1.0  
**Created:** 19 September 2026  
**Checkpoint state:** Planned; implementation not started  
**Depends on:** Completed Checkpoints 1–6  
**Required baseline:** 119 passing tests and 22/22 passing Checkpoint 6 evaluation cases  
**Next checkpoint after completion:** Checkpoint 8 — Durable Storage and DynamoDB Parity

## 1. Objective

Checkpoint 7 replaces the Python reference engine as the authoritative policy decision point for the configured demo path with a real Cedar authorizer, while preserving every established Manifest contract from Checkpoints 1–6.

At completion:

- every registered tool proposal is translated into a typed Cedar principal-action-resource-context request;
- a versioned Cedar schema and policy bundle are validated at startup;
- Cedar determines whether the proposal is authorized;
- determining Cedar policy IDs are translated into Manifest's stable `ALLOW`, `GUIDE`, `BLOCK`, or `ESCALATE` signals;
- Cedar errors, diagnostics, timeouts, malformed responses, unknown policy IDs, and version mismatches fail closed;
- the same shadow, enforce, guide-back, approval, exact-once, ledger, API, dashboard, and evaluation behavior remains intact;
- health, traces, evaluation evidence, and the release manifest truthfully disclose whether Cedar or the Python reference engine is active; and
- the Python engine remains available as an explicit offline fallback and conformance oracle, never as a silent replacement for Cedar.

This checkpoint changes authorization implementation, not product behavior.

## 2. Verified starting state

The implementation baseline is commit `a8a17c5` on `main`. At plan creation:

```text
python3 -m pytest -q
119 passed in 8.54s
```

Checkpoint 6 evidence reports:

```text
Evaluation cases:       22/22 passed
Attack detection:       10/10
Benign cases:           12/12
False positives:        0/12
Guide-back success:     2/2
Policy engine:          python_reference
Policy version:         demo-v1
Storage:                memory_hash_chain
Runtime:                deterministic
Deployment:             local
```

The current working tree contains modified generated Checkpoint 6 evidence files. Checkpoint 7 implementation must preserve these user changes. It must not reset, discard, overwrite, or silently commit them.

## 3. Non-negotiable compatibility with Checkpoints 1–6

| Existing checkpoint | Contract that Checkpoint 7 must preserve |
|---|---|
| 1 — Walking skeleton | Four agents, ten registered tools, deterministic fixtures, bounded orchestration, trace isolation, CLI and API paths |
| 2 — Governed MVP | One decision for every tool attempt, six policy families, stable reason codes, guide-back, shadow/enforce behavior |
| 3 — Approval | Bound approval, approve/reject/expiry, fresh authorization after approval, exact-once confirmation/cancellation/notification |
| 4 — Ledger | Event order, idempotent append, canonical hash chain, clean/tampered verification, first bad sequence |
| 5 — Dashboard | Existing API fields, real API-backed panels, approval controls, provenance, spend/risk, integrity state |
| 6 — Evidence | 22-case catalogue, deterministic functional digest, exact denominators, release disclosure, browser evidence, generated artifacts |

### Compatibility rules

- Existing API paths remain unchanged.
- Existing response fields retain their meanings; new fields are additive.
- Existing reason codes and human-readable meanings remain stable.
- Existing outcome precedence remains `BLOCK > ESCALATE > GUIDE > ALLOW`.
- Existing same-outcome family order remains ownership, provenance, cold chain, spend, separation of duties, then PII.
- Existing shadow mode still records Cedar's policy outcome while applying `ALLOW` to the mock effect.
- Existing enforce mode applies Cedar's mapped outcome.
- Existing guide retry limit remains in `ManifestGovernor`.
- Existing approval, commitment, ledger, and mock-tool code must not contain Cedar-specific branching.
- Existing Checkpoint 6 JSON and Markdown evidence must not be overwritten. Checkpoint 7 produces separate artifacts.
- Cedar must never receive credentials, demo secrets, raw PII, approval comments, idempotency secrets, or an unfiltered trajectory-state dump.

## 4. Scope

### Included

- Cedar runtime preflight and a pinned integration choice.
- One local Cedar policy decision service built on the official Rust `cedar-policy` crate.
- Versioned Cedar schema and six policy families.
- Typed Python-to-Cedar request construction.
- Stable Cedar policy ID to Manifest signal mapping.
- Startup policy/schema validation and bundle hashing.
- Configurable engine selection fixed at process startup.
- Health and trace disclosure of the active engine and bundle.
- Python/Cedar parity tests.
- Cedar failure-injection tests.
- Checkpoint 7 evaluation and release evidence.
- Local/offline Python fallback verification.
- A complete `scripts/run_checkpoint_7.sh` gate.

### Explicitly excluded

- DynamoDB or durable storage.
- Strands or Bedrock.
- Lambda, API Gateway, Amplify, Step Functions, or EventBridge.
- Amazon Verified Permissions.
- Runtime policy CRUD or a policy-authoring UI.
- User-authored Cedar policies.
- Hot policy reload.
- Network-exposed Cedar service.
- New policy families or changes to product semantics.
- Real logistics integrations.

## 5. Cedar integration decision

### 5.1 Recommended runtime path

Use a thin local Rust policy decision service built on a pinned version of the official `cedar-policy` crate. The candidate at plan creation is Cedar CLI/crate **4.12.0**, but implementation must verify and pin the exact crate and CLI versions in the release manifest.

```text
ManifestGovernor
      |
      v
CedarPolicyEngine (Python PolicyEngine adapter)
      |
      +--> CedarRequestBuilder
      |       -> validated Cedar request + entities
      |
      +--> CedarClient (bounded localhost request)
      |       -> Cedar PDP sidecar using official Rust crate
      |
      +--> CedarResultMapper
              -> tuple[PolicySignal, ...]
```

The sidecar loads and validates the schema and policy bundle once at startup. It must not spawn the Cedar CLI for every authorization request.

### 5.2 Why this path

- The official Cedar implementation is Rust-first.
- It keeps Cedar evaluation real and authoritative without embedding policy logic in Python.
- It avoids making an unverified third-party Python binding part of the mandatory path.
- It gives the later AWS checkpoint a clearly bounded component that can be packaged or replaced behind the same client protocol.
- It allows the official Cedar CLI to remain a build/test validator rather than a latency-heavy per-request runtime.

### 5.3 Time-boxed preflight decision

Before modifying the governor:

1. Confirm Rust/Cargo availability.
2. Pin an official `cedar-policy` crate version.
3. Pin a matching `cedar` CLI version for policy validation tests.
4. Prove one allow and one deny request through the sidecar.
5. Confirm the sidecar returns determining policy IDs and diagnostic errors.
6. Record binary/crate versions and checksums.

Timebox this spike to 60–90 minutes.

If building the sidecar is blocked, a pinned official Cedar CLI subprocess adapter may be used temporarily to complete policy semantics and parity tests. It is a fallback, not the desired final runtime. Per-request CLI spawning must be disclosed and cannot meet the performance exit gate unless its measured latency is acceptable.

No third-party Python binding becomes the fallback automatically. It may be considered only after checking maintenance status, supported Python/Cedar versions, license, binary provenance, and parity against the official CLI.

## 6. Authorization responsibility boundary

Cedar must be authoritative for the allow/deny result. Python may compute facts Cedar cannot derive, but Python must not independently grant a protected action.

| Responsibility | Owner | Rule |
|---|---|---|
| Tool lookup and effect metadata | Existing tool registry | Registry data is trusted server-side input, never model-provided |
| Unknown tool handling | Governor | Fail closed before Cedar because no valid Cedar action can be constructed |
| Typed context construction | Python Cedar adapter | Whitelist fields; never serialize the whole state |
| Cryptographic fact hash computation | Python preprocessor | Produce `fact_hash_valid`; Cedar authorizes based on the resulting boolean and fact fields |
| Date/expiry calculation | Python preprocessor | Produce an `approval_expired` boolean using the existing clock |
| PII-key classification | Python preprocessor | Produce booleans/set values without sending raw prohibited content |
| Ownership and mandate authorization | Cedar | Cedar policy determines the result |
| Provenance presence, validity, unit, and value authorization | Cedar | Cedar consumes the trusted computed flags and numeric values |
| Cold-chain vehicle/carrier authorization | Cedar | Cedar evaluates resource metadata |
| Spend and approval authorization | Cedar | Cedar compares minor-unit totals and approval binding fields |
| Separation-of-duties authorization | Cedar | Cedar compares actor, preparer, issuer, and approver fields |
| Disclosure boundary authorization | Cedar | Cedar evaluates safe template/recipient/field flags |
| `ALLOW/GUIDE/BLOCK/ESCALATE` mapping | Python result mapper | Mapping is keyed only by known determining Cedar policy IDs |
| Shadow/enforce application | Existing governor | Unchanged |
| Guide retry exhaustion | Existing governor | Unchanged |
| Approval state mutation | Existing approval service | Unchanged |
| Effect execution | Existing tool registry | Only after the mapped decision allows it |

### Authority invariant

For every registered tool attempt while `MANIFEST_POLICY_ENGINE=cedar`:

```text
no Cedar response -> no tool execution
Cedar error       -> no tool execution
Cedar deny        -> no tool execution, except shadow-mode counterfactual behavior
Cedar allow       -> execution may proceed subject to existing governor lifecycle
```

## 7. Cedar request model

### 7.1 Namespace and entity types

Use one namespace, for example `Manifest`.

Minimum entity types:

- `Manifest::Agent`
- `Manifest::ShipmentAction`

Actions correspond exactly to registered tools:

```text
get_order
check_inventory
list_available_vehicles
create_dispatch_plan
list_carrier_quotes
select_carrier_quote
prepare_freight_booking
confirm_freight_booking
cancel_freight_booking
write_tracking_outbox
```

No dynamic or model-generated action name is accepted. The Cedar schema and tool registry must contain exactly the same action set.

### 7.2 Principal

Map `AgentName` to a Cedar entity UID:

```json
{"type": "Manifest::Agent", "id": "dispatch"}
```

Allowed IDs are the four existing agent values only.

### 7.3 Action

Map the registered tool name to:

```json
{"type": "Manifest::Action", "id": "create_dispatch_plan"}
```

### 7.4 Resource

Represent the attempted protected operation as a `ShipmentAction` entity. Its UID should be proposal-scoped so two attempts cannot accidentally share mutable entity meaning.

```json
{
  "uid": {
    "type": "Manifest::ShipmentAction",
    "id": "PROP-..."
  },
  "attrs": {
    "orderId": "ORD-8842",
    "toolName": "create_dispatch_plan",
    "owner": {
      "__entity": {
        "type": "Manifest::Agent",
        "id": "dispatch"
      }
    },
    "effectClass": "reversible_write"
  },
  "parents": []
}
```

The owner and effect class must come from `ToolDefinition`, never request arguments.

### 7.5 Common context

Every registered request includes:

```text
policyVersion
mandatePolicyVersion
cargoClass
currency
allowedEffectClasses
effectClass
preparedActionPresent
```

Use Cedar `Long` for all integer minor-unit money and weight values. Never use floating-point currency.

### 7.6 Action-specific context

#### Dispatch plan

```text
provenanceFactPresent
provenanceFactHashValid
attemptedWeight
attemptedUnit
authoritativeWeight
authoritativeUnit
vehicleMetadataPresent
vehicleAvailable
vehicleRefrigerated
vehicleCapacityKg
```

#### Carrier selection and preparation

```text
carrierMetadataPresent
coldChainCertified
laneSupported
quoteIssuer
```

#### Confirmation

```text
preparedActionPresent
preparedStatus
preparedCurrency
preparedBy
actionHashMatches
spendCommittedMinor
spendReservedMinor
approvalStatus
approvalExpired
approvalActionMatches
approvalStateMatches
approvalPolicyMatches
approverLabel
approverConflictsWithPreparer
```

The reserved amount already contains the prepared action, so projected spend remains:

```text
spendCommittedMinor + spendReservedMinor
```

Do not add the prepared amount twice.

#### Cancellation

```text
preparedActionPresent
preparedStatus
actionHashMatches
```

#### Disclosure

```text
containsForbiddenPiiField
templateId
syntheticRecipientValid
templateVariablesAllowed
```

Do not send raw free-form messages, phone numbers, email addresses, names, addresses, payment data, or rendered notification content to Cedar.

## 8. Cedar schema design

Create an action-specific schema instead of one large untyped context record.

Recommended layout:

```text
policies/schema/
  manifest.cedarschema
  manifest.cedarschema.json
```

The human-readable schema is the authored source. The JSON form is generated or verified from the same source and used where the selected runtime requires JSON.

### Schema requirements

- Each registered tool action declares applicable principal and resource types.
- Each action declares only the context fields it needs.
- Required fields are required when absence would change authorization semantics.
- Optional fields are accessed only through safe `has` checks.
- Entity reference types are used for owners and actors where comparison matters.
- Schema validation runs before service readiness.
- Warnings fail the checkpoint validation command.
- Registry/schema action drift fails startup and tests.
- A schema or policy-bundle hash is recorded in health, decision evidence, evaluation output, and release manifest.

## 9. Policy bundle design

Recommended layout:

```text
policies/demo-v1/
  base.cedar
  ownership.cedar
  provenance.cedar
  cold_chain.cedar
  spend.cedar
  separation.cedar
  pii.cedar
  metadata.json
  bundle.json
```

`bundle.json` records the policy version, Cedar version, ordered source files, schema digest, and complete bundle digest.

### 9.1 Stable policy IDs

Use the existing Python policy IDs wherever they already exist:

```text
OWN-001 through OWN-004
PROV-001 through PROV-004
COLD-001 through COLD-004
SPEND-001 through SPEND-011
SOD-000 through SOD-008 where applicable
PII-001 through PII-004
```

Add a narrowly named base permit ID, such as `BASE-PERMIT-REGISTERED`, for valid registered requests. It must not become the user-facing primary reason when a more specific allow policy such as `SPEND-004` or `SPEND-009` applies.

Use stable `@id` annotations in authored policies and validate that policy IDs are unique.

### 9.2 Policy semantics

#### Base permit

A request is eligible for permit only when:

- policy versions match;
- principal owns the tool;
- effect class is allowed by the mandate; and
- the action/resource/context shapes are valid.

Specific `forbid` policies then enforce safety constraints. Cedar's forbid-overrides-permit and default-deny behavior provide the final binary decision.

#### Ownership and mandate

- Version mismatch -> `MISSING_POLICY_CONTEXT` / `BLOCK`.
- Principal does not match resource owner -> `TOOL_OWNER_MISMATCH` / `BLOCK`.
- Effect class not in the mandate set -> `EFFECT_NOT_ALLOWED_BY_MANDATE` / `BLOCK`.
- Confirm/cancel without a prepared action -> `PREPARED_ACTION_REQUIRED` / `BLOCK`.

#### Provenance

- Fact absent -> `PROVENANCE_REFERENCE_MISSING` / `BLOCK`.
- Fact hash invalid -> `PROVENANCE_REFERENCE_MISSING` / `BLOCK`.
- Unit differs -> `PROVENANCE_UNIT_MISMATCH` / `GUIDE`.
- Numeric value differs -> `PROVENANCE_VALUE_MISMATCH` / `GUIDE`.

#### Cold chain

- Required vehicle metadata absent -> `MISSING_POLICY_CONTEXT` / `BLOCK`.
- Vehicle unavailable, non-refrigerated, or under capacity -> `COLD_CHAIN_VEHICLE_REQUIRED` / `GUIDE`.
- Required carrier metadata absent -> `MISSING_POLICY_CONTEXT` / `BLOCK`.
- Carrier uncertified or lane unsupported -> `COLD_CHAIN_CARRIER_REQUIRED` / `GUIDE`.

#### Spend and approval

- Negative or invalid integer context is rejected before authorization and fails closed.
- Currency mismatch -> `MISSING_POLICY_CONTEXT` / `BLOCK`.
- Projected spend at or below threshold -> `SPEND_WITHIN_CEILING` / `ALLOW`.
- Projected spend above threshold without approval -> `SPEND_APPROVAL_REQUIRED` / `ESCALATE`.
- Approved and exactly bound exception -> `SPEND_EXCEPTION_APPROVED` / `ALLOW`.
- Expired, rejected, action-mismatched, state-mismatched, or policy-mismatched approval -> existing stable block reason.

#### Separation of duties

- Quote issuer equals selecting/preparing principal -> `SEPARATION_OF_DUTIES_VIOLATION` / `BLOCK`.
- Confirm/cancel status or action hash is invalid -> `PREPARED_ACTION_MISMATCH` / `BLOCK`.
- Approver conflicts with preparer -> `APPROVER_CONFLICT` or existing separation reason / `BLOCK`.

#### PII boundary

- Forbidden raw field present -> `PII_FIELD_NOT_ALLOWED` / `BLOCK`.
- Template is not allowlisted -> `DISCLOSURE_TEMPLATE_NOT_ALLOWED` / `BLOCK`.
- Recipient reference is not synthetic -> `PII_FIELD_NOT_ALLOWED` / `BLOCK`.
- Template variables exceed the allowlist -> `PII_FIELD_NOT_ALLOWED` / `BLOCK`.

## 10. Mapping Cedar results to Manifest signals

Cedar returns `Allow` or `Deny`, determining policy IDs, and diagnostic errors. Manifest needs one or more typed `PolicySignal` values.

### 10.1 Metadata registry

`policies/demo-v1/metadata.json` maps each determining policy ID to:

```text
family
Manifest outcome
reason_code
controlled because template key
guidance builder key, if any
family order
policy order
```

The adapter owns controlled messages and guidance. It must not expose raw policy source, diagnostic internals, or untrusted context in `because`.

### 10.2 Deterministic ordering

Sort mapped signals by:

1. family order matching the Python engine;
2. policy order within the family; and
3. policy ID as the final deterministic tie-breaker.

The governor retains outcome precedence:

```text
BLOCK > ESCALATE > GUIDE > ALLOW
```

This prevents nondeterministic determining-policy order from changing the primary reason.

### 10.3 Allow mapping

- Ignore the generic base permit when a more specific explanatory permit applies.
- Map within-threshold confirmation to `SPEND_WITHIN_CEILING`.
- Map a valid approved exception to `SPEND_EXCEPTION_APPROVED`.
- For ordinary allowed actions, emit the existing `ALLOW_POLICY_CHECKS_PASSED` signal.

### 10.4 Deny mapping

- Map all known determining forbid IDs into signals.
- Preserve multiple simultaneous reasons in `Decision.reasons`.
- Let the unchanged governor select the primary outcome and reason by precedence.
- If Cedar denies with no determining policy, treat it as implicit deny and return `MISSING_POLICY_CONTEXT` / `BLOCK` with a controlled explanation.

### 10.5 Error mapping

Cedar uses skip-on-error semantics internally. Manifest must be stricter:

- any diagnostic error in the Cedar response causes `POLICY_ENGINE_FAILURE` / `BLOCK`;
- any unknown determining policy ID causes `POLICY_ENGINE_FAILURE` / `BLOCK`;
- timeout, connection error, malformed JSON, version mismatch, schema mismatch, or bundle hash mismatch causes `POLICY_ENGINE_FAILURE` / `BLOCK`;
- no protected effect executes after one of these failures;
- only safe error class, request ID, and bundle identifiers are logged.

## 11. Sidecar protocol

### 11.1 Startup

The sidecar must:

1. read the configured schema and ordered policy files;
2. calculate their canonical SHA-256 digest;
3. parse and validate the policies against the schema;
4. reject duplicate policy IDs;
5. refuse readiness on warnings when strict mode is enabled;
6. load the validated policy set once; and
7. bind only to loopback.

### 11.2 Endpoints

Minimum local endpoints:

```text
GET  /health/ready
POST /v1/authorize
```

Suggested health response:

```json
{
  "status": "ready",
  "engine": "cedar",
  "cedar_version": "pinned-version",
  "policy_version": "demo-v1",
  "bundle_hash": "sha256:...",
  "schema_hash": "sha256:...",
  "validation": "passed"
}
```

Suggested authorization response:

```json
{
  "request_id": "REQ-...",
  "decision": "allow",
  "determining_policy_ids": ["SPEND-004"],
  "errors": [],
  "policy_version": "demo-v1",
  "bundle_hash": "sha256:...",
  "evaluation_us": 120
}
```

### 11.3 Transport requirements

- Loopback only; never `0.0.0.0` in this checkpoint.
- Small maximum body size.
- Bounded connect and request timeouts.
- No retry for an authorization decision inside one tool attempt.
- Request ID correlation.
- No raw request body in default logs.
- Graceful shutdown in test and checkpoint scripts.
- Readiness checked before the Python service accepts work.

## 12. Python integration changes

### New modules

```text
packages/cedar_adapter/
  __init__.py
  engine.py               # PolicyEngine implementation
  client.py               # bounded sidecar client
  context.py              # whitelist-based request/entity builder
  mapping.py              # Cedar policy ID -> PolicySignal
  metadata.py             # validated policy metadata loading
  models.py               # sidecar request/response contracts
  errors.py               # internal adapter error classes
  status.py               # safe readiness/description data
```

### Rust sidecar

```text
services/cedar_pdp/
  Cargo.toml
  Cargo.lock
  src/main.rs
  src/config.rs
  src/authorizer.rs
  src/http.rs
  tests/
```

Exact Rust module names may change, but policy loading, authorization, HTTP transport, and tests must remain separated.

### Existing files to update

| File | Required change |
|---|---|
| `packages/policy/protocol.py` | Add startup validation and safe engine-description contract used by both engines |
| `packages/policy/python_engine.py` | Implement the expanded protocol without changing decisions |
| `packages/policy/__init__.py` | Export the engine factory/protocol without hiding adapter selection |
| `packages/governor/governor.py` | Preserve lifecycle; accept deterministic mapped signals and fail closed on adapter errors |
| `apps/runtime/service.py` | Allow explicit engine injection and startup selection instead of hard-coding Python |
| `apps/api/dependencies.py` | Build one configured engine/service at startup and expose readiness failures safely |
| `apps/api/main.py` | Add Cedar readiness/bundle fields to health; no path changes |
| `apps/api/schemas.py` | Add optional health/run disclosure fields |
| `packages/domain/models.py` | Add optional engine/bundle evidence fields only if required; do not change existing meanings |
| `packages/evaluation/cases.py` | Accept an engine factory; stop hard-coding Python in focused cases |
| `packages/evaluation/runner.py` | Accept active engine metadata; do not overwrite Checkpoint 6 evidence |
| `.env.example` | Add non-secret engine, endpoint, timeout, schema, and bundle settings |
| `pyproject.toml` | Add only the client/runtime dependency actually needed |
| `README.md` | Document Cedar and explicit Python fallback launch modes |
| `policies/README.md` | Document policy ownership, validation, and parity rules |
| `scripts/README.md` | Document Cedar preflight and Checkpoint 7 gate |

### Engine factory

Use explicit configuration such as:

```text
MANIFEST_POLICY_ENGINE=cedar|python_reference
CEDAR_ENDPOINT=http://127.0.0.1:<port>
CEDAR_TIMEOUT_MS=100
POLICY_BUNDLE_PATH=policies/demo-v1
CEDAR_SCHEMA_PATH=policies/schema/manifest.cedarschema
CEDAR_EXPECTED_BUNDLE_SHA256=sha256:...
```

Rules:

- Engine choice is fixed at process startup.
- Unknown engine name fails startup.
- Configuring Cedar while it is unavailable fails readiness; it must not silently construct the Python engine.
- Python fallback requires an explicit `MANIFEST_POLICY_ENGINE=python_reference` value.
- Tests may inject an engine directly without mutating global environment state.

## 13. Health, trace, and dashboard disclosure

### Health additions

Additive fields should include:

```text
policy_engine
policy_version
policy_engine_ready
policy_bundle_hash
policy_schema_hash
cedar_runtime_version
policy_fallback_active
```

When Python is selected:

```text
policy_engine=python_reference
policy_fallback_active=true
cedar_runtime_version=null
```

When Cedar is selected and ready:

```text
policy_engine=cedar
policy_fallback_active=false
cedar_runtime_version=<pinned version>
```

### Decision/event additions

Each decision already records `engine_name`, `policy_version`, and latency. Add bundle/schema identifiers only if they can be included without exposing configuration paths. The ledger should prove which policy bundle produced the decision.

### Dashboard

The existing environment badge must display the actual engine. Add a visible warning when the Python fallback is active. No dashboard redesign is allowed.

## 14. Detailed implementation sequence

### Phase 7.0 — Freeze and preflight

1. Record the Checkpoint 6 commit, fixture digest, functional digest, and generated evidence paths.
2. Re-run the 119-test baseline.
3. Confirm current working-tree changes and preserve them.
4. Complete the Cedar allow/deny/diagnostic spike.
5. Pin Cedar versions and write the decision record.

**Gate:** no governor change until one real Cedar allow and deny have executed.

### Phase 7.1 — Schema, metadata, and request fixtures

1. Freeze the ten action names against the registry.
2. Define principal and resource entity types.
3. Define action-specific context shapes.
4. Add policy metadata registry and controlled message mappings.
5. Add canonical Cedar request fixtures for every Checkpoint 6 policy/evaluation case.
6. Add missing/type-invalid/unknown-action fixtures.

**Gate:** schema parses; registry/schema action-set equality test passes.

### Phase 7.2 — Cedar policies

1. Add base permit and ownership policies.
2. Add provenance and cold-chain policies.
3. Add spend/approval policies.
4. Add separation-of-duties and PII policies.
5. Validate with the pinned Cedar CLI in strict mode.
6. Run request fixtures directly against the Cedar CLI or sidecar.

**Gate:** all static policy fixtures return expected Cedar decision and determining policy IDs.

### Phase 7.3 — Sidecar and Python adapter

1. Implement validated sidecar startup and health.
2. Implement bounded authorization endpoint.
3. Implement whitelist-based Python request builder.
4. Implement policy ID mapper and deterministic signal ordering.
5. Implement engine status and bundle verification.
6. Add transport and failure-injection tests.

**Gate:** adapter contract tests pass without the orchestrator.

### Phase 7.4 — Runtime integration

1. Add engine factory and explicit dependency injection.
2. Run the benign journey with Cedar.
3. Run adversarial shadow with Cedar.
4. Run adversarial enforce to pending approval with Cedar.
5. Approve and resume with fresh Cedar evaluation.
6. Verify the completed ledger and dashboard projection.

**Gate:** the complete local hero journey works with `engine_name=cedar` on every decision.

### Phase 7.5 — Parity, evaluation, and failures

1. Run Python/Cedar table-driven parity cases.
2. Run all 22 Checkpoint 6 cases with Cedar.
3. Compare normalized functional results with Checkpoint 6.
4. Inject timeout, unreachable sidecar, diagnostic error, malformed response, unknown policy ID, invalid schema, and bundle mismatch.
5. Verify no protected tool executes in every failure case.
6. Measure and report Cedar policy/transport latency separately from end-to-end latency.

**Gate:** zero functional parity regressions and all failure modes fail closed.

### Phase 7.6 — Evidence and documentation

1. Generate Checkpoint 7 Cedar evaluation JSON and Markdown.
2. Generate a Checkpoint 7 release manifest.
3. Update health/dashboard screenshots with Cedar active.
4. Update README and real/mock/deferred disclosure.
5. Add and run `scripts/run_checkpoint_7.sh`.
6. Review the complete diff and confirm no Checkpoint 8 work entered.

**Gate:** one command reproduces all Checkpoint 7 evidence.

## 15. Required test plan

### 15.1 Baseline regression tests

Mandatory:

```bash
python3 -m pytest -q
./scripts/run_checkpoint_6.sh
```

All 119 pre-existing tests must remain semantically green. Test count may increase; it must never be reduced by deleting or weakening established assertions.

### 15.2 Schema and bundle tests

Required tests:

- Schema parses with the pinned Cedar version.
- All policy files parse.
- Policy validation passes with warnings treated as errors.
- Every policy has a unique stable ID.
- Bundle contains only declared files.
- Bundle digest is deterministic.
- Schema digest is deterministic.
- Changed policy content changes bundle digest.
- Registry action names equal Cedar schema action names.
- Metadata policy IDs equal policy-bundle IDs, excluding explicitly documented internal base IDs.
- Missing metadata for a determining policy fails startup.
- Duplicate or unknown metadata ID fails startup.

### 15.3 Request-builder unit tests

For every action family, verify:

- principal mapping;
- action mapping;
- proposal-scoped resource ID;
- owner and effect class sourced from the registry;
- allowed effect set sourced from the mandate;
- no entire state object is serialized;
- no secrets or approval comments are serialized;
- no forbidden PII value is serialized;
- all money and weight values are integers;
- negative or boolean-as-integer values are rejected;
- missing required context fails closed;
- optional context is omitted or represented consistently;
- entity and context JSON are canonical and deterministic;
- unknown action cannot be constructed.

Specific context assertions:

- valid 500 kg fact -> present and hash-valid;
- corrupted hash -> hash-invalid without sending source payload;
- 50 kg attempt retains authoritative 500 kg value;
- vehicle metadata includes availability, refrigeration, and capacity;
- carrier metadata includes certification, lane support, and issuer;
- spend is committed plus reserved, without double-counting prepared amount;
- approval booleans reflect action, state, policy, expiry, and actor bindings;
- disclosure context contains only safe flags, template ID, and synthetic reference validity.

### 15.4 Result-mapper unit tests

- Cedar allow with base permit -> `ALLOW_POLICY_CHECKS_PASSED`.
- Cedar allow with `SPEND-004` -> `SPEND_WITHIN_CEILING`.
- Cedar allow with `SPEND-009` -> `SPEND_EXCEPTION_APPROVED`.
- Each known forbid ID maps to the existing family, outcome, reason, and controlled explanation.
- Provenance guidance contains required fact ID/value/unit.
- Cold-chain vehicle guidance contains minimum capacity and refrigeration.
- Carrier guidance requires certification and lane support.
- Multiple determining IDs produce multiple ordered signals.
- `BLOCK` outranks `ESCALATE`, which outranks `GUIDE`.
- Same-outcome family ordering matches the Python engine.
- Cedar deny without determining IDs maps to a controlled implicit deny.
- Unknown policy ID maps to `POLICY_ENGINE_FAILURE` and never allow.
- Any Cedar diagnostic error maps to `POLICY_ENGINE_FAILURE` and never allow.
- Malformed decision value maps to failure.
- Request/response ID mismatch maps to failure.
- Policy version or bundle hash mismatch maps to failure.

### 15.5 Policy-family parity matrix

At minimum, run these cases against both Python and Cedar:

| Family | Positive/boundary cases | Negative cases |
|---|---|---|
| Ownership | correct owner; allowed effect | wrong owner; effect not allowed; policy version mismatch; missing mandate context |
| Provenance | exact fact/value/unit | missing fact; invalid fact hash; unit mismatch; 500-to-50 value drift |
| Cold chain | refrigerated capacity exactly 500; certified supported carrier | capacity 499; unavailable vehicle; non-refrigerated vehicle; uncertified carrier; unsupported lane; missing metadata |
| Spend | below threshold; exactly INR 4,000; exact approved exception | INR 4,001+ without approval; negative value; currency mismatch; rejected/expired/mismatched approval |
| Separation | independent issuer/preparer/approver; valid cancel | issuer equals actor; changed action hash; invalid prepared status; approver equals preparer |
| PII | allowlisted template; synthetic recipient; safe variables | raw message/contact field; wrong template; non-synthetic recipient; extra variable |

Parity means the same Manifest policy outcome, applied outcome, primary reason code, ordered reason-code set, and effect-executed result. Cedar's internal diagnostics may differ but must be stored only as safe adapter evidence.

### 15.6 Governor integration tests with Cedar

- Every tool attempt has exactly one decision.
- No tool handler runs before Cedar responds.
- Unknown tool fails before handler execution.
- Owner mismatch never executes.
- Guided first attempt does not execute.
- Corrected guided attempt executes once.
- Guide retry exhaustion blocks.
- Shadow mode records Cedar deny/guide/escalate and applies allow.
- Enforce mode applies the mapped Cedar outcome.
- Decision contains `engine_name=cedar`, `policy_version=demo-v1`, bundle hash, and measured evaluation latency.
- Ledger event records safe policy evidence.
- No raw context or secret appears in events.

### 15.7 Full journey tests

#### Benign enforce

- Four agents complete.
- Vehicle and carrier are compliant.
- Booking confirms once.
- Notification is written once.
- Spend ends at INR 3,400.
- All decisions are Cedar-backed.

#### Adversarial shadow

- Workflow completes through the unsafe mock path.
- Cedar records provenance, carrier, and spend violations.
- Applied outcomes are allow because mode is shadow.
- No approval record is created.

#### Adversarial enforce

- 50 kg is guided to 500 kg before dispatch.
- Unsafe vehicle is not selected.
- Uncertified carrier is guided to the certified carrier.
- INR 4,550 projects above INR 4,000.
- Confirmation does not execute.
- One pending approval is created.

#### Approved resume

- Approval is bound to trace/action/state/policy.
- Fresh Cedar evaluation returns approved exception allow.
- Confirmation executes once.
- Reserved spend moves to committed spend once.
- Notification executes once.
- Same trace completes.
- Ledger verifies.

#### Reject and expiry

- Prepared reservation is cancelled once.
- Reserved spend is released once.
- No confirmation or notification occurs.
- Ledger verifies.

### 15.8 Failure-injection tests

| Failure | Required result |
|---|---|
| Sidecar unavailable at startup | Health not ready; no run starts in Cedar mode |
| Sidecar disconnect during request | `POLICY_ENGINE_FAILURE`; effect does not execute |
| Authorization timeout | `POLICY_ENGINE_FAILURE`; no retry and no effect |
| Invalid response JSON | Fail closed |
| Response request ID mismatch | Fail closed |
| Cedar diagnostic error | Fail closed despite Cedar skip-on-error semantics |
| Unknown determining policy ID | Fail closed |
| Bundle hash mismatch | Startup/readiness failure |
| Policy version mismatch | Startup or request failure; no effect |
| Invalid schema | Sidecar never becomes ready |
| Invalid policy syntax | Sidecar never becomes ready |
| Registry/schema action drift | Application startup fails |
| Oversized request | Rejected without logging raw body |
| Python fallback selected explicitly | Works and is visibly disclosed as fallback |

### 15.9 API tests

- `/health/ready` reports Cedar only when sidecar, schema, bundle, and mappings are ready.
- Health reports Python fallback truthfully when selected.
- Existing health fields remain present.
- `POST /v1/runs` returns Cedar engine evidence.
- Trace decisions show Cedar engine and policy version.
- Existing approval endpoints remain unchanged.
- Cedar outage returns a controlled failed-dependency response or a blocked run, according to where failure occurs.
- Error responses do not expose sidecar URL, file paths, raw Cedar request, or policy source.

### 15.10 Ledger and dashboard tests

- Switching engine changes only expected decision evidence, not chain validity.
- Clean Cedar trace verifies.
- Tampered Cedar trace fails at the first altered sequence.
- Dashboard environment badge displays Cedar.
- Fallback warning displays when Python is active.
- Decision panel shows unchanged reason text and guidance.
- Spend/risk/provenance projections remain correct.
- Approval and verify controls continue to work.

### 15.11 Evaluation tests

- All 22 Checkpoint 6 cases run with an injected Cedar engine.
- Cedar result: 22/22 pass, 10/10 attack detection, 12/12 benign pass, 0 false positives, and 2/2 guide-back.
- Normalized Checkpoint 7 functional digest matches the Checkpoint 6 digest unless a reviewed evidence-schema change is documented.
- Timing samples identify adapter/transport and Cedar evaluation where available.
- Evaluation active modes report `policy_engine=cedar`.
- Checkpoint 6 artifacts remain byte-for-byte untouched by Checkpoint 7 generation.
- Repeated Cedar evaluation has identical normalized functional output.

### 15.12 Performance and resource tests

- Policy bundle loads once, not once per request.
- Sidecar process count remains one during a full journey.
- Each authorization call obeys the configured timeout.
- Cedar and total adapter p50/p95 are recorded after warm-up.
- No unbounded request queue or retry loop exists.
- Memory does not grow with repeated fixed-size authorization calls beyond an explained bounded cache.
- Performance results are reported, not inflated into production claims.

## 16. Checkpoint 7 evidence artifacts

Create separate artifacts:

```text
docs/results/checkpoint-7-cedar-evaluation.json
docs/results/checkpoint-7-cedar-evaluation.md
docs/results/checkpoint-7-policy-parity.json
docs/results/checkpoint-7-browser-smoke.md
docs/releases/checkpoint-7-cedar-baseline.json
docs/architecture/cedar-request-mapping.md
docs/architecture/cedar-responsibility-boundary.md
docs/assets/screenshots/checkpoint-7-health-cedar.png
docs/assets/screenshots/checkpoint-7-decision-cedar.png
docs/assets/screenshots/checkpoint-7-approved.png
```

The Checkpoint 7 release manifest must include:

- source revision and dirty-state fingerprint;
- Python version;
- Rust toolchain version;
- Cedar crate and CLI versions;
- sidecar binary checksum;
- schema hash;
- policy bundle hash;
- fixture-tree checksum;
- Checkpoint 6 and 7 functional digests;
- active engine and fallback state;
- test/evaluation commands and results;
- current limitations.

## 17. Checkpoint script

`scripts/run_checkpoint_7.sh` should perform, in order:

```text
1. Check required local tools and pinned versions.
2. Validate Cedar schema and policy bundle in strict mode.
3. Build or locate the pinned Cedar PDP binary.
4. Start the sidecar on an isolated loopback port.
5. Wait for readiness and verify bundle/version hashes.
6. Run the full Python regression suite.
7. Run Checkpoint 6 preservation gate.
8. Run Cedar schema, mapping, parity, failure, and integration tests.
9. Run benign, shadow adversarial, enforce pending, approve, reject, and expiry journeys with Cedar.
10. Generate Checkpoint 7 evaluation and parity evidence.
11. Compare normalized Checkpoint 6/7 functional results.
12. Generate the Checkpoint 7 release manifest.
13. Validate generated artifacts and mode disclosure.
14. Stop the sidecar through a shell trap.
15. Print a concise completion summary.
```

The script must leave no orphan sidecar process and must not modify Checkpoint 6 evidence.

## 18. Security and privacy checklist

- [ ] Sidecar binds only to loopback.
- [ ] No runtime policy mutation endpoint exists.
- [ ] Schema and bundle paths come from trusted configuration.
- [ ] Bundle hash is pinned and verified.
- [ ] Unknown policies and diagnostics fail closed.
- [ ] Authorization request size is bounded.
- [ ] Authorization timeout is bounded.
- [ ] Raw PII and secret values never enter Cedar context.
- [ ] Raw Cedar requests are not logged by default.
- [ ] Error output omits local paths and policy source.
- [ ] Model/user input cannot set principal, owner, effect class, policy version, or approval-binding booleans.
- [ ] Policy metadata and message templates are application-controlled.
- [ ] Approval comments are excluded from policy context.
- [ ] Cedar sidecar has no outbound network requirement.
- [ ] Dependency and binary licenses/checksums are recorded.

## 19. Risks and mitigations

| Risk | Early warning | Mitigation | Fallback |
|---|---|---|---|
| Rust/Cedar build unavailable | Preflight cannot build one allow/deny | Use pinned prebuilt official CLI for semantic work; keep adapter boundary | Record checkpoint blocked if no real Cedar runtime can be made reliable |
| Schema/context mismatch | Validation or request parsing errors | Action-specific schema, canonical builder, missing/type tests | Fail startup; do not loosen schema |
| Cedar binary decision loses Manifest outcome detail | Only allow/deny available | Stable determining-policy metadata mapping | Do not infer from free-form messages |
| Multiple policy IDs reorder primary reasons | Flaky reason selection | Explicit family/policy sorting | Fail parity test |
| Cedar skip-on-error allows unsafe request | Diagnostics contain errors with allow | Application fails closed on any diagnostic error | `POLICY_ENGINE_FAILURE` |
| Python and Cedar semantic drift | Functional digest or parity case differs | Table-driven dual-engine suite | Keep Python active and do not claim Cedar completion |
| Sidecar latency is high | p95 rises or timeout occurs | Load bundle once; persistent client; no per-call process | Temporary CLI adapter only with disclosure |
| Sidecar failure breaks demo | Health red or calls timeout | Explicit Python fallback launch mode and backup evidence | Restart in disclosed Python mode; no Cedar claim for that run |
| New fields break ledger/dashboard | API or hash tests fail | Additive fields only; full regression | Revert evidence-only additions, not policy safety |
| Evaluation artifacts are overwritten | CP6 hashes change | New CP7 filenames and preservation test | Restore generated CP7 path; never edit CP6 results |

## 20. Cut order if late

Cut in this order:

1. Extra Cedar documentation beyond the required responsibility/mapping pages.
2. Nonessential dashboard styling for the fallback badge.
3. Optional memory/resource soak test beyond the required bounded run.
4. Extra benign policy fixtures beyond Checkpoint 6 parity.
5. CLI fallback optimization.

Never cut:

- schema and policy validation;
- real Cedar authorization;
- fail-closed diagnostics/error behavior;
- stable policy-ID mapping;
- Python/Cedar parity tests;
- the four hero controls;
- approval re-evaluation;
- Checkpoint 6 preservation;
- truthful health/trace disclosure; or
- local Python fallback verification.

## 21. Definition of done

Checkpoint 7 is complete only when all conditions below are true:

1. A real Cedar runtime is active for the configured Checkpoint 7 demo path.
2. Schema and policy bundle validate with the pinned Cedar version.
3. Every registered tool action exists in the schema and every policy ID has a validated mapping.
4. Every registered tool attempt receives exactly one Cedar-backed decision.
5. All 119 pre-existing tests remain semantically green.
6. All new schema, builder, mapper, parity, failure, API, dashboard, and integration tests pass.
7. All 22 evaluation cases pass with Cedar.
8. Python and Cedar produce the same normalized functional results for declared parity cases.
9. Benign, shadow, enforce, approve, reject, and expiry journeys pass.
10. Cedar errors and outages fail closed with zero protected effects.
11. Approval resumes through a fresh Cedar decision and confirms exactly once.
12. Clean and tampered ledger verification remain correct.
13. Health, trace, dashboard, evaluation, and release artifacts show the real active engine and bundle.
14. Checkpoint 6 generated evidence remains unchanged.
15. The explicit Python fallback still passes the local suite and is visibly labelled.
16. `./scripts/run_checkpoint_7.sh` passes from a documented clean setup.
17. No Checkpoint 8 persistence or AWS scope has entered the change set.

Installing Cedar, adding `.cedar` files, or passing standalone policy fixtures is not enough. The full Manifest journey must be governed by Cedar.

## 22. Rollback and recovery

- Keep the last Checkpoint 6 revision and artifacts unchanged.
- Engine selection remains startup-configured, so rollback is `MANIFEST_POLICY_ENGINE=python_reference` plus a restart.
- Never catch Cedar startup failure and silently select Python.
- If Cedar becomes unreliable during a demonstration, switch to the explicitly disclosed Python fallback before the demo starts.
- Preserve the Cedar failure evidence and limitation in the release manifest.
- Do not delete the Cedar bundle or parity tests when rolling back runtime selection.

## 23. Handoff after completion

When the exit gate passes:

1. update `docs/FOLLOWUP_CHECKPOINTS_TO_COMPLETION.md` to mark Checkpoint 7 complete;
2. record the exact source revision and suggested tag `v0.7.0-cedar`;
3. update the progress report with measured Cedar evidence;
4. unlock Checkpoint 8 only; and
5. carry the `PolicyEngine` and sidecar/client contracts unchanged into durable-storage work.

## 24. Authoritative Cedar references

- [Cedar authorization algorithm and diagnostics](https://docs.cedarpolicy.com/auth/authorization.html)
- [Cedar entities and context JSON syntax](https://docs.cedarpolicy.com/auth/entities-syntax.html)
- [Cedar schema overview](https://docs.cedarpolicy.com/schema/schema.html)
- [Cedar JSON schema format](https://docs.cedarpolicy.com/schema/json-schema.html)
- [Cedar policy validation](https://docs.cedarpolicy.com/policies/validation.html)
- [Official Cedar implementation](https://github.com/cedar-policy/cedar)
- [Official Cedar releases](https://github.com/cedar-policy/cedar/releases)

These references define the Cedar behavior used by this plan. Implementation must pin exact versions and must not depend on documentation from an unversioned branch without recording the selected release.
