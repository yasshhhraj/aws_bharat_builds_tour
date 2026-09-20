# Checkpoint 9 Implementation Plan — Offline Strands Runtime

**Plan version:** 1.1

**Created:** 20 September 2026

**Last reviewed against repository and Strands documentation:** 20 September 2026

**Checkpoint state:** Complete — gate passed twice consecutively

**Depends on:** Completed Checkpoints 1–8

**Network requirement:** Dependency installation only

**AWS requirement:** None

**Next checkpoint:** Checkpoint 10 — Local/Free Provider Portability

## 1. Objective

Run Inventory, Dispatch, Carrier, and Customer Communications through the real Strands agent loop using a deterministic recorded model. Keep the existing orchestrator bounded, keep Cedar authoritative, and preserve every storage, approval, exact-once, and ledger guarantee from Checkpoint 8.

This checkpoint proves the agent framework integration independently of hosted model access. Ollama, OpenRouter, Bedrock, IAM, and AWS deployment are intentionally excluded.

## 2. Starting gate

Before changing runtime code:

```bash
cd /home/yashraj/p0/project
./scripts/run_checkpoint_8.sh
```

Record the exact commit and working-tree state used for the run. The current Checkpoint 8 baseline is represented partly by uncommitted work, so do not discard or overwrite unrelated changes.

Expected baseline evidence currently recorded by the project:

```text
Python tests with live Cedar: 164 passed, 9 skipped
Storage gate:                 11 passed
Rust/Cedar tests:              2 passed
Evaluation:                   22/22 passed
DynamoDB restart recovery:     passed
```

If the baseline gate fails, repair or explain that regression before installing Strands.

## 3. Target architecture

```text
CLI / FastAPI
      |
      v
RunService
      |
      v
ShipmentOrchestrator     (retains four-stage ordering and pause/resume)
      |
      v
AgentRuntime protocol
   |                         |
   v                         v
legacy deterministic     StrandsAgentRuntime
                              |
                              v
                    RecordedManifestModel
                              |
                              v
                   narrow governed tool wrappers
                              |
                              v
                    ManifestGovernor.execute_tool
                              |
                 +------------+-------------+
                 |                          |
                 v                          v
               Cedar                  tool registry/state
```

The Strands layer decides which declared action to request and consumes its result. It does not own policy, approvals, commitments, persistence, idempotency, or ledger integrity.

## 4. Required contracts

### 4.1 Runtime selection

Use explicit settings with safe defaults:

```text
MANIFEST_AGENT_RUNTIME=legacy|strands
MANIFEST_MODEL_PROVIDER=recorded
MANIFEST_MODEL_ID=manifest-recorded-v1
MANIFEST_AGENT_MAX_TURNS=<small bounded integer>
MANIFEST_AGENT_TIMEOUT_SECONDS=<bounded timeout>
```

`legacy` remains available only for parity checks during this checkpoint. The Checkpoint 9 gate explicitly selects `strands` and `recorded`.

### 4.2 Agent runtime protocol

Define a project-owned protocol rather than exposing Strands objects throughout the application. It must support:

- running one named role against a `TrajectoryState`;
- supplying only that role's allowed tools;
- returning a stable project-owned result/summary;
- resuming the prepared Carrier action after approval;
- reporting runtime, provider, model, turn count, and terminal status.

The existing `ShipmentOrchestrator` remains responsible for role order and terminal state transitions.

### 4.3 Role tool allow-lists

Start from the current deterministic agents and preserve their minimum capabilities. The implementation must derive the exact list from the existing tool registry rather than inventing broad tools.

Rules:

- Inventory receives inventory and order-reading operations only.
- Dispatch receives route/dispatch operations only.
- Carrier receives quote, prepare, confirm, and cancel operations required by the current workflow.
- Customer Communications receives notification operations only.
- No role receives a generic shell, HTTP, cloud SDK, database, filesystem, Python, or arbitrary tool-execution capability.

### 4.4 Governed wrapper

Each Strands tool wrapper must:

1. validate typed input;
2. bind the fixed role identity itself;
3. obtain the active trace/state from a scoped invocation context;
4. call `ManifestGovernor.execute_tool` exactly once;
5. return a small structured result;
6. allow policy denials and approval requirements to remain typed project outcomes;
7. never mutate protected state directly.

Never trust role name, trace ID, policy mode, approval state, or authority claims supplied by model-generated arguments.

### 4.5 Recorded model

`RecordedManifestModel` must implement the Strands model interface and emit deterministic tool-use responses based on:

- the fixed role;
- the current workflow stage;
- the selected synthetic scenario;
- the last governed tool result; and
- a versioned response fixture.

