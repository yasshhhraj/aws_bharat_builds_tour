# Checkpoint 11 Implementation Plan — Local Prototype Hardening

**Plan version:** 1.0

**Created:** 20 September 2026

**Implementation branch:** `checkpoint-11-hardening`

**Baseline revision:** `3cfd17c` (`main` and the Checkpoint 11 branch)

**Depends on:** Completed Checkpoints 8, 9, and 10

**Next checkpoint:** AWS demo deployment

## 1. Objective

Turn the completed local prototype into a stable, truthful, reproducible demo
candidate without changing its governance semantics.

Checkpoint 11 is hardening and packaging work. It must improve diagnostics,
operator states, startup, test coverage, documentation, and evidence while
preserving the behavior already proved by Cedar, DynamoDB Local, Strands, and
Bedrock Mantle.

Checkpoint 11 succeeds when a new developer can start the recorded-model demo
with one command, execute the complete governed journey, understand every
important state in the dashboard, and reproduce the acceptance evidence without
an AWS credential or paid model call.

## 2. Verified starting state

The branch was clean before this plan was added. The following baseline was
verified on 20 September 2026:

```text
Git revision:                         3cfd17c
Python suite:                        201 passed, 15 skipped
Checkpoint 10 Mantle live gate:     3 passed in 55.83 seconds
Checkpoint 9/10 runtime:            Strands 1.56.0
Recorded provider:                  manifest-recorded-v1
Selected hosted provider:           Bedrock Mantle / qwen.qwen3-coder-next
Policy engine in acceptance path:   Cedar 4.12.0
Durable local store:                DynamoDB Local 2.5.4, digest pinned
Evaluation cases:                   22/22 passing
Functional digest:                  sha256:99d44f22a833007bd2caa5121c2330b7222537633501590b1b43266c04b11120
```

The live Mantle result is already committed evidence. It is not rerun during
ordinary Checkpoint 11 development.

## 3. Non-negotiable invariants

The following contracts are frozen for this checkpoint:

1. Cedar remains authoritative for every governed tool attempt.
2. No model or dashboard code can execute an operational effect directly.
3. The ten governed tools, their ownership, and their input schemas do not
   change.
4. The `demo-v1` Cedar schema, policy behavior, and stable reason codes do not
   change.
5. Approval remains bound to trace, action hash, state hash, policy version,
   expiry, and optimistic version.
6. Booking confirmation, cancellation, notification, and approval resolution
   remain exact-once and idempotent across restart.
7. Ledger canonicalization, event hash vectors, sequence handling, and
   first-bad-sequence verification do not change.
8. DynamoDB keys, serialized records, and storage versioning do not change.
9. A provider failure fails the current trajectory closed. There is no silent
   provider switch or continuation under another model.
10. The recorded model remains the deterministic, no-network acceptance oracle.
11. All data and effects remain synthetic and are labelled as such.
12. Previous checkpoint evidence files are immutable. CP11 writes new files.

If a proposed change requires altering any frozen contract, stop that work
package, document the failing test that requires the change, and review the
scope before proceeding.

## 4. Explicit non-goals

Do not add the following during Checkpoint 11:

- AWS application deployment, Lambda, API Gateway, Amplify, or managed
  DynamoDB;
- native Nova migration;
- a second agent framework or a frontend framework migration;
- production authentication, user accounts, or real logistics connectors;
- autonomous planning beyond the existing bounded four-role workflow;
- a new policy family, storage schema, ledger format, or approval workflow;
- automatic provider fallback;
- a paid provider call in the default startup or acceptance script; or
- broad visual redesign unrelated to the required states.

## 5. Current hardening gaps

The current implementation is functionally healthy, but these issues must be
closed before it is a local submission candidate:

| Gap | Current evidence | Required CP11 outcome |
|---|---|---|
| Stale product metadata | FastAPI still says `Manifest Checkpoint 7 API` | Product metadata is checkpoint-neutral and comes from one version source |
| Incomplete environment display | Dashboard shows runtime, policy, storage, and approval only | Provider, requested/resolved model, route, fallback state, policy, storage, and ledger state are visible |
| Weak failed-run browser contract | `POST /v1/runs` returns an unstructured failed summary with HTTP 500 | Safe failure code and trace ID let the dashboard load and explain the failed trace |
| Missing explicit error states | Provider and exact-once states collapse into generic messages | Timeout, rate limit, denial, approval, replay/exact-once, and tamper states have distinct copy and styling |
| Provider prose can become an event summary | Role completion returns `str(result)` | Retained role-completion summaries are deterministic and bounded |
| Startup is multi-step | Docker, table, Cedar, environment, and API are started separately | One loopback-only startup command validates dependencies and starts the stack |
| Acceptance is fragmented | Earlier checkpoint scripts overlap and one compatibility script has stale numbering | One CP11 gate is canonical; old scripts remain compatible |
| Browser evidence is stale | Checkpoint 6 smoke text disclaims later components | New CP11 browser/rehearsal evidence truthfully records the active local stack |
| Submission claims are stale | Progress report predates Cedar, DynamoDB, Strands, and Mantle | README and current progress summary match the implemented state |

## 6. Architecture boundary for hardening

All new presentation data must be derived through existing read-only service and
projection boundaries:

```text
RuntimeSettings.describe() -----------+
PolicyEngine.describe() --------------+--> /health/ready --> environment panel
Store.describe() ---------------------+

TrajectoryState (copy from store)
          |
          v
Dashboard projection + trace events ------> browser state panels

Provider failure
          |
          v
sanitized Manifest error --> RUN_FAILED event --> safe API envelope --> UI state
```

The browser must not reconstruct authorization outcomes, commitment amounts,
approval validity, or ledger validity. Those remain server-owned facts.

## 7. Planned deliverables

### Application and API

- checkpoint-neutral FastAPI metadata;
- one safe failed-run API envelope carrying `error.code`, `error.message`, and
  `trace_id` without raw provider text;
- optional failure classification in the read model, derived from the retained
  `RUN_FAILED` event rather than a storage migration;
- correct fixed-route `resolved_model_id` disclosure when the selected model is
  known, while router-based resolution remains null/unknown;
- read-only exact-once receipt information in the dashboard projection;
- startup/configuration validation for only the selected provider.

### Dashboard

- expanded environment panel;
- explicit banners or cards for the required failure and pause states;
- exact-once confirmation/notification receipt display;
- persistent synthetic/local/recorded labels;
- accessible focus, keyboard, live-region, contrast, and small-screen behavior;
- no external scripts, fonts, analytics, or CDNs.

### Scripts and documentation

- `scripts/start_checkpoint_11_local.sh` — canonical loopback-only startup;
- `scripts/run_checkpoint_11.sh` — canonical no-paid-call acceptance gate;
- `scripts/check_submission_hygiene.py` — high-confidence secret, absolute-path,
  and stale-claim checks with a small reviewed allowlist;
- `docs/manual/CHECKPOINT_11_LOCAL_DEMO.md` — setup and operator runbook;
- new CP11 evaluation, browser-smoke, rehearsal, release-manifest, and completion
  evidence;
- README and current progress-report updates.

## 8. Implementation sequence

Only one work package should be in progress at a time. Commit each passing
package separately so it can be reverted without discarding later work.

### Phase 0 — Protect and record the baseline

1. Confirm the branch and clean state:

   ```bash
   git branch --show-current
   git status --short
   git rev-parse HEAD
   ```

2. Run the no-network baseline:

   ```bash
   .venv/bin/pytest -q
   ./scripts/run_checkpoint_10_bedrock_mantle.sh --offline
   ```

3. Record but do not regenerate or overwrite CP9/CP10 evidence.
4. Record the baseline functional digest and policy bundle identity.

