# Manifest Follow-up Checkpoints to Prototype Completion

**Plan version:** 1.0  
**Created:** 19 September 2026  
**Starting point:** Completed local Checkpoint 6 implementation with 119 passing tests  
**Execution model:** Complete, verify, and close one checkpoint before beginning the next

## 1. Purpose

This plan continues the repository's implemented Checkpoints 1–5 and takes the prototype from a tested local dashboard to a submission-ready Manifest demonstration.

The work is intentionally sequential:

```text
CP6 Stable local release and evaluation baseline
  -> CP7 Cedar authorization
  -> CP8 durable DynamoDB-compatible storage
  -> CP9 Strands and Bedrock runtime
  -> CP10 AWS deployment
  -> CP11 demo hardening and optional managed integrations
  -> CP12 submission freeze and final verification
```

Checkpoints 6 and 7 have passed their local exit gates. Checkpoint 8 is now the next unlocked checkpoint.

## 2. One-at-a-time checkpoint protocol

For every checkpoint:

1. Confirm the preceding checkpoint's tag or recorded green baseline.
2. Implement only the current checkpoint's in-scope work.
3. Keep all external services behind interfaces with a working local fallback.
4. Run the current checkpoint script and the full regression suite.
5. Record actual results, limitations, configuration modes, and changed contracts.
6. Review the diff and confirm that no unrelated work entered the checkpoint.
7. Mark the checkpoint complete only when every mandatory acceptance test is green.
8. Do not begin the next checkpoint while a mandatory test is red.

If a checkpoint becomes blocked by external access, use its declared fallback and record the limitation. Do not silently substitute a fallback while claiming the target integration is active.

## 3. Checkpoint queue

| Checkpoint | Outcome | Initial status | Estimated focused time |
|---|---|---|---:|
| 6 | Reproducible local release plus measured evaluation | **COMPLETE** | Completed |
| 7 | Cedar is the authoritative policy engine | **COMPLETE** | Completed |
| 8 | Runs, approvals, and ledger survive process restart | **NEXT** | 5–7 hours |
| 9 | Strands agents use Bedrock or a disclosed deterministic fallback | Locked | 5–7 hours |
| 10 | Core API and dashboard run through an AWS demo stack | Locked | 6–9 hours |
| 11 | Demo hardening, observability, and optional managed workflow | Locked | 3–5 hours |
| 12 | Frozen, measured, rehearsed submission artifact | Locked | 5–7 hours |

The estimates assume the current local implementation remains green and AWS access is available. They are planning ranges, not deadlines.

---

## Checkpoint 6 — Stable Local Release and Evaluation Baseline

**Detailed implementation specification:**
[`CHECKPOINT_6_IMPLEMENTATION_PLAN.md`](CHECKPOINT_6_IMPLEMENTATION_PLAN.md)

### Objective

Turn the committed Checkpoint 5 baseline into a reproducible local release candidate and generate judge-ready measurements before adding external integrations.

### In scope

- Review the existing Checkpoint 4–5 diff and untracked files.
- Add a release manifest containing:
  - source revision;
  - Python and dependency versions;
  - fixture checksum;
  - active policy engine and version;
  - storage, model, approval, and deployment modes;
  - test command and result.
- Add a deterministic evaluation scenario format and runner.
- Cover at least the six core attack classes:
  - weight value drift;
  - missing or corrupted provenance;
  - unsuitable cold-chain vehicle;
  - uncertified or unsupported carrier;
  - cumulative spend escalation;
  - separation-of-duties or unsafe disclosure violation.
- Add at least ten benign variants or parameterized benign cases.
- Produce machine-readable results containing exact denominators.
- Calculate policy decision p50/p95 and end-to-end run p50/p95 separately.
- Perform local browser QA of the full hero path and capture evidence.
- Add `scripts/run_checkpoint_6.sh`.

### Out of scope

- Cedar, Strands, Bedrock, DynamoDB, or cloud deployment.
- New product features or dashboard redesign.
- Expanding to real logistics integrations.

### Mandatory deliverables

