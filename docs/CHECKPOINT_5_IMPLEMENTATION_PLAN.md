# Checkpoint 5 Implementation Plan — API-Driven Operator Dashboard

## 1. Objective

Build a single-page local operator dashboard on top of the stable Checkpoint 4
runtime, APIs, approval flow, and tamper-evident ledger.

The dashboard must let a user complete the primary Manifest demonstration
without opening a terminal:

```text
open dashboard
    -> health and active runtime modes are visible
    -> select ORD-8842, shadow/enforce, benign/adversarial
    -> start a real API-backed run
    -> inspect four agents, tool attempts, and policy decisions
    -> see 500 kg -> 50 kg -> 500 kg provenance
    -> see spend against the INR 4,000 ceiling
    -> approve or reject the exact pending action
    -> refresh the same trace after resume/cancellation
    -> verify the ledger
    -> optionally tamper with a separate disposable trace and see verification fail
```

Checkpoint 5 is a presentation and read-model checkpoint. It must not redesign
the agents, policy engine, commitment state machine, approval binding, or ledger
hashing introduced in Checkpoints 1-4.

## 2. Baseline and relationship to earlier checkpoints

### 2.1 Verified starting state

At plan creation, the repository has:

```text
85 passed in 2.66s
```

Checkpoint 5 starts only from this green baseline. All existing tests and all
four earlier checkpoint scripts remain release gates.

### 2.2 Current frontend-tooling constraint

The workspace currently reports:

```text
node: command not found
```

To keep this checkpoint beginner-friendly, offline-capable, and independent of
a new toolchain, the first dashboard will use:

- semantic HTML;
- plain CSS;
- small browser-native JavaScript modules;
- inline SVG generated from real projection data; and
- FastAPI/Starlette static-file serving.

No npm package, CDN, React runtime, bundler, or network download is required.
The API and projection contracts will be framework-neutral, so a later React +
TypeScript frontend can consume the same responses without backend redesign.

### 2.3 Checkpoint 1-4 capabilities that must remain intact

- Four deterministic agent roles and bounded orchestration.
- Shadow and enforce modes.
- Benign and adversarial scenarios.
- Six deterministic policy families and controlled reasons.
- Weight provenance and cold-chain guide-back.
- Prepare/approve/reject/expire/confirm/cancel behavior.
- Exact-once mock effects and approval replay handling.
- Hash-chained events and separate per-trace heads.
- Clean/tampered verification and first-bad-sequence reporting.
- Disabled-by-default tamper mutation.
- Existing CLI behavior and every existing API path.

### 2.4 Required compatibility behavior

- Existing API fields retain their meaning.
- New API fields and endpoints are additive.
- The dashboard never contains static fake trace results.
- The dashboard does not bypass the governor or call mock tools directly.
- Approval and tamper secrets are entered by the operator and never compiled
  into JavaScript, URLs, logs, events, or browser storage.
- A browser refresh can restore a trace from `?trace_id=...` while the same
  in-memory backend process remains alive.
- The CLI continues to work when dashboard files are unavailable.
- API and dashboard use the same origin, so CORS is not added for the local
  checkpoint.

## 3. Scope

### 3.1 Included

- One responsive dashboard page served at `/dashboard/`.
- Environment and dependency health banner.
- Order, governance-mode, and scenario controls.
- Run, reset, and refresh actions.
- Current trace ID, status, workflow stage, and selected resources.
- Spend gauge and spend timeline.
- Transparent demo risk-signal score and trajectory chart.
- Four-agent trace timeline.
- Policy-decision feed with intervention filters.
- Decision detail with reason, policy signals, guidance, and latency.
- Weight-provenance panel showing authoritative and attempted values.
- Pending-approval card with approve/reject controls.
- Ledger-integrity badge and verification detail.
- Optional disposable tamper demonstration when the backend advertises it.
- Loading, empty, stale, disconnected, validation, and server-error states.
- A backend projection endpoint for stable dashboard-specific derived data.
- Static asset and projection API tests.
- Browser smoke tests and a Checkpoint 5 verification script.
- README and `.env.example` updates.

### 3.2 Explicitly excluded

- React, TypeScript, Vite, npm, Recharts, React Flow, or another build system.
- DynamoDB, Lambda, API Gateway, Amplify, or cloud hosting.
- WebSockets, server-sent events, or real-time push.
- User accounts, Cognito, sessions, cookies, or production authentication.
- Policy editing, fixture editing, trace search, pagination, or replay.
- Multiple-order comparison views.
- A general admin panel.
- Mobile-native applications.
- Real customer data or operational connectors.
- A production risk model or prediction claim.
- Changing event hashes or ledger schema for visual convenience.

### 3.3 Scope guard

Checkpoint 5 is complete when the complete local primary journey works from the
browser against real APIs, all important states remain usable at desktop and
mobile widths, and the original 85-test baseline remains green.

Do not add React or AWS while a dashboard MUST acceptance test is red.

## 4. User-visible journeys

### 4.1 First load

1. Open `/dashboard/`.
2. The page requests `/health/ready` and `/v1/fixtures/orders`.
3. The header shows:
   - backend ready/disconnected;
   - deterministic runtime;
   - Python reference policy engine;
   - local approval mode;
   - in-memory hash-chain storage; and
   - whether the disposable tamper demo is enabled.
