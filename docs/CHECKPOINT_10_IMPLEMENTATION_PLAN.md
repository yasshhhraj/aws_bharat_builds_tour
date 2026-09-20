# Checkpoint 10 Implementation Plan — Hosted Provider Portability

**Plan version:** 1.0

**Created:** 20 September 2026

**Checkpoint state:** Offline implementation complete; live OpenRouter gate pending owner key

**Depends on:** Completed Checkpoint 9 offline Strands runtime

**Selected live provider:** Amazon Bedrock Mantle (amended after OpenRouter full-gate failures)

**Selected model:** `qwen.qwen3-coder-next`

**Selected manual setup:** [`manual/CHECKPOINT_10_BEDROCK_MANTLE_SETUP.md`](manual/CHECKPOINT_10_BEDROCK_MANTLE_SETUP.md)

**Historical OpenRouter setup:** [`manual/CHECKPOINT_10_OPENROUTER_SETUP.md`](manual/CHECKPOINT_10_OPENROUTER_SETUP.md)

> **Provider pivot:** OpenRouter completed isolated Inventory probes but failed
> repeatable multi-role validation through both its free router and a fixed free
> model. The provider-neutral implementation is retained, but the Checkpoint 10
> live acceptance gate now uses the explicit, paid Bedrock Mantle endpoint. All
> governance, completion, timeout, evidence, and no-fallback requirements below
> still apply.

**Next checkpoint:** Checkpoint 11 — Local Prototype Hardening

## 1. Objective

Add OpenRouter as the first live hosted-model provider without changing Manifest's orchestration, governed tools, Cedar authorization, approvals, commitment accounting, persistence, or ledger behavior. At the same time, establish a model factory that can construct Amazon Bedrock later from configuration alone.

Checkpoint 10 succeeds when:

- the recorded model remains the default deterministic provider;
- OpenRouter runs through Strands' `OpenAIModel` integration;
- the same `StrandsRuntime` and governed tools work with recorded, OpenRouter, and future Bedrock models;
- one live OpenRouter read-only probe and one benign hero journey complete;
- an adversarial run proves that Cedar, not the model, remains authoritative;
- hosted-provider failures are classified, sanitized, recorded, and fail closed;
- no automatic application-level provider fallback occurs; and
- the full Checkpoint 9 offline gate remains green.

This checkpoint does not require an AWS account or a working Bedrock invocation.

## 2. Verified starting state

Checkpoint 9 is complete in the current working tree. Its completion report records:

```text
Checkpoint 9 gate:          passed twice consecutively
Live-Cedar Python gate:     181 passed, 10 skipped
Storage gate:               11 passed
Rust/Cedar tests:            2 passed
Evaluation:                 22/22 passed
Functional digest parity:   matched Checkpoint 8
Strands version:            1.56.0
```

Relevant current implementation:

| File | Current responsibility | Checkpoint 10 change |
|---|---|---|
| `apps/runtime/runtime_settings.py` | Permits only legacy/deterministic and Strands/recorded combinations | Add explicit recorded/OpenRouter/Bedrock provider validation |
| `apps/runtime/runtime_factory.py` | Builds legacy agents or `StrandsRecordedRuntime` | Build one provider-neutral `StrandsRuntime` |
| `apps/runtime/strands_runtime.py` | Constructs `RecordedManifestModel` directly | Obtain a Strands `Model` from the model factory |
| `apps/runtime/recorded_model.py` | Deterministic offline Strands model | Remain unchanged except for shared metrics compatibility if needed |
| `apps/runtime/strands_tools.py` | Narrow governor-backed role tools | Add completion/cancellation guards; do not add provider logic |
| `apps/runtime/agent_runtime.py` | Project-owned role runtime contract | Expand provider-neutral metrics only |

Before implementation, run:

```bash
cd /home/yashraj/p0/project
./scripts/run_checkpoint_9_offline.sh
```