It must not bypass the Strands loop by calling project tools itself. It must also reject unexpected prompts/stages instead of guessing.

The recorded provider is test infrastructure and an offline demo mode, not a live foundation model. UI and evidence must label it accurately.

### 4.6 Bounded execution

- one fresh Strands conversation per role invocation;
- no cross-trace memory;
- small maximum-turn count;
- no recursive sub-agents;
- no parallel effectful tool calls;
- one expected operational action at a time;
- unknown or repeated action requests fail closed;
- approval pause ends the current invocation; resume starts a new bounded invocation with verified approval context.

### 4.7 Pinned SDK posture

Use `strands-agents==1.56.0` for this checkpoint. PyPI identifies 1.56.0 as the current release on 20 September 2026 and lists Python 3.14 support, matching the current local runtime.

Do not install `strands-agents-tools`. Manifest supplies only its own narrow, governed tools; it must not inherit shell, filesystem, browser, HTTP, or other community tools.

The recorded provider must implement the current Strands `Model` contract:

- subclass `strands.models.Model`;
- implement async `stream(messages, tool_specs, system_prompt, **kwargs)`;
- implement `get_config()` and `update_config()`;
- implement the required `structured_output()` method and fail clearly because the recorded fixture does not support that optional execution path;
- emit valid Strands streaming events for tool requests, tool results, metadata, and final text.

Construct each role invocation with:

- a fresh `Agent` instance;
- a `SequentialToolExecutor` because workflow tools are order-dependent;
- no session manager or memory manager;
- no automatic tool-directory loading;
- no default model selection;
- no retry strategy for the deterministic recorded provider;
- a null/capturing callback rather than console streaming; and
- explicit invocation limits, with a maximum of eight turns for the longest Carrier path.

### 4.8 State transition ownership

The current deterministic agents both request tools and project successful results into `TrajectoryState`. Extract those projections into one shared deterministic `ToolResultProjector` before adding Strands.

The projector may update workflow facts such as `order`, `inventory_fact`, `selected_vehicle`, `dispatch_plan_id`, `selected_quote`, `prepared_actions`, and `notification_id` only after a successful governed result. Financial commitment, approval, idempotency, effect receipts, policy decisions, and ledger changes remain owned by `ManifestGovernor` and storage services.

Both the legacy agents and Strands tool bridge must call the same projector. This prevents two subtly different workflow implementations and makes parity meaningful.

## 5. Execution batches

Complete these batches in order. Do not start the next batch until the current batch's gate is green.

### CP9.0 — Freeze and prove the baseline

**Estimated effort:** 30–60 minutes

1. Record `git status --short` and the current commit SHA.
2. Run `./scripts/run_checkpoint_8.sh` without modifying its output to hide failures.
3. Save the exact test/evaluation counts and release-manifest digest.
4. Preserve every unrelated modified or untracked file.

**Gate:** Checkpoint 8 passes, and all pre-existing working-tree changes are identified. Do not commit or tag without repository-owner authorization.

### CP9.1 — Pin Strands and prove the SDK seam

**Estimated effort:** 1–2 hours

1. Add only `strands-agents==1.56.0` to project dependencies.
2. Install it into `.venv` and record the resolved dependency snapshot.
3. Add an isolated test-only recorded model implementing the current `Model` interface.
4. Give a temporary Strands agent one harmless local test tool.
5. Invoke the agent with `SequentialToolExecutor`, explicit turn limits, and no provider credentials.
6. Assert the model emits a tool request, Strands executes it, and the model consumes its result before ending the turn.

**Gate:** the spike works with network disabled after installation, uses no AWS environment, and confirms the exact streaming event shape needed by `RecordedManifestModel`.

### CP9.2 — Add settings and the runtime boundary

**Estimated effort:** 2 hours

1. Add validated settings for runtime, provider, model ID, maximum turns, and timeout.
2. Define project-owned `AgentRunRequest`, `AgentRunResult`, and `RoleRuntime` contracts.
3. Implement a runtime factory with exactly two permitted CP9 combinations:
   - `legacy` with the current deterministic agents;
   - `strands` with `recorded` and `manifest-recorded-v1`.
4. Reject unknown values and reject `strands` without an explicit provider/model.
5. Keep `legacy` as the default until the final CP9 gate explicitly enables Strands.
6. Add runtime/provider/model fields to service diagnostics without changing policy or storage construction.

**Gate:** factory/configuration unit tests pass, invalid combinations fail at startup, and all legacy tests remain green.

### CP9.3 — Extract shared workflow projections

**Estimated effort:** 2–3 hours