4. `ORD-8842`, `enforce`, and `adversarial` are selected by default for the hero
   path.
5. No trace panels pretend that a run exists.

### 4.2 Shadow demonstration

1. Select `shadow` and `adversarial`.
2. Click **Run shipment**.
3. The real synchronous `POST /v1/runs` request executes.
4. The dashboard loads the run, events, decisions, projection, and verification.
5. Policy cards clearly distinguish:
   - policy outcome such as `GUIDE` or `ESCALATE`; and
   - applied outcome `ALLOW` because the run is in shadow mode.
6. The unsafe mock journey completes while the UI labels every intervention as
   counterfactual (`WOULD GUIDE`, `WOULD ESCALATE`).

### 4.3 Enforce and guide-back demonstration

1. Reset the demo.
2. Select `enforce` and `adversarial`.
3. Run `ORD-8842`.
4. The provenance panel shows:

```text
source fact        500 kg / WEIGHT-ORD-8842 / WMS-SNAPSHOT-001
attempt 1           50 kg / guided
attempt 2          500 kg / allowed
```

5. The carrier decisions show the uncertified carrier guide and certified
   alternative.
6. Spend shows INR 3,650 committed + INR 900 reserved = INR 4,550 projected,
   above the INR 4,000 ceiling.
7. The run status is `PENDING_APPROVAL`.

### 4.4 Approval journey

1. The approval card loads the exact approval record.
2. It displays amount, action ID, expiry, version, and shortened action/state
   hashes.
3. The operator enters:
   - an allowlisted synthetic approver label;
   - optional comment;
   - demo approval secret; and
   - approve or reject.
4. The secret is sent only in `X-Demo-Approver-Secret` and cleared from the
   input after the request settles.
5. The UI refreshes the same trace after the response.
6. Approve produces `COMPLETED`; reject produces `CANCELLED`.
7. Double submission is prevented in the UI, while backend idempotency remains
   authoritative.

### 4.5 Ledger verification journey

1. The integrity panel calls the real `/verify` endpoint.
2. A clean trace shows `VALID`, checked event count, head sequence, algorithm,
   schema version, and shortened head hash.
3. Verification can be rerun without changing the trace.
4. An invalid result shows `INVALID`, the first bad sequence, and controlled
   failure code without crashing the rest of the dashboard.

### 4.6 Disposable tamper journey

This panel is shown only when health reports `demo_tamper_enabled: true`.

1. Click **Create disposable trace**.
2. The dashboard starts a separate benign enforce run and labels it disposable.
3. Verify it as clean.
4. Enter the demo tamper secret in a password field.
5. Alter a safe default sequence using the existing guarded endpoint.
6. The secret field clears.
7. Verification refreshes and shows the first bad sequence.
8. The primary hero trace remains selected and unchanged.

The UI must never offer tampering against the currently selected primary trace.

## 5. Page structure and wireframe

Use one page with progressive disclosure:

```text
+--------------------------------------------------------------------+
| MANIFEST                                      Backend ● Ready       |
| Trajectory governance before physical commitment                  |
| Runtime: deterministic | Policy: python_reference | Ledger: local  |
+--------------------------------------------------------------------+
| Run controls                                                       |
| Order [ORD-8842]  Mode [ENFORCE]  Scenario [ADVERSARIAL] [RUN]     |
| [Reset] [Refresh]                       Last updated: 12:30:04      |
+--------------------------------------------------------------------+
| Status          | Spend                        | Integrity          |
| PENDING APPROVAL| INR 4,550 / INR 4,000       | VALID / 38 events |
| Carrier stage   | committed + reserved gauge  | sha256 / v1       |
+--------------------------------------------------------------------+
| Spend timeline / trajectory risk signals                           |
+--------------------------------+-----------------------------------+
| Four-agent trace timeline      | Policy decisions                  |
| Inventory                      | [All] [Interventions only]         |
| Dispatch                       | GUIDE — weight mismatch            |
| Carrier                        | GUIDE — cold-chain required        |
| Customer communications       | ESCALATE — approval required       |
+--------------------------------+-----------------------------------+
| Weight provenance             | Pending approval                   |
| 500 kg -> 50 kg -> 500 kg     | exact action + hashes             |
| source and decision status     | [Approve] [Reject]                |
+--------------------------------+-----------------------------------+
| Integrity details / optional disposable tamper demonstration       |
+--------------------------------------------------------------------+
```

### 5.1 Visual hierarchy

- The run status is the strongest visual element.
- `GUIDE`, `BLOCK`, and `ESCALATE` use distinct text, icon, and color—not color
  alone.
- Shadow decisions include a visible `WOULD` label.
- Approval controls appear only when a real pending approval exists.
- Integrity appears on every loaded trace, not only in the tamper demo.
- Raw hashes and detailed event JSON are collapsed by default.

### 5.2 Responsive behavior

- At 1100 px and wider: two-column trace/decision and provenance/approval rows.
- At 700-1099 px: charts remain full width; cards use one or two columns as
  space permits.
- Below 700 px: all sections stack; controls are full width; tables become
  labelled definition lists.
- No horizontal page scroll at 360 px.
- Charts have a textual/table fallback immediately below them.

## 6. Architecture and data flow