Do not discard the current uncommitted Checkpoint 8/9 work. Review `git status --short` before each work package.

## 3. Architecture decision

### 3.1 Use the Strands `Model` contract as the provider seam

Do not create an OpenRouter-specific agent runtime. Recorded, OpenRouter, and Bedrock models all satisfy the Strands model contract, so provider construction belongs behind one project-owned factory.

```text
CLI / FastAPI
      |
      v
RunService
      |
      v
ShipmentOrchestrator
      |
      v
StrandsRuntime
      |
      v
ManifestModelFactory.create(settings, invocation_context)
      |
      +-------------------+--------------------+
      |                   |                    |
      v                   v                    v
RecordedManifestModel  OpenAIModel         BedrockModel
                       OpenRouter endpoint  AWS Bedrock Runtime
      |                   |                    |
      +-------------------+--------------------+
                          |
                          v
                  Same Strands Agent
                          |
                          v
                 Same governed role tools
                          |
                          v
             ManifestGovernor.execute_tool
                          |
                          v
                        Cedar
```

The runtime must not contain `if provider == ...` branches beyond asking the model factory for a model.

### 3.2 Use Strands' OpenAI-compatible provider

OpenRouter is exposed through:

```python
from strands.models.openai import OpenAIModel
```

with the fixed endpoint:

```text
https://openrouter.ai/api/v1
```

Do not add the OpenRouter SDK, a custom REST client, LiteLLM, or another agent framework. Strands already normalizes OpenAI-compatible tool calls into the same event loop used by Bedrock.

### 3.3 Construct a fresh model per isolated role invocation

`RecordedManifestModel` requires the invocation context, and Strands' OpenAI provider creates request-scoped asynchronous clients. For consistent isolation, the model factory receives the current `GovernedInvocationContext` and creates a model for each role invocation.

The provider credential may be reused through the process environment, but model messages, tools, metrics, and context must never be shared across traces or roles.

### 3.4 No application-level fallback

These are separate disclosed runs:

```text
recorded run   -> model_provider=recorded
OpenRouter run -> model_provider=openrouter
Bedrock run    -> model_provider=bedrock
```

If OpenRouter fails, the current trajectory fails. The user may deliberately begin a new trace in recorded mode, but the application must not continue the same trace with another provider.

`openrouter/free` is itself a disclosed router that may select different free models. That external routing is acceptable only for the non-deterministic live path and must be visible as the requested model. It is not equivalent to a fixed model.

### 3.5 Keep Bedrock construction ready but inactive

Checkpoint 10 should implement and unit-test the Bedrock branch of the model factory without invoking AWS. This makes the later switch a configuration change plus a live parity gate:

```text
MANIFEST_MODEL_PROVIDER=bedrock
MANIFEST_MODEL_ID=us.amazon.nova-2-lite-v1:0
MANIFEST_BEDROCK_REGION=us-east-1
```

No AWS credential, console task, or network call is required during Checkpoint 10.

## 4. Configuration contract

### 4.1 Common settings

| Variable | Default | Validation | Disclosed? |
|---|---|---|---:|
| `MANIFEST_AGENT_RUNTIME` | `legacy` | `legacy` or `strands` | Yes |
| `MANIFEST_MODEL_PROVIDER` | Runtime-dependent safe default | `deterministic`, `recorded`, `openrouter`, or `bedrock` | Yes |
| `MANIFEST_MODEL_ID` | Runtime-dependent safe default | Non-empty and valid for selected provider | Yes |
| `MANIFEST_AGENT_MAX_TURNS` | `8` | Integer 1–12 | Yes |
| `MANIFEST_AGENT_TIMEOUT_SECONDS` | `15` | Greater than 0 and at most 60 | Yes |
| `MANIFEST_MODEL_MAX_OUTPUT_TOKENS` | `1024` | Integer 128–2048 | Yes |

### 4.2 OpenRouter settings