```text
docs/releases/local-baseline.json
docs/results/evaluation.json
docs/results/evaluation.md
tests/evaluation/
scripts/run_evaluation.py
scripts/run_checkpoint_6.sh
docs/assets/screenshots/ (hero-path evidence)
```

Exact filenames may change if the implementation documents the replacement consistently.

### Acceptance tests

- Full existing suite remains green.
- `./scripts/run_checkpoint_5.sh` remains green.
- One command regenerates the evaluation JSON from a fixed seed.
- Results include scenario counts, pass/fail counts, false positives, guide-back success, approval outcomes, and p50/p95 latency.
- Two consecutive evaluation runs have identical functional outcomes.
- Dashboard completes benign, shadow adversarial, enforce pending-approval, approval, and verification flows in a browser.
- The release manifest accurately reports `python_reference`, `memory_hash_chain`, `local`, and `deterministic` modes.
- No credentials or secret values appear in results, screenshots, logs, or the manifest.

### Exit gate

Checkpoint 6 is complete when the repository can be reproduced from a reviewed revision, all tests pass, evaluation results are generated from code, and browser evidence exists. Creating a commit or tag is an explicit operator action; the suggested tag is `v0.6.0-local-evaluated`.

### Fallback

If the planned 20 attack/30 benign set cannot be completed, ship the six core attacks plus at least ten benign variants with exact denominators. Never invent or extrapolate results.

---

## Checkpoint 7 — Cedar Authorization Parity

**Status: COMPLETE — 19 September 2026.** The official Cedar 4.12.0 Rust sidecar is authoritative in the Checkpoint 7 gate. All 22 evaluation cases match the Checkpoint 6 functional digest, and 136 tests pass with Cedar active. See [`CHECKPOINT_7_COMPLETION_REPORT.md`](CHECKPOINT_7_COMPLETION_REPORT.md).

**Detailed implementation specification:**
[`CHECKPOINT_7_IMPLEMENTATION_PLAN.md`](CHECKPOINT_7_IMPLEMENTATION_PLAN.md)

### Prerequisite

Checkpoint 6 is complete and its baseline is reproducible.

### Objective

Make Cedar the authoritative authorization engine while preserving the existing `PolicyEngine` contract, reason catalogue, shadow/enforce semantics, and hero journey.

### In scope

- Select and pin one supported Cedar integration path.
- Add Cedar schema, entities/context mapping, and a versioned `demo-v1` policy bundle.
- Implement the existing six policy families in Cedar where appropriate.
- Retain deterministic pre-policy validation for cryptographic fact hashes and typed input normalization when Cedar cannot perform those operations directly.
- Add a Cedar adapter conforming to `packages.policy.protocol.PolicyEngine`.
- Map Cedar decisions to stable Manifest outcomes, reason codes, `because`, and guidance.
- Add engine selection through configuration.
- Keep the Python engine as an explicitly disclosed fallback and reference oracle.
- Run the same conformance cases against both engines and document any deliberate division of responsibility.
- Add `scripts/run_checkpoint_7.sh`.

### Mandatory deliverables

```text
packages/cedar_adapter/
policies/schema/
policies/demo-v1/
policies/tests/
tests/policy/test_cedar_parity.py
scripts/run_checkpoint_7.sh
```

### Acceptance tests

- Cedar returns the expected allow, guide/block, and escalate authorization signals for every policy fixture.
- Unknown action, missing context, owner mismatch, and disallowed effect fail closed.
- The 500-to-50 kg path is stopped before dispatch effect.
- The uncertified carrier is rejected and guide-back still succeeds.
- INR 4,550 against INR 4,000 still produces a bound approval.
- Approved confirmation is re-evaluated and executes once.
- Shadow mode records the counterfactual result without applying enforcement.
- Python and Cedar conformance suites agree on all declared cases.
- Health and trace output identify the active engine as Cedar only when Cedar is actually active.
- Full Checkpoint 6 regression remains green.

### Exit gate

Checkpoint 7 is complete only when the hero run and policy suite pass with Cedar active. Installing Cedar without making it authoritative does not complete the checkpoint.