```text
Browser at /dashboard/
        |
        +--> static index.html / styles.css / JavaScript modules
        |
        +--> GET /health/ready
        +--> GET /v1/fixtures/orders
        |
        +--> POST /v1/runs
        |       |
        |       v
        |   existing governed runtime
        |
        +--> Promise.all(
        |       GET /v1/runs/{trace_id},
        |       GET /v1/traces/{trace_id}/events,
        |       GET /v1/traces/{trace_id}/decisions,
        |       GET /v1/traces/{trace_id}/projection,
        |       GET /v1/traces/{trace_id}/verify
        |    )
        |
        +--> GET /v1/approvals/{approval_id} when pending
        +--> POST /v1/approvals/{approval_id}
        +--> optional guarded disposable tamper endpoint

FastAPI serves both static assets and APIs on one origin.
```

The dashboard never derives authorization. It renders backend decisions. A
button being disabled is usability behavior, not a security boundary.

## 7. Dashboard projection contract

### 7.1 Why add a projection endpoint

The existing APIs intentionally expose normalized runtime records. A dashboard
should not reproduce domain calculations in JavaScript. Checkpoint 5 therefore
adds one read-only projection:

```http
GET /v1/traces/{trace_id}/projection
```

The projection is derived from a defensive copy of the existing state,
decisions, and ledger events. It creates no new events and changes no business
state.

### 7.2 `RiskSignalPoint`

```python
@dataclass(frozen=True, slots=True)
class RiskSignalPoint:
    sequence: int
    decision_id: str
    family: str
    reason_code: str
    outcome: DecisionOutcome
    delta: int
    total: int
```

The displayed score is a deterministic demo indicator, not a probability or
production risk model.

Scoring contract:

- inspect non-`ALLOW` policy signals in decision order;
- each policy family contributes 20 points the first time it appears;
- repeated violations in the same family do not add more points;
- cap total at 100;
- shadow and enforce use the policy outcome, not the applied outcome; and
- return the method string
  `20_per_unique_non_allow_policy_family_capped_100`.

For the primary enforced fixture, the expected unique families are provenance,
cold-chain, and spend, producing the documented demo score of 60.

The UI label must say **Demo risk signals**, not “probability of failure.”

### 7.3 `SpendPoint`

```python
@dataclass(frozen=True, slots=True)
class SpendPoint:
    sequence: int
    label: str
    committed_minor: int
    reserved_minor: int
    projected_minor: int
    ceiling_minor: int
```

Projection rules:

1. `start` uses `ScenarioConfig.prior_committed_minor` and sequence 1.
2. `prepared` uses `PreparedAction.spend_reserved_after_minor` and the matching
   `prepare_freight_booking` success event sequence.
3. `confirmed`, `cancelled`, or `pending` uses current trace state and its
   matching terminal/latest event sequence.
4. Money remains integer minor units in the API.
5. The browser formats INR; it never performs financial arithmetic.

### 7.4 `WeightProvenanceProjection`

```python
@dataclass(frozen=True, slots=True)
class WeightAttempt:
    sequence: int
    proposal_id: str
    attempted_value: int
    unit: str
    fact_id: str
    policy_outcome: DecisionOutcome
    reason_code: str

@dataclass(frozen=True, slots=True)
class WeightProvenanceProjection:
    fact_id: str
    authoritative_value: int
    unit: str
    source_id: str
    source_hash: str
    attempts: tuple[WeightAttempt, ...]
    final_value: int | None
```

Build attempts by joining `create_dispatch_plan` tool-attempt events to policy
decisions by `proposal_id`. Do not infer by adjacent list index.

### 7.5 `DashboardProjection`

```python
@dataclass(frozen=True, slots=True)
class DashboardProjection:
    trace_id: str
    risk_signal_score: int
    risk_signal_method: str
    risk_points: tuple[RiskSignalPoint, ...]
    spend_points: tuple[SpendPoint, ...]
    weight_provenance: WeightProvenanceProjection | None
```

If an optional projection section cannot be built, return `null` for that
section and keep the rest usable. A missing trace remains `404`.

### 7.6 Projection integrity rule

Projection does not certify ledger integrity. The browser must show projection
data alongside the independent `/verify` result. If verification is invalid:

- show a persistent warning;
- keep data visible for diagnosis;
- label it “retained data failed integrity verification”; and
- disable approval and tamper actions for that trace.

## 8. Browser application state

Keep one explicit state object in `state.js`:

```javascript
const state = {
  health: null,
  fixtures: [],
  selection: {
    orderId: "ORD-8842",
    mode: "enforce",
    scenario: "adversarial",
  },
  activeTraceId: null,
  run: null,
  events: [],
  decisions: [],
  approval: null,
  projection: null,
  verification: null,
  loading: false,
  action: null,
  error: null,
  lastUpdatedAt: null,
  staleAfterMs: 10000,
};
```

Allowed top-level UI states:

```text
BOOT_LOADING
READY_EMPTY
STARTING_RUN
TRACE_LOADING
TRACE_READY
SUBMITTING_APPROVAL
RESETTING
DISCONNECTED
ERROR
```

State transitions happen only through named functions such as
`startSelectedRun`, `loadTrace`, `resolveApproval`, `resetDemo`, and
`runDisposableTamperDemo`.

Do not let click handlers mutate unrelated DOM elements directly. They update
state, then call render functions.

## 9. API client design