| Variable | Required | Handling |
|---|---:|---|
| `OPENROUTER_API_KEY` | Yes for OpenRouter mode | Read only while building the model; never put in settings output, traces, logs, or exceptions |
| OpenRouter base URL | Fixed in code | Do not make it user-configurable in the prototype |
| `MANIFEST_MODEL_ID` | Yes | Start with `openrouter/free`; prefer an explicit tested `:free` model for the final live evidence |

Do not add the key to `.env.example`. Documentation may name the variable, but it must never contain a value in the repository.

### 4.3 Bedrock settings

| Variable | Required | Handling |
|---|---:|---|
| `MANIFEST_BEDROCK_REGION` | In Bedrock mode | Default `us-east-1`; pass explicitly to `BedrockModel` |
| `MANIFEST_MODEL_ID` | In Bedrock mode | Later use `us.amazon.nova-2-lite-v1:0` |
| AWS credentials | Only for future live invocation | Use the standard Boto3 credential chain; never add to `RuntimeSettings` |

### 4.4 Valid combinations

| Runtime | Provider | Model | Result |
|---|---|---|---|
| `legacy` | `deterministic` | `manifest-deterministic-v1` | Allowed compatibility mode |
| `strands` | `recorded` | `manifest-recorded-v1` | Allowed default and deterministic gate |
| `strands` | `openrouter` | Non-empty OpenRouter slug/router | Allowed when key and optional dependency exist |
| `strands` | `bedrock` | Non-empty Bedrock model/profile ID | Construction allowed; live gate deferred |
| Any other combination | Any | Any | Fail at startup with `RuntimeConfigurationError` |

Provider selection is fixed for the lifetime of a `RunService` instance.

## 5. Dependency strategy

Keep core recorded mode small and add OpenRouter through an optional dependency group:

```toml
[project.optional-dependencies]
openrouter = [
  "strands-agents[openai]==1.56.0",
]
```

Retain the existing core pin:

```toml
"strands-agents==1.56.0"
```

Install the selected development environment with:

```bash
.venv/bin/pip install -e '.[dev,openrouter]'
```

The OpenAI provider import must be lazy so recorded mode still starts with only the core dependency. If OpenRouter mode is selected without its optional dependency, raise an actionable configuration error without exposing secrets.

Bedrock support uses Strands' native `BedrockModel`; Boto3 is already a project dependency.

## 6. Model factory contract

Add a project-owned factory with a small interface:

```python
from typing import Protocol
from strands.models import Model


class ManifestModelFactory(Protocol):
    def create(
        self,
        settings: RuntimeSettings,
        context: GovernedInvocationContext,
    ) -> Model:
        ...
```

Recommended production behavior:

```python
if provider == "recorded":
    return RecordedManifestModel(context, model_id=settings.model_id)

if provider == "openrouter":
    return OpenAIModel(
        client_args={
            "api_key": require_openrouter_key(),
            "base_url": OPENROUTER_BASE_URL,
            "max_retries": 0,
            "timeout": settings.timeout_seconds,
        },
        model_id=settings.model_id,
        params={
            "max_tokens": settings.max_output_tokens,
            "temperature": 0,
        },
    )

if provider == "bedrock":
    return BedrockModel(
        model_id=settings.model_id,
        region_name=settings.bedrock_region,
        max_tokens=settings.max_output_tokens,
        temperature=0,
        boto_client_config=bounded_boto_config(settings),
    )
```

This is design pseudocode, not permission to log `client_args` or model instances. Confirm exact installed SDK signatures with focused tests before committing the implementation.

Use zero SDK retries for Checkpoint 10. An invisible retry can consume scarce free requests or repeat planning after an effect. If retries are introduced later, they must be explicit, bounded, observable, and limited to calls known to be safe.

## 7. Generalize the Strands runtime

Rename `StrandsRecordedRuntime` to `StrandsRuntime` and inject a model factory:

```python
class StrandsRuntime(RoleRuntime):
    def __init__(self, settings, model_factory=None):
        self.settings = settings
        self.model_factory = model_factory or DefaultManifestModelFactory()

    def invoke(self, request):
        context = GovernedInvocationContext(...)
        model = self.model_factory.create(self.settings, context)
        agent = Agent(model=model, tools=build_strands_tools(context), ...)
        ...
```

### Provider-neutral result metrics

The current runtime reads `RecordedManifestModel.model_call_count`, which does not exist on hosted models. Replace that dependency with provider-neutral Strands result metrics:

```text
result.metrics.cycle_count
result.metrics.accumulated_usage.inputTokens
result.metrics.accumulated_usage.outputTokens
result.metrics.accumulated_usage.totalTokens
```

Usage values may be absent or zero. Store `null`/unknown rather than inventing numbers.

### Completion assertion

A live model may answer with prose without executing a required tool. `stop_reason=end_turn` is therefore insufficient.

After the Strands invocation:

1. verify that the context is not cancelled;
2. verify that only allowed tools ran;
3. verify the required phase completion predicate;
4. then accept the textual summary.

Examples:

- Inventory must have an order and inventory fact.
- Dispatch must have a dispatch plan or an explicit policy-blocked result.
- Carrier RUN must have a selected quote and prepared/confirmed/pending state appropriate to policy.
- Carrier RESUME must produce the existing confirmed booking.
- Carrier CANCEL must produce the governed cancellation.
- Communications must produce exactly one tracking outbox effect.

If the model only explains what it would do, fail the invocation without marking the role complete.

## 8. Prompt and tool requirements

### System prompt

Use one provider-neutral system prompt. It must state:

- this is the synthetic Manifest prototype;
- use only the supplied tools;
- execute the role task instead of describing hypothetical actions;
- call one tool at a time;
- use governed tool results as authoritative facts;
- follow guide-back information returned by tools;
- never invent identity, policy, approval, numeric facts, IDs, or side effects;
- stop after the role's completion predicate is satisfied.

Do not mention OpenRouter, Bedrock, model vendor, API keys, or provider-specific behavior in the operational prompt.

### Invocation prompt

The invocation prompt may include only:

- bound role name;
- bound phase;
- synthetic order ID;
- a short statement of the role completion objective.

The model should obtain operational facts through governed read tools, not from an unverified state dump in the prompt.

### Tool boundary

Do not change these Checkpoint 9 guarantees:

- role, trace ID, policy mode, approval, action hash, and idempotency key remain outside model arguments;
- tools are role-scoped;
- all operations call `ManifestGovernor.execute_tool`;
- effectful tools execute sequentially;
- no generic HTTP, shell, filesystem, database, Python, or cloud tools are exposed;
- malformed/unknown/wrong-role tool calls fail closed.

### Cancelled invocation guard

Add an `active`/`closed` state to `GovernedInvocationContext`. Every wrapper checks it before executing. On timeout or terminal failure, close the context before returning control to the caller. This prevents a late hosted-model callback from executing a tool after the run has already been marked failed.

## 9. Error classification and fail-closed behavior

Add stable project error categories without persisting raw provider exception bodies:

| Condition | Project category | Run outcome | Automatic retry? |
|---|---|---|---:|
| Missing key or optional dependency | `PROVIDER_CONFIGURATION_ERROR` | Startup rejected | No |
| HTTP 401/403 | `PROVIDER_AUTHENTICATION_ERROR` | Failed before next action | No |
| HTTP 402 / paid-only model | `PROVIDER_BILLING_ERROR` | Failed before next action | No |
| HTTP 404 / model unavailable | `PROVIDER_MODEL_UNAVAILABLE` | Failed before next action | No |
| HTTP 429 | `PROVIDER_RATE_LIMITED` | Failed before next action | No |
| Timeout | `PROVIDER_TIMEOUT` | Context closed; run failed | No |
| 5xx/network failure | `PROVIDER_UNAVAILABLE` | Context closed; run failed | No |
| Text-only response with no required action | `AGENT_INCOMPLETE` | Role/run failed | No |
| Invalid/wrong-role tool request | Existing governed runtime error | No unauthorized effect | No |

