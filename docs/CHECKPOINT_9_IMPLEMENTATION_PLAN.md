# Deferred Bedrock Integration Plan — Now Checkpoint 12

> **Deferred on 20 September 2026:** AWS account verification is still pending, so this Bedrock-first plan is no longer the active Checkpoint 9 plan. Start with [`CHECKPOINT_9_OFFLINE_IMPLEMENTATION_PLAN.md`](CHECKPOINT_9_OFFLINE_IMPLEMENTATION_PLAN.md) and the revised [`FOLLOWUP_CHECKPOINTS_TO_COMPLETION.md`](FOLLOWUP_CHECKPOINTS_TO_COMPLETION.md). The Bedrock-specific material below is retained as planning input for Checkpoint 12; its old numbering should not be used as the current execution order.

**Plan version:** 1.0  
**Created:** 19 September 2026  
**Checkpoint state:** Deferred until Checkpoint 12 and AWS account verification  
**Depends on:** Completed Checkpoints 9–11 and verified AWS access  
**Manual setup:** [`manual/CHECKPOINT_9_AWS_BEDROCK_SETUP.md`](manual/CHECKPOINT_9_AWS_BEDROCK_SETUP.md)  
**Next checkpoint after completion:** Checkpoint 13 — AWS Demo Stack

## 1. Objective

Add Amazon Bedrock to the provider factory created in Checkpoints 9–10 and prove one Bedrock-backed hero journey, without moving authorization, commitment state, approval, or ledger integrity into the model.

At completion:

- Inventory, Dispatch, Carrier, and Customer Communications run through Strands;
- Amazon Bedrock supplies model inference when `strands_bedrock` mode is selected;
- an offline recorded model provider exercises the same Strands loop and governed tools;
- every operational tool remains registered, effect-classed, and routed through `ManifestGovernor`;
- Cedar remains authoritative for every protected action;
- DynamoDB-compatible persistence, exact-once approval, and the hash chain retain their Checkpoint 8 guarantees;
- model calls and agent loops have bounded turns, tokens, retries, and timeouts;
- active runtime/model/fallback modes are visible and truthfully reported; and
- Bedrock loss never causes a silent mid-trajectory fallback or an ungoverned effect.

Checkpoint 12 adds Bedrock parity to the already-integrated Strands runtime. It does not deploy the application to AWS; that is Checkpoint 13.

## 2. Verified starting state

Checkpoint 8 records the following completed baseline:

```text
Python tests with live Cedar: 164 passed, 9 skipped
Shared memory/DynamoDB gate:   11 passed
Rust/Cedar tests:              2 passed
Evaluation:                    22/22 passed
Attack detection:              10/10
Benign cases:                  12/12
DynamoDB restart recovery:     passed
Three Cedar+DynamoDB journeys: passed
```

Current platform facts:

| Component | State relevant to Checkpoint 12 |
|---|---|
| Python | 3.14.6; supported by current Strands package metadata |
| Strands | Not installed or integrated yet |
| Cedar | 4.12.0 loopback sidecar, authoritative in Cedar mode |
| Storage | Memory and DynamoDB-compatible adapters; DynamoDB Local gate is green |
| Bedrock | Account access and credentials not yet verified |
| AWS CLI | Previously reported absent; owner setup is required unless already installed later |
| Agent roles | Deterministic Python classes |
| Tool boundary | Existing `ManifestGovernor.execute_tool` path |

### Baseline integrity prerequisite

Checkpoint 8 is currently represented by modified and untracked working-tree files beyond commit `e8e8ab4`. Before the deferred Bedrock implementation begins:

1. review the Checkpoint 8 diff;
2. run `./scripts/run_checkpoint_8.sh` successfully;
3. record the exact source revision in the Checkpoint 8 release manifest; and
4. commit/tag the baseline if the repository owner authorizes it.

Suggested operator tag: `v0.8.0-dynamodb-local`.

Checkpoint 12 must not be developed on an unidentified mixture of earlier checkpoint changes.

## 3. Key architecture decisions

### 3.1 Strands is a library inside the existing runtime