1. Extract successful tool-result state transitions from the four existing deterministic agents into `ToolResultProjector`.
2. Keep agent choice/retry logic where it is; extract only deterministic projection logic.
3. Make legacy agents call the projector.
4. Add before/after snapshot tests for every registered tool.
5. Prove denied, guided, malformed, or failed results do not project successful state.

**Gate:** all legacy journey outputs, policy decisions, commitment totals, approvals, and ledger hashes remain functionally identical to the pre-extraction baseline.

### CP9.4 — Build four governed Strands tool sets

**Estimated effort:** 3–4 hours

1. Create a fresh invocation context containing fixed role, active state, governor, and projector.
2. Implement four class-based Strands tool sets so each role exposes only its registered tools.
3. Bind role, trace, policy mode, and state outside model-controlled arguments.
4. Call `ManifestGovernor.execute_tool` exactly once per accepted request.
5. Project successful results through `ToolResultProjector` and serialize only safe primitives back to Strands.
6. Return explicit structured outcomes for allow, guide, block, and approval-required results.
7. Refuse every additional tool request after an approval pause or terminal failure.

**Gate:** schema snapshots and tool-boundary tests prove correct allow-lists, strict arguments, one governor call, no direct handler call, and no mutation on rejection.

### CP9.5 — Implement the recorded model

**Estimated effort:** 3 hours

1. Implement `RecordedManifestModel` as a finite-state model over role, phase, previous tool results, and versioned scenario fixtures.
2. Support normal `run`, Carrier `resume_approved`, and Carrier `cancel` phases.
3. Request one operational tool at a time even though the executor is sequential.
4. Consume guide-back data and issue the one permitted corrected request.
5. End immediately on block, approval-required, invalid tool result, or completed role outcome.
6. Reject unexpected stage, missing tool, repeated terminal action, and fixture mismatch.
7. Emit deterministic metadata and a concise final summary without chain-of-thought content.

**Gate:** model-contract tests cover every role/phase, malformed streams, unknown tools, repeated calls, turn exhaustion, and deterministic replay.

### CP9.6 — Integrate all roles without replacing the orchestrator

**Estimated effort:** 4–5 hours

1. Add `StrandsRoleAgent` adapters implementing the existing `BaseAgent` seam.
2. Add a Carrier adapter for normal, resume-approved, rejected, and expired phases.
3. Construct a fresh Strands `Agent` per role invocation to prevent cross-role or cross-trace history leakage.
4. Keep `ShipmentOrchestrator` responsible for role order, pause/resume, terminal statuses, and top-level events.
5. Replace hard-coded `runtime_mode: deterministic` event/health values with the selected runtime descriptor.
6. Run memory-backed journeys first, followed by Cedar and DynamoDB Local journeys.

**Gate:** benign, shadow, enforce, guide-back, approval/approve, approval/reject, approval/expire, duplicate confirmation, restart, and tamper journeys pass through `strands + recorded`.

### CP9.7 — Prove parity and freeze evidence

**Estimated effort:** 2–3 hours

1. Add a parity comparator for protected outcomes between `legacy` and `strands + recorded`.
2. Compare policy outcomes, reason codes, selected resources, commitments, approvals, effects, final status, and ledger validity; exclude wording, UUIDs, timings, and hashes that legitimately depend on IDs.
3. Add `scripts/run_checkpoint_9_offline.sh` combining the full regression, Cedar/Rust, storage, evaluation, parity, and offline Strands gates.
4. Generate Checkpoint 9 JSON/Markdown evidence and a release manifest.
5. Run the gate twice from reset local state.
6. Write the completion report and update the progress submission report.

**Gate:** two consecutive full passes, no AWS/hosted-provider environment requirement, no secret scan finding, and an evidence bundle tied to the exact source revision.

### Estimated total

Approximately **18–22 focused hours**, depending mainly on the Strands streaming fixture and Carrier approval/resume integration. Stop after every batch and preserve its green tests; this keeps debugging bounded during the hackathon.

## 6. Recommended file changes

Names may change during implementation, but responsibilities should remain separated:

```text
apps/runtime/
  agent_runtime.py          # project-owned request/result/runtime protocols
  runtime_factory.py        # explicit runtime/provider construction
  runtime_settings.py       # validated runtime limits/configuration
  strands_runtime.py        # bounded Strands role execution
  strands_agents.py         # BaseAgent-compatible role adapters
  recorded_model.py         # deterministic Strands model implementation
  strands_tools.py          # four typed governor-backed tool sets
  tool_result_projector.py  # shared legacy/Strands state projection

tests/agents/
  test_recorded_model.py
  test_strands_tools.py
  test_strands_runtime.py
  test_runtime_factory.py
  test_tool_result_projector.py

tests/integration/
  test_strands_orchestrator.py
  test_strands_approval_resume.py

scripts/
  run_checkpoint_9_offline.sh

docs/results/
  checkpoint_9_offline_*.json

docs/releases/
  checkpoint-9-offline-strands.json
```