Persist only the category, provider, requested model, trace ID, stage, and safe request/correlation identifier when the SDK exposes one. Never persist authorization headers, API keys, raw client configuration, complete provider response bodies, or full prompt content.

If a provider fails after an already-authorized effect, do not roll the effect back or replay it automatically. Preserve the valid committed state, record the run failure, and rely on existing idempotency/approval semantics for deliberate recovery.

## 10. Observability and disclosure

Extend health/run/evidence fields with:

```text
runtime_mode
model_provider
requested_model_id
resolved_model_id        # null when not available from the SDK
provider_route_kind      # fixed | router
provider_fallback_active # always false at application level
agent_max_turns
agent_timeout_seconds
model_max_output_tokens
model_cycles
input_tokens             # nullable
output_tokens            # nullable
total_tokens             # nullable
provider_failure_category
```

For `openrouter/free`:

- report `requested_model_id=openrouter/free`;
- report `provider_route_kind=router`;
- do not claim a resolved model unless it was actually observed;
- use the OpenRouter Activity page as manual evidence if Strands does not expose the routed model;
- never relabel the run as a fixed-model run.

The dashboard should show that OpenRouter mode is live, hosted, non-deterministic, and limited to synthetic data.

## 11. Implementation work packages

### WP0 — Reconfirm the offline baseline

1. Run `./scripts/run_checkpoint_9_offline.sh`.
2. Record `git status --short` and the source revision.
3. Confirm no API key is present in repository files or shell command history.

**Gate:** Checkpoint 9 remains green before provider work begins.

### WP1 — Optional dependency and settings

1. Add the `openrouter` optional dependency group.
2. Add output-token and Bedrock-region settings.
3. Replace the exact two-combination validation with the explicit matrix above.
4. Keep secrets outside `RuntimeSettings` and `describe()`.
5. Add settings and missing-dependency tests.

**Gate:** recorded mode works without importing the OpenAI provider; invalid combinations fail at startup.

### WP2 — Provider-neutral model factory

1. Add `ManifestModelFactory` and its default implementation.
2. Move recorded-model construction out of `strands_runtime.py`.
3. Add lazy OpenRouter `OpenAIModel` construction.
4. Add construction-only `BedrockModel` support.
5. Fix the OpenRouter endpoint in code.
6. Add bounded client timeouts and zero retries.
7. Add secret-redaction tests.

**Gate:** unit tests construct all three providers without making network calls.

### WP3 — Generic runtime, completion, and cancellation

1. Rename/generalize `StrandsRecordedRuntime`.
2. Inject the model factory.
3. Read cycle/token usage from Strands result metrics.
4. Add provider-neutral completion predicates.
5. Close invocation context on timeout/failure.
6. Keep a fresh agent/model/context per role invocation.

**Gate:** all recorded Strands journeys pass with unchanged protected outcomes.

### WP4 — Safe prompts and provider failure mapping

1. Add provider-neutral role objectives.
2. Map provider exceptions to safe categories.
3. Ensure raw provider errors never enter user-visible summaries or durable events.
4. Test no-tool prose, malformed calls, timeout, 401, 402, 404, 429, and 5xx behavior with fakes.

**Gate:** every simulated hosted-provider failure leaves governed state valid and emits a sanitized category.

### WP5 — OpenRouter preflight and staged live probe

1. Add `scripts/check_openrouter_ready.py` for key/configuration validation.
2. Add an opt-in live read-only Inventory probe.
3. Begin with `openrouter/free`.
4. Inspect OpenRouter Activity to identify the resolved model.
5. Prefer an explicit tested `:free` model for the full live gate when available.
6. Run one benign journey, then one adversarial enforce journey.