### Fallback

If the preferred Python binding fails, use a thin local Cedar sidecar behind the same adapter. If neither path is stable within the checkpoint timebox, keep the Python reference engine, record Checkpoint 7 as blocked, and do not claim Cedar use.

---

## Checkpoint 8 — Durable Storage and DynamoDB Parity

### Prerequisite

Checkpoint 7 is green, or Cedar is explicitly recorded as externally blocked while the local reference baseline remains green.

### Objective

Persist traces, approvals, decisions, idempotency records, and ledger heads so the workflow survives process restart and supports the intended DynamoDB data model.

### In scope

- Extract a storage protocol from `MemoryTraceStore` without changing domain behavior.
- Preserve the memory implementation for unit tests and offline fallback.
- Implement a DynamoDB-compatible adapter using the planned keys:

```text
PK=TRACE#<trace_id>, SK=META
PK=TRACE#<trace_id>, SK=HEAD
PK=TRACE#<trace_id>, SK=EVENT#<sequence>
PK=TRACE#<trace_id>, SK=APPROVAL#<approval_id>
```

- Use conditional sequence/head updates to prevent chain forks.
- Persist approval versioning and idempotency results.
- Reconstruct trajectory state for read, approval resume, verification, and dashboard projection.
- Support local DynamoDB or an equivalent test double before cloud deployment.
- Add migration-free table creation and reset for the synthetic demo namespace.
- Add `scripts/run_checkpoint_8.sh`.

### Acceptance tests

- A pending adversarial run survives API process restart.
- The restarted service can approve the exact prepared action and confirm once.
- Concurrent approval attempts still produce one terminal decision.
- Duplicate event append and duplicate confirm remain idempotent.
- Conditional writes reject stale sequence/head updates.
- Clean verification passes after restart.
- Disposable tampering is detected without affecting other traces.
- Two simultaneous traces remain isolated.
- Memory and DynamoDB adapters pass the same storage contract suite.
- Checkpoint 7 policy behavior remains unchanged.

### Exit gate

Checkpoint 8 is complete when persistence and restart recovery are proven with the DynamoDB-compatible adapter, not merely when table code exists.

### Fallback

Use local DynamoDB-compatible storage for the demo if cloud credentials are unavailable. A file-backed emergency adapter may be used only for recovery and must be disclosed; it does not satisfy the DynamoDB completion claim.

---

## Checkpoint 9 — Strands Agents and Bedrock Runtime

### Prerequisite

Checkpoint 8 persistence contracts are green.

### Objective

Replace the plain-Python agent decision layer with four thin Strands agents using Bedrock when available, while keeping the governor—not the model—authoritative.

### In scope

- Introduce an agent runtime protocol with deterministic and Strands implementations.
- Pin the Strands SDK and selected Bedrock model configuration.
- Implement Inventory, Dispatch, Carrier, and Customer Communications agents with bounded steps.
- Expose only registered governed tools to each agent.
- Prove that every tool call passes through `ManifestGovernor`.
- Preserve stable trace, decision, approval, and ledger contracts.
- Add controlled guide-back prompts/results for weight and carrier correction.
- Add recorded deterministic model responses behind the same runtime interface.
- Add model step/token limits, timeouts, and safe error handling.
- Disclose active model/runtime mode through health, trace, dashboard, and release manifest.
- Add `scripts/run_checkpoint_9.sh`.

### Acceptance tests

- All four Strands agents appear in one trace.
- No registered operational effect bypasses the governor.
- Benign enforce completes twice from reset.
- Adversarial shadow completes with counterfactual decisions.
- Adversarial enforce guides both weight and carrier, then pauses for approval.
- Approval resumes the original trace and confirms once.
- Maximum-step and timeout paths fail safely.
- Bedrock failure switches only to the explicitly enabled recorded fallback.
- Recorded fallback drives the same governed tools; it does not bypass policy or ledger behavior.
- Cedar remains authoritative regardless of model mode.

### Exit gate