Create `apps/dashboard/static/js/api.js` with one shared request function.

### 9.1 Request behavior

- Use relative same-origin URLs.
- Use `Accept: application/json`.
- Add `Content-Type: application/json` only when a body exists.
- Use `AbortController` with an 8-second timeout.
- Parse the existing safe error envelope.
- Throw a small `ApiError` containing status, code, and safe message.
- Never place a secret in a query string.
- Never automatically retry mutation requests.
- A read request may be retried manually through **Refresh**.

### 9.2 Required client functions

```text
getHealth()
listOrders()
startRun(orderId, mode, scenario)
getRun(traceId)
getEvents(traceId)
getDecisions(traceId)
getProjection(traceId)
verifyTrace(traceId)
getApproval(approvalId)
decideApproval(approvalId, request, secret)
resetDemo()
tamperDisposableTrace(traceId, sequence, replacementSummary, secret)
```

### 9.3 Trace loading

`loadTrace(traceId)` performs the independent reads concurrently. Approval is
loaded after the run response reveals a pending approval ID.

One failed panel request should not silently erase the other successful data.
The first implementation may use `Promise.allSettled` and show a panel-level
error. The integrity panel is always attempted.

## 10. Rendering design

### 10.1 Health and environment banner

Show labels directly from health:

```text
Runtime       deterministic
Policy        python_reference / demo-v1
Storage       memory_hash_chain
Approval      local
Integrity     sha256 / ledger-event-v1
Tamper demo   disabled or enabled
```

If health fails, disable all mutation controls but leave a retry button.

### 10.2 Run summary

Show:

- trace ID with copy button;
- order ID;
- mode and scenario;
- run status and workflow stage;
- selected vehicle/carrier;
- current committed/reserved/projected spend;
- event and decision counts; and
- last refresh time.

Trace IDs and hashes use a monospace style but remain selectable.

### 10.3 Spend visualization

Render a small dependency-free SVG or CSS stacked-bar chart from `spend_points`:

- committed portion;
- reserved portion;
- ceiling line;
- over-ceiling region; and
- labelled points for start, prepared, and terminal/current state.

Always include an accessible table of exact INR values beneath the visual.

### 10.4 Risk-signal visualization

Render the 0-100 demo score and one marker for each first-seen non-allow family.
The method explanation is available through a disclosure element.

Do not hide repeated decisions; they remain in the decision feed even though a
repeated family does not increase the aggregate score.

### 10.5 Trace timeline

Group events into four agent lanes plus system/control events. Each row shows:

- sequence;
- time;
- agent or system;
- event type;
- summary;
- tool/effect class when present; and
- an expandable safe detail block.

Default timeline filtering may hide routine `ALLOW` details, but **Show all**
must reveal every ledger event in sequence.

### 10.6 Decision feed

Default to **Interventions only**:

```text
policy_outcome != allow
```

Each card shows:

- `WOULD` prefix when `enforced == false` and policy outcome is not allow;
- policy and applied outcomes;
- reason code and `because`;
- agent/tool/effect;
- policy version and engine;
- evaluation milliseconds;
- signal families and IDs; and
- guidance when present.

### 10.7 Provenance panel

Show the fact at the top and attempts below it. The hero path must make the
50 kg attempted value visually different from the sourced 500 kg value and the
corrected 500 kg value.

Hashes are shortened in the main view and available in full through a details
element/copy action.

### 10.8 Approval panel

Display only synthetic safe fields. The secret input uses `type="password"`,
`autocomplete="off"`, and is never placed into application state or
`localStorage`.

While submitting:

- disable approve and reject buttons;
- show the chosen action;
- keep approval version fixed to the displayed record; and
- generate one idempotency key per deliberate click.

On conflict, refresh approval and run state before enabling another action.

### 10.9 Integrity panel

States:

```text
UNKNOWN     grey, verification not loaded
VALID       green + check icon/text
INVALID     red + warning icon/text and first bad sequence
ERROR       amber + retry action
```

Color is never the only signal.

## 11. URL, refresh, and freshness behavior

- On successful run, update the URL with
  `/dashboard/?trace_id=<encoded trace ID>` using `history.replaceState`.
- On page load with `trace_id`, load that trace after health succeeds.
- Never put secrets, approval IDs, comments, or hashes in the URL.
- Show **Fresh** for 0-10 seconds after load.
- Show **Stale** after 10 seconds until refresh.
- While a run is pending approval, poll read-only run status every 3 seconds so
  a decision made in another browser becomes visible.
- Stop polling at terminal states, on disconnect, or when the page is hidden.
- Polling never invokes a mutation endpoint.

## 12. Security and privacy rules

- All data remains synthetic.
- No secret is embedded in HTML or JavaScript.
- No secret is stored in `localStorage`, `sessionStorage`, cookies, URL, global
  state, console logs, or error messages.
- Clear password inputs in a `finally` block.
- Render all API text with `textContent`, never `innerHTML`.
- Build SVG elements with DOM APIs or strictly numeric coordinates.
- Do not render raw prompt/model content.
- Do not expose a generic tamper payload editor.
- Approval and tamper authorization remain server-side.
- Invalid ledger verification disables trace mutations in the UI but does not
  replace backend enforcement.
- External fonts, scripts, analytics, images, and CDNs are excluded.