**Gate:** the provider performs actual Strands tool use; prose-only output is not accepted.

### WP6 — Evidence and regression gate

1. Add `scripts/run_checkpoint_10_openrouter.sh`.
2. Keep offline and live phases separate.
3. Run all deterministic tests and the Checkpoint 9 gate without the API key.
4. Run the live phase only with an explicit opt-in environment flag.
5. Generate sanitized JSON/Markdown evidence and a release manifest.
6. Add the completion report and README instructions.

**Gate:** deterministic gates pass repeatedly; one deliberately invoked live gate passes without exposing the key.

## 12. Recommended file changes

```text
pyproject.toml
.env.example                         # provider examples only; no secret value
README.md

apps/runtime/
  model_factory.py                   # new provider seam
  runtime_settings.py                # provider matrix and safe settings
  runtime_factory.py                 # generic Strands runtime construction
  strands_runtime.py                 # provider-neutral runtime
  strands_tools.py                   # completion/cancellation guard
  provider_errors.py                 # optional safe error classifier

packages/domain/
  errors.py                          # stable provider/runtime error types
  models.py                          # only if evidence fields need domain support

tests/agents/
  test_model_factory.py
  test_runtime_settings.py
  test_strands_runtime.py
  test_openrouter_error_mapping.py
  test_provider_secret_redaction.py

tests/integration/
  test_strands_recorded_runtime.py   # retained regression
  test_strands_hosted_fake_runtime.py
  test_openrouter_live.py            # skipped unless explicitly enabled

scripts/
  check_openrouter_ready.py
  run_checkpoint_10_openrouter.sh

docs/
  CHECKPOINT_10_COMPLETION_REPORT.md
  results/checkpoint-10-openrouter-*.json
  results/checkpoint-10-openrouter-*.md
  releases/checkpoint-10-openrouter.json
```

Do not duplicate the four agents or the governed tool bridge under an `openrouter` directory.

## 13. Test strategy

### Always-run, no-network tests

- configuration matrix and bounds;
- lazy optional dependency behavior;
- model factory construction with patched SDK constructors;
- no secret in `repr`, health, events, errors, or release evidence;
- generic runtime with a scripted fake hosted model;
- completion predicate enforcement;
- wrong-role, unknown, malformed, duplicate, and late-after-timeout tool calls;
- provider error classification;
- provider-neutral metrics with missing usage fields;
- all existing Checkpoint 9 recorded journeys;
- full Python, Cedar/Rust, storage, and evaluation gates.

### Opt-in live tests

Live tests require all of:

```text
MANIFEST_RUN_LIVE_OPENROUTER=1
MANIFEST_AGENT_RUNTIME=strands
MANIFEST_MODEL_PROVIDER=openrouter
MANIFEST_MODEL_ID=<router or explicit free model>
OPENROUTER_API_KEY=<present in process environment>
```

Without the opt-in flag, tests skip before constructing a hosted provider.

Live sequence:

1. key metadata/preflight;
2. read-only Inventory tool probe;
3. benign enforce hero journey;
4. adversarial enforce journey;
5. approval resume only if request quota remains and earlier stages are stable.

Do not run all 22 evaluation cases live. The deterministic recorded provider remains the full evaluation oracle.

## 14. Free-request budget

As checked on 20 September 2026, OpenRouter advertises a free plan with 50 requests per day. One Strands role may use several provider calls because each tool result returns to the model.

Use a deliberate request budget:

| Activity | Approximate provider calls | Rule |
|---|---:|---|
| Key metadata check | 0 model calls | Safe anytime |
| Read-only Inventory probe | 2–4 | Run first |
| Benign four-role journey | Approximately 12–18 | Run once after the probe passes |
| Adversarial/approval journey | Approximately 15–22 | Run only after benign is stable |
| Full 22-case evaluation | Too many | Never run live on the free route |