Do not create an Amazon Bedrock Agent service. The Python Strands SDK runs inside the current CLI/FastAPI process and calls Amazon Bedrock Runtime through Boto3's normal AWS credential chain.

```text
CLI / FastAPI
      |
      v
ShipmentOrchestrator (keeps bounded four-stage ordering)
      |
      v
AgentRuntime protocol
   |                       |
   v                       v
Legacy deterministic    Strands runtime
                           |
                  +--------+---------+
                  |                  |
                  v                  v
            RecordedModel       BedrockModel
                                     |
                                     v
                          Amazon Bedrock Runtime

Every Strands tool wrapper
      |
      v
ManifestGovernor -> Cedar -> TraceRepository -> mock operational effect
```

The existing orchestrator keeps the high-level sequence. Strands decides which of a role's small allowlisted tools to call; it does not receive a general shell, file, network, or AWS tool.

### 3.2 The governed tool wrapper is the enforcement point

Each function exposed to Strands is a thin adapter around the existing governor. It must not call `MockLogisticsTools`, fixture loaders, repositories, or AWS APIs directly.

```text
model requests tool
  -> Strands validates the tool input schema
  -> Manifest wrapper resolves the trace and agent role
  -> ManifestGovernor builds trajectory-aware request
  -> Cedar authorizes or denies
  -> governor executes the registered mock only on ALLOW/shadow behavior
  -> decision/result/guidance is returned as a structured tool result
  -> Strands continues, replans, or stops
```

Strands hooks are useful for metrics and bypass detection, but they are not the sole authorization boundary. A hook cancellation must never replace the existing decision, approval, effect-receipt, and ledger transaction.

### 3.3 Do not add a second Cedar enforcement layer

Strands has authorization/intervention capabilities, but Manifest already owns trajectory construction, reason mapping, approval binding, and evidence persistence. Checkpoint 12 will not enable a second independent Cedar plugin that could double-authorize or disagree with Manifest.

One Cedar decision path remains authoritative:

```text
Strands tool -> ManifestGovernor -> existing Cedar adapter -> effect or guidance
```

### 3.4 Explicit runtime and model modes

Use two independent settings:

```text
MANIFEST_AGENT_RUNTIME=legacy_deterministic | strands
MANIFEST_MODEL_PROVIDER=recorded | bedrock
```

Valid combinations:

| Agent runtime | Model provider | Meaning |
|---|---|---|
| `legacy_deterministic` | ignored | Checkpoint 1–8 compatibility path |
| `strands` | `recorded` | Offline Strands loop with deterministic recorded model events |
| `strands` | `bedrock` | Live Strands + Amazon Bedrock path |

Invalid values fail startup. The application must never silently change modes after startup.

### 3.5 No mid-run model fallback

Automatic fallback inside an active trace risks mixed behavior, repeated tools, and ambiguous evidence. Therefore:

- fallback is disabled by default;
- if a Bedrock startup probe fails and `MANIFEST_ALLOW_RECORDED_STARTUP_FALLBACK=true`, the process may start in `strands_recorded` mode before accepting any run;
- the selected mode is fixed for the process and recorded on each new trace;
- if Bedrock fails after a trace begins, that trace ends with a controlled failure;
- the operator may start a new, clearly labelled recorded-mode trace.

### 3.6 Initial Bedrock model choice

Use this explicit first configuration:

```text
Region:    us-east-1
Endpoint:  bedrock-runtime
Model ID:  us.amazon.nova-2-lite-v1:0
Provider:  Strands BedrockModel using AWS credentials
Streaming: false for the first stable path
Temperature: 0
Max output: 1000 tokens
```

Reasons:

- Nova 2 Lite is available in the owner's catalog and AWS currently marks its lifecycle active;
- it supports Bedrock Runtime, Converse, and client-side tool calling;
- it is an Amazon model, so no third-party Marketplace subscription or Anthropic first-use form is required;
- Strands can use it through the standard `BedrockModel`; and
- `us.amazon.nova-2-lite-v1:0` keeps routing within the US geography.

