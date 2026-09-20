# Manifest — Offline-First Checkpoints to Prototype Completion

**Plan version:** 2.1

**Rewritten:** 20 September 2026

**Baseline:** Checkpoints 1–10 complete in the current working tree

**Current checkpoint:** Checkpoint 11 — Local Prototype Hardening

**AWS state:** Bedrock Mantle operational; native Nova access remains deferred

## 1. Revised delivery strategy

AWS account verification must not block implementation. The remaining work now follows this order:

```text
Checkpoint 8 baseline
        |
        v
CP9  Offline Strands runtime + governed tools (complete)
        |
        v
CP10 Bedrock Mantle provider portability + live governed proof (complete)
        |
        v
CP11 Local prototype hardening + submission candidate
        |
        v
CP12 Bedrock parity after AWS verification
        |
        v
CP13 Optional AWS demo deployment
        |
        v
CP14 Final evidence and submission freeze
```

This creates two honest milestones:

1. **Local prototype complete at Checkpoint 11:** the full governed journey is hardened and reproducible offline, with separate completed Mantle evidence.
2. **AWS deployment target complete at Checkpoint 14:** native Nova parity if available, any required cloud deployment, and final evidence are complete.

The local milestone is not permission to claim that Bedrock or AWS deployment has been completed. It is a working fallback that allows development, testing, UI work, and rehearsal to continue.

## 2. Provider order

| Priority | Provider | Network | Cost/account | Purpose |
|---:|---|---|---|---|
| 1 | Recorded deterministic model | None | None | Mandatory repeatable acceptance and regression baseline |
| 2 | Bedrock Mantle Qwen3 Coder Next | Internet/AWS | Paid; temporary Bedrock API key | Completed Checkpoint 10 live-provider path |
| 3 | OpenRouter | Internet | Free availability and limits can change | Implemented experiment; full gate was unreliable |
| 4 | Ollama | Local only | No cloud account; requires suitable hardware | Optional contingency only |
| 5 | Amazon Nova 2 Lite | Internet/AWS | Native access still restricted | Optional native-provider parity when available |

Relevant provider documentation:

- Strands model providers: <https://strandsagents.com/docs/user-guide/concepts/model-providers/>
- Strands with Ollama: <https://strandsagents.com/docs/user-guide/concepts/model-providers/ollama/>
- Strands with OpenRouter: <https://strandsagents.com/docs/integrations/model-providers/openrouter/>
- OpenRouter free-model router: <https://openrouter.ai/openrouter/free>

### Non-negotiable provider rules

- The selected provider is explicit at process start and visible in diagnostics, traces, and demo evidence.
- Never silently change providers during an agent trajectory.
- The model proposes actions; `ManifestGovernor` and Cedar authorize them.
- Every operational effect continues through the governed tool boundary.
- Only synthetic Manifest data may be sent to any hosted provider.
- API keys and AWS credentials never enter the repository, `.env.example`, screenshots, logs, or submission artifacts.
- The free router is a development convenience, not the deterministic acceptance oracle. Free models, quotas, and routing can change.
- A provider outage must fail closed before a commitment is made.

## 3. Execution queue

| Order | Checkpoint | Status | Can start while AWS is verifying? | Exit result |
|---:|---|---|---|---|
| 9 | Offline Strands Runtime | **COMPLETE** | Yes | All four roles use Strands with the recorded model and governed tools |
| 10 | Bedrock Mantle Provider Portability | **COMPLETE** | Yes | Qwen probe, benign journey, and adversarial Cedar escalation passed |
| 11 | Local Prototype Hardening | **NEXT** | Yes | Rehearsed, reproducible local submission candidate |
| 12 | Bedrock Provider Parity | Waiting on AWS verification and CP11 | No live gate yet | Nova 2 Lite passes the same provider and governance contracts |
| 13 | AWS Demo Stack | Locked by CP12 | No | Reproducible least-privilege cloud deployment if required |
| 14 | Submission Freeze | Locked by release-path decision | Mostly | Final evidence, claims, artifacts, and tagged release |

Work one checkpoint at a time. A checkpoint closes only after its exit gate and evidence are recorded. Do not weaken Cedar, exact-once approval, numeric provenance, or ledger checks to make a model provider pass.

---

## Checkpoint 9 — Offline Strands Runtime

**Objective:** Replace the plain-Python action-selection layer with thin Strands agents while using a deterministic, offline recorded model. No AWS account, credential, API key, or network call is required.

**Detailed implementation plan:** [`CHECKPOINT_9_OFFLINE_IMPLEMENTATION_PLAN.md`](CHECKPOINT_9_OFFLINE_IMPLEMENTATION_PLAN.md)

### Scope