Checkpoint 9 is complete when one Bedrock-backed hero run passes or, if Bedrock access is externally unavailable, the Strands integration is proven with the disclosed recorded adapter and the limitation is recorded. Plain-Python agents alone do not satisfy this checkpoint.

### Fallback

Use recorded deterministic responses through the same Strands/runtime interface. Do not replace deterministic authorization with prompt instructions.

---

## Checkpoint 10 — AWS Demo Stack

### Prerequisite

Checkpoint 9 is green and the local fallback remains untouched.

### Objective

Deploy the minimum credible AWS path for the existing prototype without adding new product scope.

### In scope

- Add infrastructure-as-code for:
  - API Gateway;
  - Lambda handlers or an explicitly documented runtime host;
  - DynamoDB;
  - CloudWatch logs/metrics;
  - minimum IAM permissions;
  - static dashboard hosting.
- Package the exact tested runtime and policy bundle.
- Add configuration validation and a useful readiness endpoint.
- Keep secrets server-side and use the AWS credential chain locally.
- Deploy backend first, run smoke tests, then deploy the dashboard.
- Add a synthetic-only reset mechanism restricted to the demo stack.
- Add cloud smoke and rollback scripts.
- Add `scripts/run_checkpoint_10.sh`.

### Acceptance tests

- A clean browser loads the hosted dashboard.
- Health reports actual runtime, model, policy, storage, approval, and deployment modes.
- The cloud path starts a run and returns real trace data.
- Adversarial enforce reaches pending approval with Cedar active.
- Approval confirms the exact action once and survives separate API invocations.
- `/verify` passes for the completed persisted trace.
- The local/offline Checkpoint 9 path remains green.
- Logs contain trace correlation but no credentials, task tokens, raw PII, or approver secrets.
- Deployment can roll back to the previous known-good artifact.

### Exit gate

Checkpoint 10 is complete when the public or judge-accessible URL passes the hero smoke test from a clean browser. A created AWS stack that cannot complete the journey is not sufficient.

### Fallback

Cloud repair has a strict time cap. If it remains unstable, preserve the frozen local build and use a backup video. Disclose that the judged run is local; do not represent it as the cloud path.

---

## Checkpoint 11 — Demo Hardening and Managed Integrations

### Prerequisite

Checkpoint 10 has a green core cloud path or an explicit local-only fallback decision.

### Objective

Harden the demonstrated path, add operational visibility, and attempt only the managed integrations that cannot threaten the stable release.

### Mandatory scope

- Add structured CloudWatch or local metrics for:
  - decision count and outcomes;
  - policy latency;
  - guide-back success;
  - approval age;
  - ledger verification failures.
- Add UI loading, error, stale, disconnected, and fallback-mode checks.
- Test approval approve, reject, expiry, replay, wrong binding, and stale version through the deployed interface.
- Test Bedrock, storage, policy-engine, and network failure behavior.
- Capture screenshots of the five hero states.
- Add `scripts/run_checkpoint_11.sh`.

### Optional scope, in order

1. Step Functions callback while preserving the local approval adapter.
2. EventBridge fan-out after authoritative ledger append.
3. S3 redacted trace archive.

Cognito, Object Lock, additional provenance fields, and a frontend rewrite remain stretch work. OpenSearch, real integrations, multi-tenancy, billing, and policy-authoring features remain cut.

### Acceptance tests

- Every mandatory failure path is understandable in the UI and fails safely.
- Approval tokens or Step Functions task tokens never reach the browser or trace.
- Managed approval, if enabled, is bound to the same trace/action/state/policy fields.
- Event fan-out, if enabled, is not authoritative for ledger ordering.
- All optional integrations can be disabled without breaking the core journey.
- Local and cloud modes are labelled truthfully.
- Full earlier checkpoint suite remains green.

### Exit gate

Checkpoint 11 is complete when the core demo is resilient and observable. Optional managed integrations may remain incomplete without blocking completion if their fallbacks are tested and clearly disclosed.

---

## Checkpoint 12 — Submission Freeze and Prototype Completion

### Prerequisite

The selected local/cloud release path is stable and no mandatory implementation checkpoint is red.

### Objective