The estimates are planning bounds, not guaranteed provider billing units. Instrument and record actual Strands cycle/token metrics. On HTTP 429, stop; do not loop or automatically retry.

## 15. Planned checkpoint commands

After implementation, the normal deterministic gate remains:

```bash
./scripts/run_checkpoint_9_offline.sh
```

The Checkpoint 10 script should support two explicit phases:

```bash
# No hosted request; always safe to run.
./scripts/run_checkpoint_10_openrouter.sh --offline

# Hosted requests; requires deliberate opt-in and the key in this shell.
MANIFEST_RUN_LIVE_OPENROUTER=1 \
  ./scripts/run_checkpoint_10_openrouter.sh --live
```

The script must refuse `--live` when the opt-in flag, key, provider, or model ID is missing. It must not print the key or use shell tracing.

## 16. Acceptance criteria

### Architecture

- [x] One provider-neutral `StrandsRuntime` serves recorded, OpenRouter, and Bedrock construction paths.
- [x] One model factory contains provider-specific construction.
- [x] No OpenRouter branch exists in orchestration, agents, tools, governor, policy, approval, storage, or ledger code.
- [x] Bedrock requires only configuration and its later live parity test.

### Security and governance

- [x] OpenRouter key is never committed, logged, persisted, returned by health endpoints, or included in evidence.
- [x] Only synthetic data is sent to OpenRouter.
- [x] Every operational tool remains governed by Cedar.
- [x] Late calls after timeout are rejected.
- [x] Provider failure never silently changes provider or bypasses policy.

### Functional proof

- [x] Recorded Checkpoint 9 gate remains green.
- [ ] Live OpenRouter performs a governed read-only tool call.
- [ ] Live benign journey reaches the expected protected state.
- [ ] Live adversarial journey remains blocked/guided/approval-bound according to Cedar.
- [x] Exact-once, commitment, and ledger invariants remain valid in the offline regression gate.

### Disclosure and evidence

- [x] Runtime, provider, requested model, router/fixed status, limits, and nullable usage are visible.
- [x] `openrouter/free` is described as a changing router, not a fixed model.
- [x] Resolved model is recorded only when actually observed.
- [x] Evidence is sanitized and the implementation report records the source revision and dependency versions.

## 17. Exit gate

Checkpoint 10 is complete only when:

1. all no-network provider-contract tests pass;
2. the full Checkpoint 9 offline gate still passes;
3. OpenRouter completes a governed read-only Inventory probe;
4. OpenRouter completes one benign hero journey;
5. one adversarial run proves Cedar remains authoritative;
6. rate-limit/timeout/error behavior is tested with fakes and fails closed;
7. no API key appears in repository or generated evidence;
8. the completion report records the requested model and, when observable, the resolved model; and
9. the owner revokes or retains the API key deliberately after the live gate.

## 18. Explicit exclusions

Checkpoint 10 does not include:

- AWS account setup or a live Bedrock request;
- Ollama unless OpenRouter becomes unusable and the roadmap is explicitly revised;
- paid OpenRouter models or purchasing credits;
- OpenRouter's separate Agent SDK;
- multi-provider fallback or model routing implemented inside Manifest;
- live execution of the full evaluation dataset;
- real carrier booking or customer messaging;
- weakening tool schemas, Cedar policies, approval binding, or exact-once behavior to accommodate a model.

## 19. Official references

- Strands model providers: <https://strandsagents.com/docs/user-guide/concepts/model-providers/>
- Strands OpenRouter integration: <https://strandsagents.com/docs/integrations/model-providers/openrouter/>
- Strands Amazon Bedrock provider: <https://strandsagents.com/docs/user-guide/concepts/model-providers/amazon-bedrock/>
- OpenRouter free router: <https://openrouter.ai/openrouter/free>
- OpenRouter pricing and current free limits: <https://openrouter.ai/pricing>
- OpenRouter current-key endpoint: <https://openrouter.ai/docs/api/api-reference/api-keys/get-current-key>