1. Pin and install the Strands SDK in the project environment.
2. Introduce an `AgentRuntime` boundary so orchestration does not depend directly on a provider SDK.
3. Implement `RecordedManifestModel` through the real Strands model interface.
4. Create thin Inventory, Dispatch, Carrier, and Customer Communications Strands agents.
5. Wrap existing operations as narrow, typed Strands tools.
6. Route every protected tool call through `ManifestGovernor.execute_tool`.
7. Keep the existing bounded four-stage workflow, approval lifecycle, Cedar evaluation, persistence, and ledger behavior unchanged.
8. Add explicit runtime/provider diagnostics and trace events.
9. Keep the legacy deterministic runtime temporarily available for parity comparison, not as a silent fallback.

### Required tests

- recorded-model protocol and malformed-response tests;
- one-tool, unknown-tool, duplicate-tool, and maximum-turn tests;
- role-to-tool allow-list tests;
- benign, shadow, enforce, approval, and tamper journeys through Strands;
- equality of protected state and authorization outcomes between legacy and Strands modes;
- proof that provider text cannot bypass Cedar or create direct effects;
- all Checkpoint 8 tests remain green.

### Exit gate

- All four roles execute through Strands in `recorded` mode.
- The entire hero journey completes without network access.
- Adversarial enforce mode remains blocked or guided back as designed.
- Exact-once confirmation and ledger verification still pass.
- Provider/runtime mode is shown in `/health`, traces, and evidence.
- A new `scripts/run_checkpoint_9_offline.sh` gate passes twice consecutively.
- No AWS environment variables or hosted-provider credentials are required.

### Manual work

None beyond approving dependency installation if the environment requests network permission. Do not work on the AWS console during this checkpoint.

### Explicit cuts

- no Bedrock invocation;
- no OpenRouter or Ollama integration yet;
- no AWS deployment;
- no autonomous planning beyond the bounded workflow;
- no direct tool execution outside the governor.

---

## Checkpoint 10 — Bedrock Mantle Provider Portability

**Objective:** Prove that the Strands runtime can swap to Amazon Bedrock Mantle without changing tools, policy, approval, state, or ledger semantics. OpenRouter remains an implemented but unreliable experimental path.

**Detailed implementation plan:** [`CHECKPOINT_10_IMPLEMENTATION_PLAN.md`](CHECKPOINT_10_IMPLEMENTATION_PLAN.md)

**Manual setup guide:** [`manual/CHECKPOINT_10_OPENROUTER_SETUP.md`](manual/CHECKPOINT_10_OPENROUTER_SETUP.md)

**Selected setup guide:** [`manual/CHECKPOINT_10_BEDROCK_MANTLE_SETUP.md`](manual/CHECKPOINT_10_BEDROCK_MANTLE_SETUP.md)

### Implementation work

1. Add a provider factory with explicit configuration:

   ```text
   MANIFEST_MODEL_PROVIDER=recorded|openrouter|bedrock_mantle|bedrock
   MANIFEST_MODEL_ID=<explicit model or router id>
   ```

2. Keep `recorded` as the default for tests and reproducible demos.
3. Add Strands OpenAI-compatible adapters for OpenRouter and Bedrock Mantle plus a construction-only native Bedrock branch.
4. Normalize provider output into the same tool-call contract.
5. Add request timeouts, turn limits, retry limits, and output-size limits.
6. Record provider, requested model, actual routed model when returned, latency, usage when returned, and failure category.
7. Ensure a provider failure stops the current trajectory; a retry or provider change starts a new disclosed run.

### Selected route — Bedrock Mantle

1. Generate a temporary Bedrock API key in the same Region where the playground worked.
2. Put the key only in the current shell through hidden input.
3. Start with `MANIFEST_MODEL_ID=qwen.qwen3-coder-next`.
4. Run a governed read-only Inventory probe.
5. Review the current Bedrock price before the paid probe and full gate.
6. Send only the synthetic `ORD-8842` fixture.
7. Remove the short-term key from the shell after testing.

Never paste the Bedrock key into source files, committed `.env` files, logs, screenshots, or chat.

### Required tests

- common provider contract suite against the recorded adapter;
- live read-only tool probe against Bedrock Mantle;
- live benign hero journey against the selected provider;
- adversarial enforce journey proving Cedar remains authoritative;
- provider timeout, rate-limit, invalid tool, and malformed-argument handling;
- no automatic provider switching inside a trajectory;
- recorded offline gate remains green.

### Exit gate

- At least one non-recorded provider completes a governed read-only tool call and benign hero journey.
- The same Cedar decisions, commitment limits, approval rules, and ledger invariants hold.
- Provider and model identity are visible in evidence.
- Hosted-provider failure can be reproduced without corrupting state.
- `scripts/run_checkpoint_10_bedrock_mantle.sh` passes, with the live portion clearly labelled paid and non-deterministic.