The console may list this model in a legacy-model section, but its model card currently reports an active lifecycle. That is acceptable for this time-boxed prototype. Recheck lifecycle status before any post-hackathon production use. Use the US inference-profile ID for calls from `us-east-1`; do not use the unprefixed base ID for the checkpoint gate.

Do not use `Agent()` without an explicit model. The Strands default currently selects an Anthropic Claude model and would introduce different permissions and setup.

### 3.7 Package pin

Start with:

```text
strands-agents==1.56.0
```

This was the current PyPI release when the plan was written and supports Python 3.10–3.14. Add it to a dedicated optional dependency group initially:

```toml
[project.optional-dependencies]
agents = [
  "strands-agents==1.56.0",
]
```

Do not install `strands-agents-tools`; Manifest exposes only its own governed tools.

The Checkpoint 12 Bedrock environment command becomes:

```bash
python3 -m pip install -e '.[dev,agents]'
```

## 4. Runtime contracts

### 4.1 Agent runtime protocol

Introduce a protocol that is independent of Strands types:

```python
class AgentRuntime(Protocol):
    name: str
    model_mode: str

    def run_role(
        self,
        *,
        role: AgentName,
        trace_id: str,
        objective: str,
        allowed_tools: tuple[str, ...],
    ) -> AgentRunResult: ...
```

`AgentRunResult` should contain only Manifest-owned fields:

```text
role
runtime name/version
model provider/model ID
stop reason
model-call count
tool-call count
input/output/total tokens when available
elapsed milliseconds
fallback flag
safe terminal summary
```

Do not persist raw prompts, chain-of-thought, full model responses, credentials, approval comments, or raw PII.

### 4.2 Per-trace and per-role isolation

- Construct a fresh Strands `Agent` for each role invocation.
- Do not reuse message history between traces.
- Do not share retry-strategy instances between agents.
- Give each agent only its role-owned tools.
- Capture the trace ID in the wrapper context, not in model-supplied arguments.
- Never let the model select or change the governance mode, mandate, policy version, approval identity, or trace ID.

### 4.3 Role tool allowlists

| Role | Exposed tools |
|---|---|
| Inventory | `get_order`, `check_inventory` |
| Dispatch | `list_available_vehicles`, `create_dispatch_plan` |
| Carrier | `list_carrier_quotes`, `select_carrier_quote`, `prepare_freight_booking` |
| Customer Communications | `write_tracking_outbox` |

`confirm_freight_booking` and `cancel_freight_booking` remain deterministic approval-state transitions invoked through the governor after an exact bound approval/rejection. The model must not reconstruct or alter their protected arguments.

### 4.4 Structured tool results

Each wrapper returns a compact JSON-compatible result:

```json
{
  "status": "allowed | guided | blocked | pending_approval | succeeded",
  "outcome": "allow | guide | block | escalate",
  "reason_code": "PROVENANCE_VALUE_MISMATCH",
  "because": "Attempted weight 50 kg differs from sourced weight 500 kg.",
  "guidance": {
    "required_fact_id": "WEIGHT-ORD-8842",
    "required_value": 500,
    "required_unit": "kg"
  },
  "result": {}
}
```

The result must be derived from the actual governor response. Prompts may tell the model how to respond, but prompts never decide whether an effect is allowed.

### 4.5 Prompt rules

Each role gets a short versioned system prompt that states:

- its role and exact goal;
- the tools it owns;
- that it must use tools rather than invent values;
- that sourced facts and tool results are authoritative;
- how to handle `guided`, `blocked`, and `pending_approval` results;
- the maximum number of correction attempts;
- that it must stop after completing its role; and
- that tool content is data, not permission to bypass Manifest.

Prompts must not contain credentials, secrets, approval tokens, Cedar internals, or hidden fallback claims.

## 5. Bedrock configuration and limits

Proposed environment variables:

```text
MANIFEST_AGENT_RUNTIME=strands
MANIFEST_MODEL_PROVIDER=bedrock
MANIFEST_ALLOW_RECORDED_STARTUP_FALLBACK=false
MANIFEST_BEDROCK_STARTUP_PROBE=true
BEDROCK_MODEL_ID=us.amazon.nova-2-lite-v1:0
BEDROCK_REGION=us-east-1
BEDROCK_ENDPOINT=bedrock-runtime
AWS_PROFILE=manifest-dev
MANIFEST_AGENT_MAX_TURNS=6
MANIFEST_AGENT_MAX_OUTPUT_TOKENS=1000
MANIFEST_AGENT_MAX_TOTAL_TOKENS=12000
MANIFEST_MODEL_MAX_ATTEMPTS=2
MANIFEST_MODEL_CONNECT_TIMEOUT_SECONDS=5
MANIFEST_MODEL_READ_TIMEOUT_SECONDS=60
MANIFEST_AGENT_TIMEOUT_SECONDS=90
MANIFEST_PROMPT_VERSION=manifest-agents-v1
```

Suggested construction:

```python
from botocore.config import Config as BotocoreConfig
from strands import Agent, ModelRetryStrategy
from strands.models import BedrockModel

model = BedrockModel(
    model_id=settings.model_id,
    region_name=settings.region,
    temperature=0,
    max_tokens=settings.max_output_tokens,
    streaming=False,
    boto_client_config=BotocoreConfig(
        retries={"max_attempts": 2, "mode": "standard"},
        connect_timeout=5,
        read_timeout=60,
    ),
)

agent = Agent(
    model=model,
    tools=role_tools,
    system_prompt=role_prompt,
    retry_strategy=ModelRetryStrategy(
        max_attempts=2,
        initial_delay=1,
        max_delay=4,
    ),
)

result = agent(
    role_objective,
    limits={
        "turns": 6,
        "output_tokens": 1000,
        "total_tokens": 12000,
    },
)
```

Confirm the exact constructor fields against the pinned SDK during implementation. Tests must validate settings rather than rely on library defaults.

The existing governor's total tool-call limit and guided-attempt limit remain active in addition to Strands' invocation limits.

## 6. Recorded offline model

Implement `RecordedManifestModel` as a Strands custom model provider rather than bypassing the Strands loop.

It should:

- implement the Strands `Model` interface;
- emit recorded tool-use streaming events compatible with the pinned SDK;
- choose responses by role, scenario, mode, and prior tool result;
- produce the same benign and adversarial tool attempts as the Bedrock path;
- exercise guide-back by first proposing 50 kg/unsafe carrier, reading the governor guidance, and retrying correctly;
- stop on pending approval;
- never call mock adapters directly; and
- identify itself as `recorded_manifest_v1` in health, trace metadata, and release evidence.

Recorded fixtures are source-controlled test data, not cached Bedrock output presented as live inference.

## 7. Observability and disclosure

### Health response additions

Add:

```text
agent_runtime
strands_version
model_provider
model_id
model_region
model_streaming
model_probe_ready
recorded_fallback_allowed
recorded_fallback_active
prompt_version
agent_limits
```

### Trace/evidence additions

The run-start metadata and release manifest should record:

```text
agent runtime and version
model provider and model ID
region
prompt version/checksum
limits
fallback state
```

### Metrics

Capture:

- model calls per role;
- tool calls per role;
- stop reason;
- latency per model call and role;
- token usage when supplied by the provider;
- throttle/error count; and
- whether the startup probe or recorded fallback was used.

Model lifecycle metrics may be emitted to structured logs and evaluation evidence. Do not add raw model content to the authoritative hash-chain ledger unless it is redacted and explicitly versioned.

## 8. Implementation work packages

### Work package 0 — Freeze Checkpoint 8 baseline

1. Review the current working tree.
2. Run the complete Checkpoint 8 gate.
3. Confirm its completion report and release evidence match the output.
4. Record or tag the exact baseline with owner authorization.

**Gate:** no unexplained working-tree change is carried into the Checkpoint 12 diff.

### Work package 1 — Bedrock preflight and package spike