**Gate:** `201 passed, 15 skipped` remains the expected ordinary suite result,
and the CP10 offline provider contract passes.

### Phase 1 — Add characterization tests before changing behavior

Add tests that capture the current protected behavior and the new hardening
contract before editing implementation files.

Required characterization coverage:

- health diagnostics never contain a credential, provider endpoint credential,
  local user path, or AWS account identifier;
- recorded mode starts with OpenRouter, Mantle, and AWS credentials absent;
- selecting OpenRouter or Mantle without its required key produces the stable
  `PROVIDER_CONFIGURATION_ERROR` and does not start a run;
- a fixed provider/model has a known resolved model; a router does not claim
  one;
- provider timeout, rate-limit, authentication, billing, missing-model, and
  availability errors keep their stable sanitized codes;
- a failed run has a retained trace, valid ledger, no confirmation effect, no
  notification effect, and a safe failure code;
- the model prompt contains only role, phase, synthetic order reference, and
  bounded task instructions;
- tool results sent back to the model omit authority fields, idempotency keys,
  recipient content, and unneeded state;
- raw model prose is not retained as the authoritative role-completion event;
- dashboard projection is read-only and derives exact-once receipts from stored
  state/events.

Suggested test locations:

```text
tests/agents/test_runtime_settings.py
tests/agents/test_provider_errors.py
tests/agents/test_strands_tools.py
tests/integration/test_strands_provider_runtime.py
tests/e2e/test_checkpoint_11_hardening.py
tests/unit/test_dashboard_projection.py
```

**Gate:** New tests fail for only the intended missing CP11 behavior; all prior
tests stay green.

### Phase 2 — Harden diagnostics and startup validation

1. Make FastAPI metadata checkpoint-neutral. Do not use checkpoint numbering as
   the application semantic version.
2. Keep the package version unchanged during hardening unless an explicit
   release/tag decision is made.
3. Centralize requested/resolved model disclosure:
   - `recorded` and explicit fixed routes may disclose the selected model as
     resolved;
   - `openrouter/free` remains unresolved unless the provider returns a model;
   - `provider_fallback_active` is always false.
4. Validate only the configured provider:
   - recorded mode must not require any network key;
   - OpenRouter requires `OPENROUTER_API_KEY` only when selected;
   - Mantle requires `BEDROCK_MANTLE_API_KEY` only when selected;
   - native Bedrock uses the normal AWS credential chain and must not demand
     literal credentials in project configuration.
5. Convert missing optional configuration into a stable, secret-safe readiness
   result or startup error. Never echo the supplied value.
6. Add tests for every allowed and rejected configuration combination.

Files expected to change:

```text
apps/api/main.py
apps/api/schemas.py
apps/runtime/runtime_settings.py
apps/runtime/model_factory.py
tests/agents/test_runtime_settings.py
tests/agents/test_model_factory.py
tests/cedar/test_api_health.py
tests/e2e/test_checkpoint_5_dashboard.py
```

**Gate:** recorded mode starts with all hosted-provider credentials removed;
selected hosted providers fail early and safely when misconfigured.

### Phase 3 — Make failed runs inspectable without weakening fail-closed behavior

1. Preserve the existing failed trace and its valid ledger.
2. For a failed `POST /v1/runs`, return a documented safe error envelope with:

   ```json
   {
     "error": {
       "code": "PROVIDER_TIMEOUT",
       "message": "Bedrock Mantle model request timed out.",
       "trace_id": "TR-..."
     }
   }
   ```

3. Map categories deliberately:
   - timeout: HTTP 504;
   - rate limit: HTTP 429;
   - provider authentication, billing, missing model, or unavailable: HTTP 503;
   - malformed client request: HTTP 422;
   - policy denial/block: a created, inspectable run with status `blocked`, not
     a provider failure.