### OpenRouter outcome

OpenRouter completed isolated read-only probes but failed the complete multi-role gate through both the free router and a fixed free model. Keep those failures as honest evidence; do not repeatedly retry them. Bedrock Mantle is the selected live provider, and its reviewed probe, benign journey, and adversarial gate have passed.

---

## Checkpoint 11 — Local Prototype Hardening and Submission Candidate

**Objective:** Finish and rehearse the complete local prototype before returning to AWS.

### Scope

1. Show runtime, provider, requested model, actual model when known, policy mode, storage mode, and ledger state in the dashboard.
2. Add clear UI states for provider timeout, rate limit, authorization denial, approval required, duplicate confirmation, and tamper detection.
3. Remove stale placeholder claims and make simulated effects visually explicit.
4. Bound prompts and traces so only necessary synthetic fields reach the provider.
5. Add startup validation that reports missing optional provider configuration without breaking recorded mode.
6. Add a one-command local startup path and a one-command local acceptance gate.
7. Capture local screenshots, trace samples, test summaries, and a short backup demo recording.
8. Rehearse benign, shadow, enforce, guide-back, approval, exact-once, and tamper journeys twice from a clean local state.

### Required gates

```text
Checkpoint 8 Cedar + storage gate
Checkpoint 9 offline Strands gate
Checkpoint 10 provider contract gate
Full Python and Rust test suites
Evaluation dataset gate
Browser smoke and accessibility checks
Secret and stale-claim scan
Two clean local rehearsals
```

### Exit gate

- A new developer can follow the README and reproduce the local recorded-mode demo.
- The chosen no-cost/local provider path is separately documented and truthfully labelled.
- Offline mode remains sufficient for deterministic judging evidence.
- All error states fail closed and leave protected state valid.
- The local evidence bundle is complete enough to demo even if AWS is still unavailable.

### Manual work

- Review screenshots for secrets and personal account information.
- Record the short local backup demo.
- Verify that all claims say “local,” “simulated,” or “recorded model” where applicable.

---

## Checkpoint 12 — Bedrock Provider Parity

**Objective:** After AWS account verification succeeds, add Amazon Nova 2 Lite as another provider behind the already-tested Strands runtime.

**Deferred setup guide:** [`manual/CHECKPOINT_9_AWS_BEDROCK_SETUP.md`](manual/CHECKPOINT_9_AWS_BEDROCK_SETUP.md). The filename is retained for link stability, but the work now belongs to Checkpoint 12.

### Preconditions

- AWS reports that account verification is complete.
- A Bedrock playground or CLI probe no longer returns `ValidationException: Operation not allowed`.
- The owner has enabled cost monitoring and agreed to use paid AWS services.
- CP9–CP11 are green; do not change local governance semantics to accommodate Bedrock.

### Manual AWS work

1. Confirm account and payment verification in Billing/Account settings.
2. Use `us-east-1` unless the current model availability documentation requires another supported region.
3. Confirm access to Amazon Nova 2 Lite v1.
4. Test the US cross-region inference profile `us.amazon.nova-2-lite-v1:0`.
5. Create a non-root developer identity or temporary login for application testing.
6. Grant only the required Bedrock Runtime invocation permissions.
7. Create a small budget alert and review CloudTrail/cost visibility.

Do not create root access keys. Root console access does not repair an account-level `Operation not allowed` restriction.

### Implementation work

1. Add the Strands `BedrockModel` adapter to the provider factory.
2. Use the normal AWS credential chain; never load AWS secrets from committed configuration.
3. Keep the same tool schemas, governor boundary, timeouts, traces, and failure behavior as CP10.
4. Run a read-only tool probe before any effectful hero journey.
5. Record region, inference profile, provider, latency, and request identifiers without recording credentials or sensitive prompt content.

### Exit gate

- Nova 2 Lite completes a governed read-only tool call.
- A Bedrock-backed benign hero journey completes.
- Adversarial enforce mode remains denied/guided back by Cedar.
- Bedrock unavailability fails closed with no silent provider switch.
- Offline and no-cost/local provider gates remain green.
- Evidence clearly distinguishes recorded, local/free, and Bedrock runs.

### If verification is still pending

Leave CP12 in `WAITING_EXTERNAL`. Do not create unrelated paid usage, rotate policies randomly, or weaken security in an attempt to force activation. Continue polishing CP11 evidence and periodically retry a minimal playground/CLI probe.

---

## Checkpoint 13 — AWS Demo Stack

**Objective:** Deploy only the minimum AWS components required by the hackathon/submission after Bedrock is proven.