1. Complete the manual AWS guide through the console playground test.
2. Pin `strands-agents==1.56.0` in an `agents` dependency group.
3. Add `scripts/probe_bedrock.py` using Boto3 `Converse` with no tools.
4. Add `scripts/probe_strands.py` with one harmless read-only test tool.
5. Record installed Strands/Boto3 versions, model ID, region, and probe latency.

**Gate:** one direct Bedrock response and one Strands read-only tool call succeed with the selected profile.

### Work package 2 — Runtime protocol and factory

1. Add Manifest-owned `AgentRuntime`, settings, result, and error contracts.
2. Wrap the current agents as the compatibility runtime.
3. Add explicit environment selection and fail-closed validation.
4. Extend health and release evidence.

**Gate:** all Checkpoint 8 tests pass without Strands installed in legacy mode.

### Work package 3 — Strands tool bridge

1. Build tool functions only from the existing registry metadata.
2. Use simple Nova-compatible top-level object schemas.
3. Bind trace and principal outside model arguments.
4. Return structured governor decisions and safe results.
5. Add hooks for audit/metrics and a test that every Strands tool reaches the governor exactly once.
6. Reject unregistered or wrong-owner tools before any effect.

**Gate:** a fake/recorded model cannot reach a mock effect without a Cedar-backed governor decision.

### Work package 4 — Recorded Strands runtime

1. Implement `RecordedManifestModel`.
2. Add role prompts and prompt versioning.
3. Run benign, adversarial shadow, and adversarial enforce through the Strands loop without AWS.
4. Preserve approval resume and exact-once behavior.

**Gate:** all hero paths pass in `strands + recorded` mode with Cedar and both storage adapters.

### Work package 5 — Live Bedrock runtime

1. Implement the configured `BedrockModel` factory targeting `bedrock-runtime`.
2. Add startup credential/model probe.
3. Add bounded retry, connection/read timeout, invocation limits, and error mapping.
4. Run role-by-role read-only probes before enabling writes.
5. Run the benign path twice.
6. Run adversarial shadow.
7. Run adversarial enforce through approval and verification.

**Gate:** the exact hero journey passes with health and trace showing `strands`, `bedrock`, `us.amazon.nova-2-lite-v1:0`, `us-east-1`, `bedrock-runtime`, and `fallback_active=false`.

### Work package 6 — Evaluation and completion evidence

1. Add recorded-mode cases to the deterministic evaluation gate.
2. Add a small live-Bedrock reliability set separate from deterministic policy accuracy metrics.
3. Report model tool-selection/replan success and latency with denominators.
4. Add Checkpoint 12 Bedrock evaluation JSON/Markdown and release manifest.
5. Add `scripts/run_checkpoint_12_bedrock.sh`.
6. Write `docs/CHECKPOINT_9_COMPLETION_REPORT.md` only after every gate passes.

**Gate:** complete local/offline and live-Bedrock evidence exists without overwriting earlier checkpoint artifacts.

## 9. Recommended files

```text
packages/agent_runtime/
  __init__.py
  protocol.py
  settings.py
  factory.py
  legacy.py
  prompts.py
  results.py
  errors.py
  strands_runtime.py
  strands_tools.py
  hooks.py
  recorded_model.py

fixtures/model_responses/
  manifest-agents-v1.json

scripts/
  probe_bedrock.py
  probe_strands.py
  run_checkpoint_12_bedrock.sh

tests/agent_runtime/
  test_settings.py
  test_factory.py
  test_strands_tool_bridge.py
  test_recorded_model.py
  test_role_isolation.py
  test_limits_and_failures.py
  test_runtime_disclosure.py

tests/integration/
  test_checkpoint_12_recorded_regression.py
  test_checkpoint_12_bedrock_live.py

docs/results/
  checkpoint-12-bedrock-evaluation.json
  checkpoint-12-bedrock-evaluation.md

docs/releases/
  checkpoint-12-strands-bedrock.json
```

## 10. Test strategy

### Always-run tests