4. Extend the browser API error object to retain the safe trace ID.
5. If a trace ID is present, load that trace and render the terminal state while
   also showing the error banner.
6. Prove that failure occurs before protected commitment and that ledger
   verification still succeeds.

Do not add `error_code` to persisted `TrajectoryState` in this checkpoint. Read
it from the last `RUN_FAILED` event to avoid a storage-codec migration.

**Gate:** every injected provider failure is classified, inspectable, ledger
valid, and effect-free.

### Phase 4 — Bound prompts and retained model output

1. Keep the current role prompt allowlist: role, phase, synthetic order ID, and
   bounded objective only.
2. Keep authority, approval binding, idempotency values, trace internals, and
   operational credentials inside application-owned binders.
3. Continue returning only the minimum governed tool result needed by the next
   model action.
4. Replace free-form provider completion text in retained role events with a
   deterministic application-owned summary after `context.assert_complete()`.
5. Keep provider usage and latency fields nullable; do not invent missing
   values.
6. Add maximum-length and secret-like-key assertions for retained diagnostic
   details.

This phase must not change the prompt objective, tool schemas, completion
predicate, turn limit, or timeout behavior unless a new characterization test
demonstrates an existing defect.

**Gate:** recorded-runtime parity and the CP10 fake-hosted provider tests pass;
the functional evaluation digest is unchanged.

### Phase 5 — Expand the dashboard environment and state model

The environment panel must display, using server-provided values:

| Field | Expected recorded-demo value |
|---|---|
| Runtime | `strands` |
| Provider | `recorded` |
| Requested model | `manifest-recorded-v1` |
| Resolved model | `manifest-recorded-v1` |
| Route | `fixed`; no fallback |
| Policy | `cedar / demo-v1` plus shortened bundle identity |
| Storage | `dynamodb_local` |
| Ledger | `sha256 / ledger-event-v1`; current trace valid/invalid |
| Data/effects | `synthetic / simulated` |

Required distinct operator states:

| Condition | Dashboard behavior |
|---|---|
| Provider timeout | Red terminal banner; trace remains loadable; retry starts a new trace |
| Provider rate limit | Amber/red provider banner; no automatic retry or fallback |
| Authorization denial | `BLOCKED` state with Cedar reason code and no protected effect |
| Approval required | Pending approval panel bound to action/state hashes |
| Duplicate/idempotent replay | Exact-once receipt indicates one confirmation and one notification |
| Tamper detected | Invalid ledger state, first bad sequence, approval controls disabled |
| Backend disconnected | Controls disabled without clearing the last displayed trace |

Implementation rules:

- prefer small changes to `index.html`, `render.js`, and `styles.css`;
- keep all values rendered with `textContent`, never provider-controlled HTML;
- do not duplicate policy or spend calculations in JavaScript;
- preserve the existing trace URL and refresh behavior;
- ensure status is never communicated by color alone;
- move focus to the result/error summary after a run action;
- keep 44-pixel controls, visible focus, skip navigation, and usable 320-pixel
  layout;
- keep all assets local.

**Gate:** existing dashboard tests plus new state-contract tests pass. A manual
keyboard and narrow-screen smoke test is recorded.

### Phase 6 — Add the one-command local startup path

Create `scripts/start_checkpoint_11_local.sh` with these properties:

1. `set -eu`; resolve paths relative to the repository, not the caller's home.
2. Check Python environment, Docker, Cargo, and required local ports before
   starting child processes.
3. Start the digest-pinned DynamoDB Local service and run the idempotent table
   setup.
4. Build the pinned Cedar sidecar with `cargo build --locked`.
5. Bind Cedar and Uvicorn to `127.0.0.1` only.
6. Export the fixed recorded-mode environment:

   ```text
   MANIFEST_AGENT_RUNTIME=strands
   MANIFEST_MODEL_PROVIDER=recorded
   MANIFEST_MODEL_ID=manifest-recorded-v1
   MANIFEST_POLICY_ENGINE=cedar
   MANIFEST_STORAGE_BACKEND=dynamodb
   ```