### Core deployment scope

1. Define infrastructure as code for the selected region.
2. Package the API/runtime for Lambda or another explicitly chosen compute target.
3. Expose only required endpoints through API Gateway.
4. Use DynamoDB with conditional writes for approval, confirmation, and ledger state.
5. Host the dashboard on the smallest suitable static-hosting path.
6. Use least-privilege execution roles and provider-specific permissions.
7. Add structured logs, correlation IDs, alarms, and cost controls.
8. Run the same acceptance journeys against the deployed endpoint.

### Optional integrations

EventBridge, Step Functions, SNS/SES, advanced observability, custom domains, and richer workflow orchestration are optional unless the submission rules explicitly require them. Simulated carrier and notification effects remain acceptable when disclosed.

### Exit gate

- Infrastructure can be created and removed reproducibly.
- No long-lived credentials are embedded in artifacts.
- Deployed benign, adversarial, approval, exact-once, restart, and tamper journeys pass.
- The cloud UI identifies region, runtime, model, policy, storage, and simulated effects accurately.
- Budget alarms and a teardown procedure are documented.

### Manual work

- Approve actual AWS spend before deployment.
- Review IAM roles and public endpoint exposure.
- Configure allowed origins and any hosted frontend settings.
- Run the final console smoke test and capture sanitized evidence.

---

## Checkpoint 14 — Final Evidence and Submission Freeze

**Objective:** Freeze one truthful, reproducible release and prepare the final submission.

### Release-path decision

- **Preferred:** CP12 and CP13 are green; submit the AWS-backed evidence bundle.
- **Contingency:** If AWS remains externally unavailable and rules permit local submission, submit the CP11 local candidate and explicitly state that Bedrock/AWS gates are pending.
- Never describe a local/OpenRouter/Ollama run as a Bedrock run.

### Required artifacts

- architecture diagram matching the implemented runtime;
- setup and runbook for the selected release path;
- exact test and evaluation evidence;
- provider/model disclosure;
- policy decision, approval, exact-once, and ledger trace examples;
- sanitized screenshots and demo video;
- limitations, simulated-effect disclosure, cost/region notes, and teardown steps;
- release manifest with commit SHA, dependency versions, model IDs, policy version, fixture ID, and evidence hashes;
- clean tag/commit authorized by the repository owner.

### Exit gate

- All claims can be traced to evidence.
- A clean-environment rehearsal succeeds twice.
- No secret, personal account identifier, stale claim, or broken link remains.
- The exact submitted commit and artifact hashes are recorded.
- No source changes occur after the final successful rehearsal except a full gate rerun.

---

## 4. Manual-action ledger

| When | Owner action | Required? | Why |
|---|---|---:|---|
| CP9 | Approve dependency download if prompted | Maybe | Install the pinned Strands SDK |
| CP10 | Generate and remove a temporary Bedrock API key | Complete | Selected paid Mantle proof |
| CP11 | Review/record sanitized demo evidence | Yes | Human quality and privacy check |
| CP12 | Complete AWS account verification | Yes for Bedrock | Account-level activation cannot be automated locally |
| CP12 | Create non-root AWS identity and budget alert | Yes | Safer runtime access and spend visibility |
| CP13 | Approve deployment spend and public exposure | Yes | External state and cost change |
| CP14 | Approve release commit/tag and submission | Yes | Irreversible release decision |

## 5. Permanent scope cuts

Unless a written submission requirement says otherwise, do not add:

- multi-order or multi-tenant production behavior;
- real carrier booking or real customer messaging;
- a general-purpose autonomous agent;
- direct model access to databases or cloud SDKs;
- policy authoring by the model;
- a custom authentication platform;
- production HA/DR or multi-region deployment;
- Kubernetes, EKS, or an unnecessary microservice split;
- a second LLM framework;
- hidden automatic failover between providers.

## 6. Current handoff

**Start now:** Checkpoint 11 — Local Prototype Hardening and Submission Candidate.

**Do not wait for:** native Nova access or AWS deployment.

**Do not do yet:** native Nova migration or AWS deployment.

**First command before implementation:** `./scripts/run_checkpoint_10_bedrock_mantle.sh --offline`

**Completed provider report:** [`CHECKPOINT_10_COMPLETION_REPORT.md`](CHECKPOINT_10_COMPLETION_REPORT.md)

**Current manual guide:** Checkpoint 11 instructions are the next planning task.

**Deferred AWS guide:** [`manual/CHECKPOINT_9_AWS_BEDROCK_SETUP.md`](manual/CHECKPOINT_9_AWS_BEDROCK_SETUP.md)

The immediate target is a rehearsed local submission candidate that preserves the completed Bedrock Mantle and offline evidence.