For dashboard responses, add a path-scoped Content Security Policy where
practical:

```text
default-src 'self';
script-src 'self';
style-src 'self';
img-src 'self' data:;
connect-src 'self';
object-src 'none';
base-uri 'none';
frame-ancestors 'none'
```

Do not apply a policy globally if it breaks FastAPI's existing `/docs` assets;
scope it to `/dashboard` static responses.

## 13. Accessibility requirements

- One logical `<h1>` and ordered heading hierarchy.
- Every input has a visible `<label>`.
- Buttons have clear action names.
- Status updates use an `aria-live="polite"` region.
- Errors use `role="alert"`.
- Dialog-like detail panels return focus to their trigger.
- Keyboard-only operation works for run, filters, approval, verification, and
  reset.
- Focus is visibly styled.
- Outcome badges include text, not color alone.
- Contrast targets WCAG AA for normal text.
- `prefers-reduced-motion` disables nonessential transitions.
- Charts include adjacent tables or lists containing the same facts.

## 14. Backend integration changes

### 14.1 New projection module

Add `packages/projections/dashboard.py` with pure helpers:

```text
build_dashboard_projection(state)
build_risk_points(state.decisions, state.events)
build_spend_points(state, state.events)
build_weight_provenance(state, state.events, state.decisions)
```

It reads defensive copies and never calls the policy engine, tools, approval
lifecycle, or ledger append methods.

### 14.2 Service method

Add:

```python
RunService.get_dashboard_projection(trace_id) -> DashboardProjection
```

It uses `store.get_state(trace_id)` so projection cannot mutate live state.

### 14.3 API endpoint

Add:

```http
GET /v1/traces/{trace_id}/projection
```

Behavior:

- `200` for known traces, including pending and cancelled traces;
- `404 TRACE_NOT_FOUND` for an unknown trace;
- no event append;
- no verification side effect; and
- no secret, approval comment, or raw PII.

### 14.4 Static dashboard mount

Mount static files using an absolute path derived from `__file__`, never the
current working directory.

Conceptual setup:

```python
dashboard_dir = Path(__file__).resolve().parents[1] / "dashboard" / "static"
app.mount("/dashboard", StaticFiles(directory=dashboard_dir, html=True), name="dashboard")
```

Add `GET /` as an optional redirect to `/dashboard/`. Do not shadow `/docs`,
`/openapi.json`, health, or `/v1` routes.

### 14.5 Version and health

Advance the prototype version to `0.7.0` and add:

```json
{
  "dashboard_mode": "static_no_build",
  "dashboard_ready": true,
  "projection_version": "dashboard-v1"
}
```

Health must report `dashboard_ready: false` or fail readiness if required static
assets are missing at startup.

## 15. Planned file structure

```text
apps/
  api/
    main.py                         # projection route and dashboard mount
    schemas.py                      # projection and health schemas
  dashboard/
    __init__.py
    static/
      index.html
      styles.css
      js/
        api.js                      # HTTP wrapper and endpoint functions
        state.js                    # one explicit dashboard state
        format.js                   # money/time/hash/text formatters
        charts.js                   # dependency-free SVG renderers
        render.js                   # panel render functions
        app.js                      # actions, events, initialization, polling
packages/
  projections/
    __init__.py
    dashboard.py                    # pure dashboard read model
tests/
  unit/
    test_dashboard_projection.py
  e2e/
    test_checkpoint_5_dashboard_api.py
    test_checkpoint_5_static_assets.py
scripts/
  run_checkpoint_5.sh
docs/
  CHECKPOINT_5_IMPLEMENTATION_PLAN.md
```

No generated `dist/`, `node_modules/`, source map, or bundled vendor asset is
created in this checkpoint.

## 16. File-by-file implementation map

### New backend files

`packages/projections/dashboard.py`

- risk-signal scoring;
- spend points;
- provenance joins by proposal ID;
- projection validation and deterministic ordering.

`packages/projections/__init__.py`

- export the projection builder only.

### New dashboard files

`apps/dashboard/static/index.html`

- semantic page skeleton;
- forms and panel containers;
- `<template>` elements for repeated rows/cards;
- module entrypoint only, no inline script or embedded secret.

`apps/dashboard/static/styles.css`

- responsive card/grid system;
- status/outcome styles;
- accessible focus and reduced-motion styles;
- print-safe fallback for demo screenshots.

`apps/dashboard/static/js/api.js`

- request wrapper;
- timeout and safe error parsing;
- endpoint functions.

`apps/dashboard/static/js/state.js`

- state object;
- state transition helpers;
- subscriptions or one render callback.

`apps/dashboard/static/js/format.js`

- format integer minor units;
- format timestamps;
- shorten hashes without changing copied values;
- escape is unnecessary when all rendering uses `textContent`.

`apps/dashboard/static/js/charts.js`

- SVG spend and risk rendering;
- numeric-only coordinates;
- empty-data states;
- accessible text alternatives.

`apps/dashboard/static/js/render.js`

- health, controls, summary, trace, decisions, provenance, approval, integrity,
  and error renderers.

`apps/dashboard/static/js/app.js`

- startup;
- DOM event listeners;
- load/run/reset/refresh actions;
- approval and disposable tamper actions;
- URL state and polling lifecycle.

### Files to modify

`packages/domain/models.py`

- add projection dataclasses.