- Checkpoints 1–8 regression suite.
- Runtime configuration validation.
- Role/tool allowlist and owner mismatch.
- Trace/principal values cannot be supplied or changed by model arguments.
- Every tool wrapper calls the governor once.
- Guide result is returned to the model and bounded replan succeeds.
- Block and escalation cause no unauthorized effect.
- Recorded model uses the Strands loop.
- Per-trace conversation isolation.
- Turn, token, tool, retry, and timeout handling.
- Bedrock is never contacted in recorded or legacy modes.
- No secret/raw prompt appears in event, API, dashboard, or evidence payloads.
- Memory and DynamoDB adapters retain parity.

### Opt-in live tests

Live tests must require both:

```text
RUN_BEDROCK_TESTS=true
MANIFEST_MODEL_PROVIDER=bedrock
```

They should skip—not fail—when deliberately disabled, but fail if enabled and credentials/model access are invalid.

Live test sequence:

1. Direct `Converse` probe.
2. Strands read-only tool probe.
3. Inventory role.
4. Dispatch role with benign fixture.
5. Carrier role with benign fixture.
6. Communications role with synthetic recipient.
7. Benign enforce twice.
8. Adversarial shadow.
9. Adversarial enforce to pending approval.
10. Approval resume, exact-once confirmation, and chain verification.

Do not run the full 22-case deterministic policy suite against Bedrock repeatedly. Policy correctness belongs to Cedar tests; live model runs measure integration and reliability while controlling cost.

## 11. Acceptance criteria

### Framework and model

- `strands-agents==1.56.0` is pinned and disclosed.
- All four roles run through Strands in Checkpoint 12 Bedrock mode.
- One real Nova 2 Lite tool-calling journey succeeds through `bedrock-runtime` from `us-east-1`.
- The model and region are explicitly configured; no Strands default model is used.
- Recorded offline mode exercises Strands rather than bypassing it.

### Governance and safety

- No operational tool bypasses `ManifestGovernor`.
- Cedar remains authoritative for every tool attempt.
- Weight provenance and carrier guide-back succeed within limits.
- Spend escalation creates the same exact bound approval.
- Confirmation/cancellation remains deterministic, re-authorized, and exact-once.
- Unknown tool, wrong owner, missing context, Cedar failure, and storage failure fail closed.
- Bedrock errors never produce a protected effect.

### Reliability

- Benign enforce completes twice from clean reset.
- Adversarial shadow records counterfactual decisions and completes.
- Adversarial enforce reaches pending approval.
- Approval completes the original trace and verifies cleanly.
- Agent turn/token/tool/retry/time limits are tested.
- Separate traces do not share messages or agent instances.
- Startup-only recorded fallback is explicitly enabled, reported, and fixed before runs.

### Disclosure and evidence

- Health, trace, dashboard, evaluation, and release manifest show the actual runtime/model/fallback mode.
- Model calls, tool calls, stop reasons, latency, and available token counts are measured.
- No credentials, raw PII, task token, full prompt, or chain-of-thought is stored.
- Checkpoint 8 results remain available and unmodified.

## 12. Checkpoint gate command

The final script should support two levels:

```bash
# Offline, deterministic Strands gate
./scripts/run_checkpoint_12_bedrock.sh

# Live Bedrock integration gate
RUN_BEDROCK_TESTS=true \
AWS_PROFILE=manifest-dev \
AWS_REGION=us-east-1 \
MANIFEST_AGENT_RUNTIME=strands \
MANIFEST_MODEL_PROVIDER=bedrock \
BEDROCK_MODEL_ID=us.amazon.nova-2-lite-v1:0 \
BEDROCK_ENDPOINT=bedrock-runtime \
./scripts/run_checkpoint_12_bedrock.sh
```

The live command must not require real AWS credentials to be stored in repository files.

## 13. Manual owner checkpoints

| When | Owner action | Agent can continue without it? |
|---|---|---|
| Before package/live spike | Review/commit or tag the verified Checkpoint 8 baseline | Offline planning yes; implementation should wait for baseline identification |
| Before first Bedrock call | Create budget, IAM policy, model access, and secure local AWS login using the manual guide | Recorded/offline implementation yes; live gate no |
| At first successful probe | Confirm no unexpected cost/resource was created | Yes |
| Before completion claim | Run or observe one live hero journey and confirm the disclosed region/model | No |
| After session | Log out; delete fallback long-term key when no longer needed | Completion evidence can remain; security cleanup remains owner responsibility |