7. Use a CP11-specific namespace so earlier evidence is not modified.
8. Validate the readiness endpoint before printing the dashboard URL.
9. Trap exit and stop only the Cedar/API child processes started by the script.
   Do not remove the DynamoDB volume.
10. Never print or persist hosted-provider credentials.

Approval and tamper secrets are local operator inputs. The runbook must explain
how to export them. The startup script must reject `.env.example` placeholder
values and must never bind a known placeholder secret to a non-loopback host.

**Gate:** from a fresh shell, one command reaches a ready recorded/Cedar/
DynamoDB Local dashboard. Interrupting it leaves no orphan Cedar or Uvicorn
process.

### Phase 7 — Add the canonical CP11 acceptance gate

Create `scripts/run_checkpoint_11.sh`. Its default path must make no hosted
provider call and should execute in this order:

1. verify dependency pins and working prerequisites;
2. start and initialize digest-pinned DynamoDB Local;
3. build and test Cedar with `--locked`;
4. start Cedar on a dedicated loopback port and validate bundle identity;
5. set recorded Strands, Cedar, and DynamoDB Local modes explicitly;
6. run the complete Python suite;
7. run the shared memory/DynamoDB repository and restart/concurrency contracts;
8. run benign enforce, adversarial shadow, adversarial enforce/pending,
   approve, reject, expiry, and exact-once replay journeys;
9. run disposable tamper detection without touching the primary trace;
10. execute the clean automated rehearsal twice with a reset between runs;
11. generate CP11 evaluation JSON/Markdown;
12. assert the CP11 functional digest equals the CP9 recorded-runtime digest;
13. run submission hygiene checks;
14. build a separate CP11 release manifest; and
15. stop Cedar through a trap while leaving the local database recoverable.

Do not implement the gate by invoking every old checkpoint script; that repeats
slow setup and creates port/process conflicts. CP11 should be a single superset
gate. Keep earlier scripts working for historical reproduction.

Normalize the confusing Mantle script naming without breaking callers:

- move the shared body to a provider-named helper;
- retain `run_checkpoint_10_bedrock_mantle.sh` as the documented historical
  wrapper;
- retain the existing stale wrapper only as a deprecated forwarder until after
  final submission.

Live Mantle verification remains a separate, explicit, billable command guarded
by `MANIFEST_RUN_LIVE_BEDROCK_MANTLE=1`. It is not part of CP11 acceptance.

**Gate:** `./scripts/run_checkpoint_11.sh` passes twice consecutively from a
clean namespace.

### Phase 8 — Documentation, hygiene, and evidence

1. Update README current status, setup, startup, acceptance, and limitations.
2. Replace the outdated progress summary with current facts; keep old checkpoint
   reports as historical evidence.
3. Add a repository-owned hygiene check for:
   - private-key blocks;
   - high-confidence AWS/OpenRouter/Mantle key shapes;
   - bearer tokens or credentials in tracked configuration;
   - `/home/<user>` and other personal absolute paths in submission-facing
     documents;
   - stale claims in README, API metadata, dashboard copy, current progress
     summary, and CP11 evidence.
4. Do not use a naive search for the word `secret`; tests and documentation
   intentionally discuss secrets. Use precise patterns and a reviewed allowlist.
5. Create new evidence paths:

   ```text
   docs/results/checkpoint-11-local-evaluation.json
   docs/results/checkpoint-11-local-evaluation.md
   docs/results/checkpoint-11-browser-smoke.md
   docs/results/checkpoint-11-rehearsal-1.md
   docs/results/checkpoint-11-rehearsal-2.md
   docs/releases/checkpoint-11-local-candidate.json
   docs/assets/screenshots/checkpoint-11-*.png
   docs/CHECKPOINT_11_COMPLETION_REPORT.md
   ```