`packages/domain/errors.py`

- add `DashboardProjectionError` only if corrupted internal relationships need
  a controlled API error.

`apps/runtime/service.py`

- expose read-only projection.

`apps/api/schemas.py`

- add projection response models;
- add health fields.

`apps/api/main.py`

- add projection endpoint;
- mount dashboard static files after API routes;
- optionally redirect `/`;
- update version/description.

`pyproject.toml`

- advance version;
- include dashboard static assets in package data.

`README.md`

- add dashboard start/use/demo instructions;
- update architecture and current status.

`scripts/README.md`

- describe the Checkpoint 5 script.

## 17. Detailed implementation order and gates

### Phase 0 — Protect the Checkpoint 4 baseline

Actions:

1. Run `python3 -m pytest -q`.
2. Run `./scripts/run_checkpoint_4.sh`.
3. Record the 85-test baseline.
4. Confirm Node remains unavailable and document the zero-build decision.
5. Do not edit policy, fixture, commitment, approval, or ledger semantics.

Gate:

```text
85 tests pass
Checkpoint 4 script passes
frontend strategy is frozen for this checkpoint
```

### Phase 1 — Add projection contracts only

Actions:

1. Add projection dataclasses.
2. Define the exact risk-signal method string.
3. Define spend and provenance field meanings.
4. Add response schemas.
5. Keep runtime output unchanged.

Gate:

```text
all old tests pass
projection models serialize through to_primitive
money remains integer minor units
```

### Phase 2 — Build and test the pure projection

Actions:

1. Implement provenance joins by proposal ID.
2. Implement unique-family risk-signal points.
3. Implement spend points from scenario/prepared/current state.
4. Test benign, shadow, pending, approved, rejected, and expired traces.
5. Test deterministic ordering.

Gate:

```text
primary enforce fixture risk score == 60
provenance displays 500 -> 50 -> 500
pending spend displays 3650 committed + 900 reserved
approved spend displays 4550 committed + 0 reserved
rejected spend displays 3650 committed + 0 reserved
projection does not add a ledger event
```

### Phase 3 — Expose projection and static shell

Actions:

1. Add the service method and projection endpoint.
2. Create the dashboard package and minimal semantic HTML.
3. Mount the static directory.
4. Add health metadata and version `0.7.0`.
5. Test `/dashboard/`, CSS, JavaScript modules, and projection API.

Gate:

```text
dashboard opens without Node/npm
all assets are served locally
health and fixture data appear in the page
API/CLI regressions remain green
```

### Phase 4 — Build run controls and trace loading

Actions:

1. Add the API wrapper and explicit state object.
2. Populate order/mode/scenario controls from APIs.
3. Implement run, reset, refresh, URL trace restoration, and errors.
4. Disable duplicate mutations while requests are active.
5. Render summary cards from real responses.

Gate:

```text
benign, shadow, and enforce runs start from browser
URL contains only trace_id
refresh restores the trace while backend remains alive
failed API request produces a visible recoverable error
```

### Phase 5 — Render trace, decisions, and provenance

Actions:

1. Render ordered event timeline.
2. Render intervention-first decision feed.
3. Add filters and expandable detail.
4. Render 500 -> 50 -> 500 provenance.
5. Validate that all text uses safe DOM methods.

Gate:

```text
all four agents are visible
shadow policy/applied outcomes are distinguishable
guide-back evidence is clear without reading raw JSON
event order matches API sequence exactly
```

### Phase 6 — Render spend and risk signals

Actions:

1. Render dependency-free SVG/CSS visuals.
2. Add exact-value tables.
3. Add ceiling/overflow treatment.
4. Explain the demo risk method.
5. Test empty and partial projection data.

Gate:

```text
INR 4550 vs INR 4000 is immediately visible
risk score 60 is labelled as a demo signal score
charts and tables agree
no chart library or CDN is used
```

### Phase 7 — Approval from the dashboard

Actions:

1. Load the pending approval.
2. Render exact binding fields.
3. Add approve/reject form.
4. Generate idempotency key per action.
5. Clear secret after success or failure.
6. Refresh the same trace.
7. Handle stale/conflict/expired responses.

Gate:

```text
approve completes the same trace exactly once
reject cancels and releases reservation exactly once
secret never appears in DOM text, URL, console, API event output, or storage
double click produces one deliberate mutation request
```

### Phase 8 — Integrity and disposable tamper demo

Actions:

1. Render valid/invalid/error verification states.
2. Add manual verify refresh.
3. Show tamper demo only when enabled by health.
4. Create and label a separate disposable trace.
5. Require manually entered tamper secret.
6. Reverify and show first bad sequence.

Gate:

```text
primary trace cannot be selected for tampering
clean disposable trace verifies
altered disposable trace reports expected sequence
tamper secret is cleared and never persisted
```

### Phase 9 — Responsive, accessible, and failure-state pass

Actions:

1. Test 360, 768, and 1440 px widths.
2. Test keyboard-only navigation.
3. Test loading, stale, disconnected, 404, 409, 410, 422, and 500 UI states.
4. Add focus management and live regions.
5. Confirm no horizontal scroll and no unreadable chart-only facts.

Gate:

```text
primary journey works at all three widths
all controls are keyboard reachable
errors are visible and recoverable
color is never the only status indicator
```