Prefer extending existing domain enums and evidence models only where required. Avoid a parallel set of agent-specific business models.

## 7. Test matrix

| Layer | Required proof |
|---|---|
| Model contract | deterministic tool request, final response, malformed stage, maximum turns |
| Tool boundary | typed input, role binding, unknown tool, wrong-role tool, exactly one governor call |
| Governance | benign permit, shadow observation, enforce deny, guide-back, approval required |
| State | no mutation on denied/malformed/repeated calls; exact-once confirmation |
| Resume | verified approval resumes Carrier; stale/wrong approval fails |
| Isolation | no messages or state leak between roles or traces |
| Ledger | event chain verifies; tamper is detected |
| Parity | legacy and Strands modes reach equivalent protected outcomes |
| Offline | network-disabled hero path passes with no cloud credentials |
| Regression | every Checkpoint 8 gate remains green |

The model's human-readable wording does not need byte-for-byte parity. Policy decisions, effects, commitment totals, approval state, run status, and ledger validity do.

## 8. Failure behavior

| Failure | Required outcome |
|---|---|
| Recorded fixture has no valid next step | Fail closed with a typed runtime error |
| Model requests unknown or wrong-role tool | Reject; no effect or protected-state mutation |
| Model exceeds maximum turns | Stop run; record bounded-runtime failure |
| Tool input is malformed | Reject before governor execution |
| Cedar is unavailable in authoritative mode | Fail closed according to the existing Cedar contract |
| Approval is required | Persist pending state and stop the current role invocation |
| Duplicate confirmation is requested | Preserve existing exact-once behavior |
| Ledger verification fails | Surface tamper/failure state; do not hide it in model text |

There is no automatic switch to the legacy runtime after a Strands trajectory begins.

## 9. Manual tasks

There is no AWS, Bedrock, IAM, Ollama, or OpenRouter work in Checkpoint 9.

The only possible owner actions are:

1. approve downloading the pinned `strands-agents==1.56.0` package if the environment requests network permission;
2. ensure Docker is running for the inherited DynamoDB Local gate;
3. review the pre-existing dirty working tree before implementation; and
4. authorize a commit/tag only after the final gate, if desired.

Do not create any cloud account, API key, access key, model entitlement, or paid resource for this checkpoint.

## 10. Exit checklist

- [x] Checkpoint 8 gate passed before changes.
- [x] Strands dependency is pinned and its resolved version recorded.
- [x] Recorded model uses the real Strands model protocol.
- [x] All four roles run through the Strands loop.
- [x] Tool wrappers bind role and state outside model-controlled input.
- [x] Every protected operation calls the governor.
- [x] Cedar remains the authoritative decision point.
- [x] Approval pause/resume and exact-once confirmation pass.
- [x] Offline benign, shadow, enforce, guide-back, and tamper paths pass.
- [x] Legacy/Strands protected-outcome parity passes.
- [x] Runtime/provider/model disclosure appears in diagnostics and evidence.
- [x] No AWS or hosted-provider secret is required.
- [x] The Checkpoint 9 gate passes twice.
- [x] Completion report records exact versions and evidence hashes.

## 11. Stop conditions

Stop and repair the design before proceeding if:

- a tool can execute without `ManifestGovernor`;
- model input can select its own role or policy mode;
- a Strands failure triggers an undisclosed fallback;
- protected state diverges from the legacy baseline without an approved reason;
- a hosted-provider dependency becomes necessary for the offline gate; or
- Checkpoint 8 guarantees regress.

## 12. Handoff to Checkpoint 10

Checkpoint 10 may start only after the offline gate is green. It adds Ollama/OpenRouter through the same runtime and tool contracts; it must not redesign governance or duplicate the agent workflow.

## 13. Official references

- Strands Agents 1.56.0 on PyPI: <https://pypi.org/project/strands-agents/>
- Custom model provider contract: <https://strandsagents.com/docs/user-guide/concepts/model-providers/custom_model_provider/>
- Custom and class-based tools: <https://strandsagents.com/docs/user-guide/concepts/tools/custom-tools/>
- Tool security and loading: <https://strandsagents.com/docs/user-guide/concepts/tools/>
- Sequential tool execution: <https://strandsagents.com/docs/user-guide/concepts/tools/executors/>
- Agent-loop limits and stop reasons: <https://strandsagents.com/docs/user-guide/concepts/agents/agent-loop/>