6. The release manifest must accurately say:
   - deployment: local;
   - runtime: Strands;
   - provider: recorded;
   - policy: local loopback Cedar;
   - storage: DynamoDB Local;
   - logistics effects: synthetic/simulated;
   - separate CP10 evidence proves paid Mantle inference;
   - AWS application deployment is not yet complete.

**Gate:** hygiene scan passes, all claims are source-backed, and no earlier
evidence artifact changed.

## 9. Regression cadence

Use the smallest relevant gate while editing, followed by the larger gate at
each package boundary:

| Change area | Inner-loop test | Package gate |
|---|---|---|
| Runtime/config | `pytest -q tests/agents` | CP10 offline provider contract |
| API/read model | focused API and health tests | full Python suite |
| Projection/UI | dashboard projection and E2E tests | full Python suite plus browser smoke |
| Startup script | shell syntax + readiness smoke | clean-shell startup rehearsal |
| Acceptance/evidence | focused script invocation | full CP11 gate twice |
| Docs/claims | hygiene checker | final CP11 gate |

After any change to `apps/runtime`, `packages/governor`, `packages/approvals`,
`packages/storage`, `packages/ledger`, or `policies`, immediately run the full
Python suite and the applicable Cedar/storage contract. Do not accumulate
multiple unverified changes in those areas.

## 10. Required acceptance matrix

| Journey | Required terminal state | Critical assertions |
|---|---|---|
| Benign enforce | `completed` | INR 3,400 committed; one booking; one notification; valid ledger |
| Adversarial shadow | `completed` | counterfactual interventions recorded; simulated path disclosed |
| Adversarial enforce | `pending_approval` | 50→500 kg guide-back; certified carrier; INR 4,550 projected vs INR 4,000 ceiling |
| Approve | `completed` | bound approval; fresh Cedar check; one confirmation and notification |
| Approval replay | unchanged `completed` | idempotent replay; no extra effect or ledger event |
| Reject | `cancelled` | prepared action cancelled exactly once; no confirmation/notification |
| Expire | `cancelled` | expiry reason retained; prepared action cancelled exactly once |
| Restart/resume | expected state retained | pending approval survives service reconstruction and resolves once |
| Provider timeout/rate limit | `failed` | safe code; valid ledger; no protected commitment; no fallback |
| Authorization denial | `blocked` | Cedar reason visible; blocked effect absent |
| Disposable tamper | primary trace unchanged | first bad sequence reported; invalid trace cannot approve |
| Reset | clean namespace | only configured synthetic namespace removed |

Every journey must assert both terminal state and protected side effects. A
green HTTP response alone is not sufficient.

## 11. Manual operator work

Automation cannot complete the visual and recording checks. After the automated
gate passes, the owner must perform these tasks locally:

1. Start the stack with `./scripts/start_checkpoint_11_local.sh`.
2. Open the printed loopback dashboard URL in a clean browser profile.
3. Verify the environment panel says recorded model, Cedar, DynamoDB Local,
   local deployment, and synthetic effects.
4. Complete benign, adversarial pending approval, approval, shadow, and
   disposable-tamper journeys.
5. Repeat the complete demo once more after reset.
6. Test keyboard-only navigation, visible focus, the skip link, and approval
   controls.
7. Test at approximately 320, 768, and 1440 CSS pixels; record any clipping or
   horizontal scrolling.
8. Capture sanitized screenshots only after checking for:
   - API keys, secrets, account IDs, email addresses, browser profiles, and
     terminal history;
   - personal absolute paths;
   - unexpected model/provider claims; and
   - unrelated browser tabs or notifications.
9. Record a short backup demo. Keep secrets and AWS console pages out of the
   recording.
10. Fill both rehearsal records with duration, result, defects, and exact source
    revision.