### Phase 10 — Documentation and release

Actions:

1. Add `run_checkpoint_5.sh`.
2. Update README and screenshots if desired.
3. Run every earlier checkpoint script.
4. Complete two browser rehearsals from reset.
5. Complete one offline/local rehearsal.

Gate:

```text
all automated tests pass twice
all checkpoint scripts pass
four-minute primary demo works without terminal interaction after server start
known limitations are documented
```

## 18. Testing plan

### 18.1 Projection unit tests

- Benign enforce has no non-allow risk families.
- Primary adversarial enforce score is 60.
- Repeated cold-chain decisions do not add duplicate family points.
- Shadow uses policy outcomes even though applied outcomes are allow.
- Risk points are ordered by event sequence.
- Spend start uses prior committed amount.
- Prepare adds reserved amount once.
- Approve moves reserved to committed.
- Reject/expiry releases reserved amount.
- Projection contains no negative minor-unit value.
- Weight attempts join decisions by proposal ID.
- Missing optional provenance returns null rather than crashing.
- Projection does not change event count or ledger head.

### 18.2 API tests

- Known trace projection returns `200` and documented schema.
- Unknown trace returns `404`.
- Projection values match run summary.
- Health reports dashboard readiness and projection version.
- Existing response contracts remain compatible.
- Static mount does not shadow `/v1`, `/docs`, or `/health/ready`.

### 18.3 Static-asset tests

- `/dashboard/` returns `200` and HTML content type.
- CSS and every JavaScript module return `200` with appropriate content types.
- HTML references only local assets.
- No `http://`, `https://`, CDN script, or embedded secret appears in assets.
- Entry script uses `type="module"`.
- Forms contain visible labels.
- Required panel IDs are unique.
- Packaged installation includes static files.

### 18.4 Browser functional tests

Because Node and a browser test runner are absent, the first checkpoint uses a
documented manual browser matrix in addition to Python API/static tests:

- initial health and fixture load;
- benign enforce run;
- adversarial shadow run;
- adversarial enforce pending state;
- approve path;
- reject path;
- verify refresh;
- disposable tamper path;
- backend unavailable/restarted state;
- stale approval conflict;
- page reload with trace ID;
- keyboard-only operation;
- 360/768/1440 px layouts.

If a browser automation capability is available during implementation, automate
the primary run/approve/verify flow, but do not add Node solely for this phase.

### 18.5 Security tests

- Approval secret never appears in requests other than the header.
- Tamper secret never appears in requests other than the header.
- Secrets are absent from events, decisions, errors, URL, and static assets.
- API strings containing HTML-like text render as text.
- Invalid verification disables mutation controls.
- Tamper panel stays hidden when health says disabled.

### 18.6 Regression gate

Run:

```bash
python3 -m pytest -q
./scripts/run_checkpoint_1.sh
./scripts/run_checkpoint_2.sh
./scripts/run_checkpoint_3.sh
./scripts/run_checkpoint_4.sh
./scripts/run_checkpoint_5.sh
```

Earlier scripts may not be weakened to make the dashboard pass.

## 19. Minimum manual smoke test

Start the API/dashboard server:

```bash
cd /home/yashraj/p0/project
export DEMO_APPROVER_SECRET='local-demo-only-change-me'
python3 -m uvicorn apps.api.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/dashboard/
```

Perform:

1. Confirm the environment banner reports ready.
2. Run adversarial shadow and inspect counterfactual decisions.
3. Reset.
4. Run adversarial enforce.
5. Confirm provenance shows 500 -> 50 -> 500.
6. Confirm spend shows INR 4,550 against INR 4,000.
7. Enter the configured approval secret and approve.
8. Confirm the same trace becomes completed.
9. Confirm the ledger remains valid with a later head.
10. Reload the page and confirm the trace restores from the URL.

Optional tamper smoke:

```bash
export ENABLE_DEMO_TAMPER=true
export DEMO_TAMPER_SECRET='local-tamper-only-change-me'
```

Restart the server, create a disposable trace from the integrity panel, tamper
it, and confirm the reported first bad sequence. Then reset the demo.

## 20. Acceptance criteria

- [ ] The original 85 tests pass unchanged.
- [ ] Dashboard loads from FastAPI without Node, npm, CDN, or network access.
- [ ] Health and fixtures come from real APIs.
- [ ] Benign, shadow, and enforce runs start from the browser.
- [ ] Trace timeline uses real ordered ledger events.
- [ ] All four agents are visible.
- [ ] Shadow policy and applied outcomes are distinguishable.
- [ ] Weight provenance shows 500 -> 50 -> 500.
- [ ] Uncertified-to-certified carrier guide-back is visible.
- [ ] Pending spend shows INR 4,550 against INR 4,000.
- [ ] Demo risk score is reproducibly 60 for the primary enforce fixture and is
      clearly labelled as a synthetic indicator.
- [ ] Approve and reject work without terminal interaction.
- [ ] Approval mutation confirms/cancels exactly once.
- [ ] Approval secret is never persisted or rendered.
- [ ] Clean trace verification shows valid.
- [ ] Invalid disposable trace shows the first bad sequence.
- [ ] Primary trace cannot be tampered through the UI.
- [ ] Loading, empty, stale, disconnected, and error states are visible.
- [ ] Page is usable at 360, 768, and 1440 px.
- [ ] Keyboard navigation and text alternatives work.
- [ ] Existing CLI and API behavior remains compatible.
- [ ] Complete browser demo succeeds twice from reset.
- [ ] `run_checkpoint_5.sh` passes twice.