Freeze one exact artifact, verify all claims, and package a reliable four-minute demonstration and submission.

### In scope

- Freeze code, policy, schemas, fixtures, model configuration, and infrastructure parameters.
- Run the final evaluation target:
  - preferred: 20 attack and 30 benign runs;
  - minimum: six core attack classes plus at least ten benign variants.
- Generate the final results JSON and human-readable report.
- Update architecture to match the actual release.
- Complete the real/mock/deferred disclosure table.
- Finalize README setup, reset, demo, evaluation, deployment, rollback, and limitation instructions.
- Prepare the four-minute script, architecture visual, and metrics slide.
- Record a complete backup video.
- Store local copies of essential assets.
- Run three timed rehearsals; at least two must pass from a clean reset.
- Verify every submission link from a clean browser.
- Identify the exact release revision and create the final tag as an explicit operator action.

### Mandatory submission artifacts

```text
README.md
docs/architecture/
docs/demo/FOUR_MINUTE_SCRIPT.md
docs/results/evaluation.json
docs/results/evaluation.md
docs/REAL_MOCK_DEFERRED.md
docs/KNOWN_LIMITATIONS.md
docs/releases/final-release.json
docs/assets/screenshots/
backup demo video location recorded in the release manifest
```

### Final smoke matrix

- Benign enforce completes.
- Adversarial shadow completes and records counterfactual violations.
- Adversarial enforce corrects weight and carrier and pauses for approval.
- Approval confirms exactly once and sends one simulated notification.
- Rejection and expiry cancel and release the reservation.
- Clean chain verifies.
- Disposable tampered chain identifies the first bad sequence.
- Active model, policy, storage, approval, and deployment modes are visible.
- Cloud path passes if it is part of the submitted claim.
- Local/offline fallback passes independently.
- Backup video plays without network access.

### Exit gate: definition of prototype complete

The prototype is finished only when all of the following are true:

1. The primary four-minute journey passes twice from a clean reset.
2. The local fallback passes once without cloud or Bedrock.
3. All claimed integrations are active and visible during their relevant proof, or clearly labelled as fallback/deferred.
4. Results are reproducible and include exact denominators.
5. The release has no known P0/P1 defect in the primary journey.
6. The source revision, policy bundle, fixture checksum, model mode, deployment mode, and artifact hashes are pinned.
7. Documentation, screenshots, architecture, video, and links match the exact frozen build.
8. No unsupported production, compliance, or immutability claim remains.

### Final release decision

- **GO:** all mandatory exit conditions pass and the claimed demo route is stable.
- **CONDITIONAL GO:** the complete local path passes, but one or more cloud/managed integrations are disclosed as unavailable and excluded from claims.
- **NO-GO:** the primary journey, approval exact-once behavior, provenance correction, Cedar authorization claim, or ledger verification is unreliable.

## 4. Permanent cut list

The following work does not belong in these completion checkpoints:

- Real WMS, TMS, carrier, payment, SMS, or ONDC integrations.
- Route optimization.
- OpenSearch.
- Blockchain.
- Multi-tenancy, billing, or complete user administration.
- Broad policy authoring, replay, behavioral baselining, or collusion analysis.
- Production PII processing or compliance certification.
- A dashboard redesign that does not improve the four-minute proof.

## 5. Current handoff

**Completed checkpoint:** 6 — Stable Local Release and Evaluation Baseline  
**Evidence:** 119 tests; 22/22 labelled cases; 10/10 attacks detected; 12/12 benign cases passed; 0/12 false positives; 2/2 guide-backs; browser smoke passed  
**Current checkpoint:** 7 — Cedar Authorization Parity  
**Current status:** Ready to plan and implement  
**Do not begin yet:** DynamoDB, Strands/Bedrock, or AWS deployment  
**Checkpoint 6 implementation:** [`CHECKPOINT_6_IMPLEMENTATION_PLAN.md`](CHECKPOINT_6_IMPLEMENTATION_PLAN.md)  
**Checkpoint 6 results:** [`results/checkpoint-6-evaluation.md`](results/checkpoint-6-evaluation.md)