Do not commit the raw video unless repository size and submission rules have
been reviewed. Record its filename and SHA-256 digest in the completion report.

## 12. Risk controls and rollback

| Risk | Prevention | Detection | Recovery |
|---|---|---|---|
| Governance regression | Freeze Cedar/tool contracts | policy/evaluation parity gates | Revert only the failing work-package commit |
| Ledger/storage break | No codec/key/canonical changes | hash vectors, restart, concurrency, tamper tests | Restore last passing package; do not migrate local data |
| UI duplicates domain logic | Server-owned projections only | projection/API equality tests | Remove client calculation and expose read-only field |
| Provider key leak | Environment-only keys, precise hygiene scan | tracked-file and screenshot review | Revoke key immediately; remove from history before sharing |
| Paid call during local gate | Recorded provider forced by script | assert provider in health/evidence | abort gate; rotate accidental key if exposed |
| Orphan process/port conflict | preflight plus shell traps | post-exit port check | stop only recorded child PID; never broad-kill processes |
| Stale/overstated claims | scoped claim checker and manual review | final evidence audit | correct claims; regenerate only CP11 artifacts |
| Evidence overwritten | checkpoint-specific output names | `git diff --name-status` review | restore historical file from its committed revision |

Never use `git reset --hard`, delete the DynamoDB volume, or overwrite prior
checkpoint evidence as a rollback technique.

## 13. Commit boundaries

Recommended commits:

1. `test(cp11): characterize hardening contracts`
2. `feat(cp11): harden diagnostics and failed-run API state`
3. `feat(cp11): add truthful operator states and exact-once receipts`
4. `chore(cp11): add local startup and acceptance gates`
5. `docs(cp11): add runbook, evidence, and current claims`

Do not combine policy, persistence, runtime, UI, and generated-evidence changes
in one commit.

## 14. Definition of done

Checkpoint 11 is complete only when every item is true:

- [ ] Baseline and new characterization tests pass.
- [ ] Recorded mode starts without any hosted-provider credential.
- [ ] Selected-provider configuration errors are early, stable, and secret-safe.
- [ ] Runtime/provider/model/policy/storage/ledger/simulation state is visible.
- [ ] Timeout, rate limit, authorization denial, approval, exact-once replay,
      and tamper states are distinguishable.
- [ ] Provider prose is not trusted as retained completion evidence.
- [ ] One startup command produces the loopback local demo.
- [ ] One no-paid-call acceptance command proves the entire local candidate.
- [ ] Python, Rust, Cedar, storage, evaluation, browser, hygiene, and rehearsal
      gates pass.
- [ ] The functional digest matches the completed recorded-runtime baseline.
- [ ] The full automated rehearsal passes twice from clean state.
- [ ] Two manual browser rehearsals are recorded.
- [ ] Screenshots and backup video pass manual secret/privacy review.
- [ ] README, API metadata, dashboard, progress report, and release manifest make
      no stale or cloud-deployment claim.
- [ ] CP10 Mantle evidence is referenced but not rerun or overwritten.
- [ ] Earlier checkpoint evidence is unchanged.
- [ ] A completion report records exact commands, counts, hashes, limitations,
      and remaining AWS deployment work.

## 15. Stop conditions

Stop implementation and investigate before continuing if any of these occurs:

- the functional digest changes;
- an existing ledger hash vector changes;
- approval replay creates another confirmation, cancellation, notification, or
  ledger event;
- recorded mode attempts a network request or asks for a hosted-provider key;
- a provider error reaches an API, trace, log, screenshot, or report with raw
  response text or credential material;
- the local script binds Cedar, DynamoDB, or the API to a non-loopback address;
- a failed or blocked run leaves a protected commitment not represented by the
  expected prepared/cancelled state;
- the default acceptance gate incurs hosted-provider cost; or
- a CP6–CP10 evidence file is modified.

These are correctness failures, not items to waive for demo convenience.