## 21. Beginner-oriented work sessions

### Session 1 — Static page and API health (60-90 minutes)

- Learn the roles of HTML, CSS, and JavaScript.
- Serve one page through FastAPI.
- Fetch and display `/health/ready`.
- Stop once loading/error/ready states work.

### Session 2 — Explicit state and run form (90-120 minutes)

- Build the state object.
- Load fixtures.
- Submit `POST /v1/runs`.
- Display only the run summary first.

### Session 3 — Trace and decisions (90-120 minutes)

- Fetch events and decisions.
- Render ordered rows using `<template>` and `textContent`.
- Add intervention filtering.

### Session 4 — Backend projection (90-120 minutes)

- Implement one projection function at a time.
- Start with provenance, then spend, then risk signals.
- Write tests before drawing charts.

### Session 5 — Provenance and charts (90-120 minutes)

- Render exact tables first.
- Add SVG/CSS visuals only after values are correct.
- Check 500 -> 50 -> 500 and INR 4,550 / INR 4,000.

### Session 6 — Approval (90-120 minutes)

- Render pending approval fields.
- Submit one decision.
- Clear the secret and refresh the same trace.
- Test approve before reject.

### Session 7 — Integrity and optional tamper demo (60-90 minutes)

- Render `/verify` result.
- Build a separate disposable-trace flow.
- Never reuse the hero trace.

### Session 8 — Accessibility, failures, and rehearsal (90-120 minutes)

- Test keyboard and three viewport widths.
- Stop/restart backend to exercise disconnected behavior.
- Rehearse the complete flow twice.

Estimated beginner time: 12-16 focused hours. Do not work on visual polish while
an API, projection, approval, or integrity gate is red.

## 22. Common mistakes to avoid

- Hard-coding the expected trace into HTML.
- Adding React before the plain API-backed page works.
- Using a CDN that breaks the offline demo.
- Computing authorization outcomes in JavaScript.
- Calling the demo signal score a probability or learned risk model.
- Doing financial arithmetic with floating-point rupees.
- Joining events and decisions by array position instead of `proposal_id`.
- Rendering API content through `innerHTML`.
- Saving demo secrets in local storage for convenience.
- Sending secrets in URLs.
- Allowing approve/reject double clicks.
- Treating a disabled button as backend security.
- Hiding an invalid ledger because other panels loaded successfully.
- Tampering with the primary demo trace.
- Polling mutation endpoints.
- Starting AWS deployment before the local browser journey is reliable.
- Spending time on animation before loading/error/mobile states work.

## 23. Suggested commit checkpoints

```text
test: pin checkpoint 4 dashboard baseline
feat: add dashboard projection contracts
feat: derive provenance spend and risk signal projections
feat: expose dashboard projection endpoint
feat: serve zero-build dashboard shell
feat: add run controls and trace loading
feat: render trace decisions and provenance
feat: render spend and risk signal visuals
feat: resolve approvals from dashboard
feat: add integrity and disposable tamper panels
test: cover dashboard APIs and static assets
docs: document checkpoint 5 browser demo
```

Do not combine policy, fixture, ledger-schema, or agent behavior changes with
dashboard commits.

## 24. Risks and controls

| Risk | Early warning | Control | Fallback |
|---|---|---|---|
| Frontend scope expands | Multiple pages or design-system work starts | One page and fixed panel list | Cut visual polish, keep tables |
| JavaScript becomes hard to follow | Cross-module circular imports | One-way `api -> actions -> state -> render` flow | Merge tiny modules, preserve named actions |
| Projection disagrees with runtime | Chart values differ from summary | Pure projection tests and exact tables | Hide chart, keep verified values |
| Approval secret leaks | Secret visible after request or reload | Password input only, clear in `finally` | Disable browser approval until fixed |
| Dashboard masks errors | Blank panel on failed fetch | Panel-level error state and retry | Show raw safe error code/message |
| Trace is stale | External approval not shown | Timestamp, pending-only polling, refresh | Manual refresh button |
| Static mount shadows API | `/v1` returns HTML | Mount after routes and route tests | Serve dashboard under separate sub-app |
| Browser differences | SVG/layout differs | Native APIs only, responsive smoke matrix | Tables remain authoritative |
| Tamper harms hero trace | Wrong trace ID used | Dashboard-created disposable ID only | Omit tamper button; use existing API demo |
| Risk score overclaimed | UI says predictive/production risk | Method label and limitation copy | Show family count only |

## 25. Exit and handoff to Checkpoint 6

Checkpoint 5 hands the next checkpoint:

- a complete local browser-operated demonstration;
- stable framework-neutral projection contracts;
- real trace, decision, provenance, approval, spend, risk-signal, and integrity
  panels;
- a no-terminal primary journey after server start;
- static assets that work offline; and
- regression coverage across Checkpoints 1-5.

Checkpoint 6 can introduce a durable DynamoDB adapter and AWS API deployment
behind the same service contracts. React/TypeScript may also replace the
zero-build view later, but it must preserve the projection/API behavior and
must not become a prerequisite for the stable local demo.