The owner must never send credentials to the implementation agent. Only success/failure status and sanitized error messages are needed.

## 14. Failure and fallback behavior

| Failure | Required behavior |
|---|---|
| Missing Strands package in `strands` mode | Startup fails with install instructions |
| Invalid runtime/model configuration | Startup fails before accepting a run |
| Missing/expired AWS credentials | Bedrock startup probe fails; no live run begins |
| Bedrock access denied or invalid model ID | Controlled readiness failure with sanitized error category |
| Bedrock throttle | At most the configured bounded retry; no effect is duplicated |
| Bedrock timeout during a trace | Trace becomes failed with safe reason; no same-trace fallback |
| Model emits invalid tool arguments | Schema rejection returns a controlled error; model may retry within limits |
| Model repeatedly ignores guidance | Retry/turn/tool limit stops the role and fails safely |
| Model asks for an unowned tool | Tool is unavailable; any forged call fails at governor ownership checks |
| Cedar unavailable | Protected action fails closed exactly as in Checkpoint 7/8 |
| DynamoDB unavailable | Protected transition fails without executing an unrecorded effect |
| Recorded startup fallback enabled | Process starts and remains explicitly `strands_recorded`; UI/health disclose it |

## 15. Scope exclusions

- AWS application deployment, Lambda, API Gateway, Amplify, Step Functions, and EventBridge.
- Amazon Bedrock Agents managed service.
- Strands swarms, graphs, A2A, MCP, memory, or community tools.
- A second Cedar policy bundle inside Strands.
- LLM authorization, LLM-as-judge, or prompt-only safety.
- Real logistics systems or customer data.
- Model comparison, fine-tuning, RAG, Knowledge Bases, or Guardrails.
- Automatic mid-run provider switching.
- Dashboard redesign.

## 16. Exit gate

Checkpoint 12 is complete only when:

1. Checkpoint 8 remains green.
2. All four roles run through Strands with the recorded model.
3. All tools pass through the Manifest governor and Cedar.
4. The complete recorded/offline hero path passes with DynamoDB-compatible persistence.
5. One live Bedrock-backed hero journey passes using the explicit selected model, or an external account restriction is documented with the live gate marked blocked rather than complete.
6. Limits, failures, and disclosure tests pass.
7. Checkpoint 12 evaluation and release evidence are generated.
8. The completion report states exactly which runs used Bedrock and which used recorded responses.

Plain-Python agents alone do not complete Checkpoint 12. A direct Boto3 model response without Strands tool use does not complete it. A Strands agent that calls mock tools without the Manifest governor does not complete it.

## 17. Official references

- [Strands Agents Python quickstart](https://strandsagents.com/docs/user-guide/quickstart/python/)
- [Strands Bedrock model provider](https://strandsagents.com/docs/user-guide/concepts/model-providers/amazon-bedrock/)
- [Strands agent loop and invocation limits](https://strandsagents.com/docs/user-guide/concepts/agents/agent-loop/)
- [Strands retry strategies](https://strandsagents.com/docs/user-guide/concepts/agents/retry-strategies/)
- [Strands hooks](https://strandsagents.com/docs/user-guide/concepts/agents/hooks/)
- [Strands custom model providers](https://strandsagents.com/docs/user-guide/concepts/model-providers/custom_model_provider/)
- [Strands tools](https://strandsagents.com/docs/user-guide/concepts/tools/)
- [Strands Agents 1.56.0 package](https://pypi.org/project/strands-agents/1.56.0/)
- [Amazon Nova 2 Lite model card](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-amazon-nova-2-lite.html)
- [Amazon Bedrock model access](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)
- [Amazon Bedrock inference permissions](https://docs.aws.amazon.com/bedrock/latest/userguide/inference.html)
- [AWS local console-credential login](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html)

References were checked on 19 September 2026. Package versions, model availability, pricing, and console labels are time-sensitive and must be rechecked when implementation begins.
