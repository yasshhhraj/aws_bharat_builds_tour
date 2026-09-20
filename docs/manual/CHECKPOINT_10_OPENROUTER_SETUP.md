# Checkpoint 10 Manual Setup — OpenRouter Free Provider

**Audience:** First-time OpenRouter user

**Purpose:** Create a limited development API key and run Manifest's staged live-provider gate

**Selected initial model:** `openrouter/free`

**Project data rule:** Synthetic `ORD-8842` fixture only

**Estimated account setup time:** 10–20 minutes

**Implementation plan:** [`../CHECKPOINT_10_IMPLEMENTATION_PLAN.md`](../CHECKPOINT_10_IMPLEMENTATION_PLAN.md)

## 1. What this setup does

OpenRouter provides one API endpoint for models hosted by multiple providers. Manifest will use it through Strands' built-in `OpenAIModel` integration.

You will:

1. create or sign in to an OpenRouter account;
2. review its privacy settings;
3. create one API key for this prototype;
4. load that key into the current terminal without saving it in the repository;
5. verify the key;
6. run the implemented staged tool-use test; and
7. revoke or deliberately retain the key when testing is finished.

You will not:

- purchase credits for this checkpoint;
- select a paid model;
- give the API key to Codex, another chat, or a repository file;
- send real orders, customer data, addresses, emails, phone numbers, or credentials;
- create an OpenRouter Agent SDK application; or
- configure AWS.

## 2. Cost and availability reality

As checked on **20 September 2026**:

- OpenRouter lists a free plan with **50 requests per day**;
- `openrouter/free` is priced at zero for prompt and completion tokens;
- the router chooses from currently available free models and filters for requested features such as tool calling; and
- the model selected by the router can change.

These limits and available models can change. Confirm them before each live test:

- Pricing: <https://openrouter.ai/pricing>
- Free Models Router: <https://openrouter.ai/openrouter/free>

If the site asks you to purchase credits or add a paid method before allowing the free route, stop and review the current terms. The Checkpoint 10 plan does not authorize purchasing anything.

One Strands journey uses multiple API requests because the model is called again after each tool result. Do not run the full 22-case evaluation against OpenRouter.

## 3. Security rules

1. Never paste the OpenRouter key into source code, `.env.example`, README files, documentation, screenshots, issues, or chat.
2. Do not run the shell with command tracing such as `set -x` while the key is present.
3. Do not print the key with `echo`, `env`, `printenv`, or debugging output.
4. Use a dedicated key named for this prototype instead of reusing a personal production key.
5. Use only the synthetic fixture data already in this repository.
6. Treat free-router prompts and outputs as data sent to external providers with provider-dependent retention/training policies.
7. Revoke the key immediately if it appears anywhere it should not.

The repository ignores `.env`, but this guide intentionally keeps the key out of `.env` as an additional safety measure.

## 4. Step A — Create or sign in to OpenRouter

1. Open <https://openrouter.ai/>.
2. Select **Sign Up** or **Sign In**.
3. Complete the offered account-verification steps.
4. Confirm that you can reach the OpenRouter dashboard.
5. Do not add credits or a payment method for this checkpoint.

The exact sign-in buttons may change. Use only the official `openrouter.ai` domain.

## 5. Step B — Review privacy settings

OpenRouter may route a request to another model provider. Different providers can have different logging, retention, and training practices.

1. Open your OpenRouter settings.
2. Find **Privacy**, **Data**, or **Guardrails** settings.
3. Review whether provider data collection is allowed.
4. If you enable zero-data-retention or deny data collection, understand that this may reduce the set of eligible free models.
5. Regardless of the setting, send only Manifest's synthetic data.

Provider information is available at <https://openrouter.ai/providers>. Do not treat a free routed model as appropriate for real logistics or customer data.

## 6. Step C — Create a dedicated API key

1. Open <https://openrouter.ai/settings/keys>.
2. Select **Create Key**.
3. Use a recognizable name such as:

   ```text
   manifest-checkpoint-10-local
   ```

4. If an expiration option is available, choose a short development-appropriate expiration.
5. If a paid spending limit is offered, do not use it as permission to select paid models. This checkpoint uses only a free model/router.
6. Create the key.
7. Copy it once into your password manager or directly into the hidden terminal prompt in the next step.

OpenRouter API keys normally begin with a recognizable prefix, but do not depend on the prefix as authentication proof. The API verification call below is the proof.

Do not screenshot the key-creation result.

## 7. Step D — Load the key safely in the current zsh terminal

From the repository directory:

```bash
cd /home/yashraj/p0/project
```

Use zsh's hidden-input prompt:

```zsh
read -s "OPENROUTER_API_KEY?Paste OpenRouter API key: "
echo
export OPENROUTER_API_KEY
```

The pasted characters should not appear on the screen.

Verify only that the variable is present, without printing its value:

```zsh
if [[ -n "${OPENROUTER_API_KEY:-}" ]]; then
  echo "OpenRouter key is set in this shell."
else
  echo "OpenRouter key is missing."
fi
```

This environment variable exists only in this shell and child processes. Opening a new terminal requires loading it again.

Do not use:

```bash
export OPENROUTER_API_KEY="the-real-key"
```

because the literal value may be retained in shell history.

## 8. Step E — Verify the key without making a model request

Run the official current-key endpoint:

```zsh
curl --fail-with-body --silent --show-error \
  https://openrouter.ai/api/v1/key \
  --header "Authorization: Bearer ${OPENROUTER_API_KEY}"
```

Expected result:

- HTTP 200;
- a JSON object with key metadata; and
- no model-inference request consumed.

The response may contain account/key metadata such as a creator identifier, usage, limits, or expiry. Do not paste or screenshot the complete response. Record only:

```text
OpenRouter key verification: HTTP 200
```

If you receive HTTP 401, revoke the key if necessary, create a new one, and load it again. Do not send the key to anyone for troubleshooting.

Official endpoint documentation: <https://openrouter.ai/docs/api/api-reference/api-keys/get-current-key>

## 9. Step F — Install the OpenRouter provider dependency

From the project root:

```bash
.venv/bin/pip install -e '.[dev,openrouter]'
```

Verify that Strands' OpenAI-compatible provider imports:

```bash
.venv/bin/python -c 'from strands.models.openai import OpenAIModel; print("Strands OpenRouter dependency is ready.")'
```

This installs the OpenAI-compatible client library used by Strands. Do not install the separate OpenRouter Agent SDK; Manifest keeps Strands as its only agent framework.

If installation fails because network access is restricted, approve only the scoped dependency-download request. Do not use `sudo` and do not install into system Python.

## 10. Step G — Select OpenRouter runtime configuration

Set:

```zsh
export MANIFEST_AGENT_RUNTIME=strands
export MANIFEST_MODEL_PROVIDER=openrouter
export MANIFEST_MODEL_ID=openrouter/free
export MANIFEST_AGENT_MAX_TURNS=8
export MANIFEST_AGENT_TIMEOUT_SECONDS=30
export MANIFEST_MODEL_MAX_OUTPUT_TOKENS=1024
```

Why the live timeout is initially 30 seconds:

- free providers can have queueing latency;
- 30 seconds remains within the project's maximum bound; and
- the runtime still cancels and fails closed when the bound is exceeded.

This limit applies to the complete multi-call role, not to each individual
provider request. If a fixed free model passes once but later times out while
queueing, increase it to the supported maximum before one deliberate retry:

```zsh
export MANIFEST_AGENT_TIMEOUT_SECONDS=60
```

Do not increase the code limit or repeatedly retry a slow/unavailable model.
The live gate stops at its first failure to conserve the free request allowance.

Do not change policy or governance settings to make a model pass. The recommended live gate uses authoritative Cedar.

Confirm the safe, non-secret variables:

```zsh
printf 'runtime=%s\nprovider=%s\nmodel=%s\n' \
  "${MANIFEST_AGENT_RUNTIME}" \
  "${MANIFEST_MODEL_PROVIDER}" \
  "${MANIFEST_MODEL_ID}"
```

Expected:

```text
runtime=strands
provider=openrouter
model=openrouter/free
```

## 11. Step H — Run the staged readiness checks

The following commands are implemented Checkpoint 10 deliverables.

### 11.1 Configuration and key check

```zsh
.venv/bin/python scripts/check_openrouter_ready.py
```

This check must:

- validate configuration;
- confirm the optional provider dependency;
- call only the current-key endpoint;
- never display the key; and
- make no model-inference request.

### 11.2 Read-only Inventory probe

```zsh
export MANIFEST_RUN_LIVE_OPENROUTER=1
./scripts/run_checkpoint_10_openrouter.sh --probe
```

The probe should expose only the Inventory role's `get_order` and `check_inventory` tools. It passes only if the live model actually calls the governed tools and the inventory fact is established.

Expected evidence:

```text
provider: openrouter
requested model: openrouter/free
route kind: router
role: inventory
governed tool calls: get_order, check_inventory
result: passed
```

If the model replies with prose but does not call the tools, the probe must fail. Do not weaken the completion check.

## 12. Step I — Identify and optionally pin the routed free model

After a successful probe:

1. Open <https://openrouter.ai/activity>.
2. Find the request by its time and model route.
3. Record the resolved model name in private checkpoint notes.
4. Check that model's current OpenRouter page for tool-calling support and a free variant.
5. If an explicit free slug is available and the probe is reliable, set it for the hero run:

   ```zsh
   export MANIFEST_MODEL_ID='<provider>/<model>:free'
   ```

6. Rerun only the read-only probe before the full journey.

Do not copy the placeholder `<provider>/<model>:free` literally.

Why pin when possible:

- `openrouter/free` can choose different models across requests;
- a fixed free slug gives more repeatable tool behavior; and
- the later Bedrock comparison is clearer.

If no suitable explicit free model is available, keep `openrouter/free` and disclose that the run used a changing router. Never claim it used a fixed model.

## 13. Step J — Run the live Checkpoint 10 gate

Only proceed after the read-only probe passes.

```zsh
export MANIFEST_RUN_LIVE_OPENROUTER=1
./scripts/run_checkpoint_10_openrouter.sh --live
```

The live phase should run in this order:

1. configuration/key preflight;
2. read-only Inventory probe;
3. one benign governed hero journey;
4. one adversarial enforce journey;
5. sanitized evidence generation.

The script must not run the 22-case evaluation live. It should run full evaluation only with the recorded offline provider.

Expected high-level result:

```text
Offline provider-contract gate: PASS
OpenRouter read-only probe:     PASS
OpenRouter benign journey:      PASS
OpenRouter adversarial gate:    PASS
Cedar authoritative:            YES
Application provider fallback:  NONE
Secret scan:                    PASS
```

Stop after the first failure. Repeated attempts can exhaust the free daily request allowance and make diagnosis harder.

## 14. What to inspect after the run

In Manifest evidence, confirm:

- `runtime_mode` is `strands`;
- `model_provider` is `openrouter`;
- `requested_model_id` matches the configured router/model;
- router/fixed status is truthful;
- Cedar is the active policy engine;
- every tool decision has a traceable policy outcome;
- no key or authorization header appears;
- failed provider calls do not silently switch to recorded mode;
- exact-once and ledger verification remain valid.

In OpenRouter Activity, confirm:

- the request used the expected router/model;
- the request count is within the free allowance;
- the resolved provider/model is recorded for private evidence if shown; and
- no unexpected paid request appears.

Do not include screenshots containing account IDs, emails, full activity payloads, or API-key details in the submission.

## 15. Troubleshooting

### `OPENROUTER_API_KEY is missing`

The key was not loaded in this shell.

```zsh
read -s "OPENROUTER_API_KEY?Paste OpenRouter API key: "
echo
export OPENROUTER_API_KEY
```

### `ModuleNotFoundError: No module named 'openai'`

Install the project optional dependency after the Checkpoint 10 `pyproject.toml` change:

```bash
.venv/bin/pip install -e '.[dev,openrouter]'
```

### HTTP 401 or 403

- Verify the key using `GET /api/v1/key`.
- Confirm no leading/trailing whitespace was pasted.
- Confirm the key was not revoked or expired.
- Create a new dedicated key if needed.

Do not print the key.

### HTTP 402 or a paid-model error

- Confirm `MANIFEST_MODEL_ID=openrouter/free` or an explicit model ending in `:free`.
- Do not add credits merely to make the checkpoint pass.
- Check the model's current pricing page.

### HTTP 404 or model unavailable

The explicit free model may have been removed or renamed.

1. Return to `openrouter/free`.
2. Run only the read-only probe as a new trace.
3. Select a currently available explicit free model if appropriate.

### HTTP 429 / rate limited

- Stop the live gate.
- Do not loop or enable automatic retries.
- Check OpenRouter Activity and current pricing/limits.
- Wait for the documented reset or continue only with recorded offline mode.

### Model returns text but makes no tool call

- Confirm the request advertises tools.
- Confirm the selected model/router currently supports tool calling.
- Try one new trace with a different explicit free tool-capable model.
- Keep the completion assertion fail-closed.

Do not accept prose as proof of tool execution.

### Wrong or malformed tool arguments

The governed wrapper should reject the call without an unauthorized effect. Inspect the sanitized error category and choose another tool-capable model if the behavior repeats. Do not loosen schemas or allow the model to provide role, policy, approval, trace, action-hash, or idempotency fields.

### Timeout or provider 5xx error

- Confirm the run is marked failed and the invocation context is closed.
- Confirm no late tool call executes.
- Check <https://status.openrouter.ai/>.
- Begin a new trace only after the service is healthy.

Never continue the same trace with recorded mode or Bedrock.

### Privacy settings leave no eligible model

Strict privacy/ZDR settings can reduce the available free-provider pool. Keep using synthetic data, review the current provider choices, and decide whether the privacy setting or the live free-provider requirement should take priority. Do not silently relax privacy settings.

## 16. End-of-session cleanup

Remove the key from the current shell:

```zsh
unset OPENROUTER_API_KEY
```

Confirm only that it is absent:

```zsh
if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
  echo "OpenRouter key removed from this shell."
fi
```

Then choose one:

- keep the dedicated key temporarily for continued Checkpoint 10 work; or
- revoke/delete it at <https://openrouter.ai/settings/keys>.

Revoke it immediately if:

- it was pasted into chat or an issue;
- it appeared in a screenshot or recording;
- it was committed or written into a tracked file;
- it was printed in logs; or
- you cannot account for its usage.

After revocation, create a new key only when another live test is necessary.

## 17. Later switch to Bedrock

The Checkpoint 10 implementation deliberately keeps provider selection behind one model factory. After AWS verification succeeds, the operational switch should require only:

```zsh
unset OPENROUTER_API_KEY
export MANIFEST_AGENT_RUNTIME=strands
export MANIFEST_MODEL_PROVIDER=bedrock
export MANIFEST_MODEL_ID=us.amazon.nova-2-lite-v1:0
export MANIFEST_BEDROCK_REGION=us-east-1
```

The agents, prompts, tools, Cedar policies, approval lifecycle, storage, and ledger must remain unchanged. Bedrock credentials will come from the standard AWS credential chain, not from this OpenRouter setup.

Do not attempt the Bedrock live gate until AWS account verification is complete.

## 18. Owner checklist

- [ ] Signed in through the official OpenRouter domain.
- [ ] Reviewed privacy/provider-routing implications.
- [ ] Created a dedicated `manifest-checkpoint-10-local` key.
- [ ] Did not purchase credits or select a paid model.
- [ ] Loaded the key through hidden terminal input.
- [ ] Verified the key with `GET /api/v1/key`.
- [ ] Installed only the project's OpenRouter optional dependency.
- [ ] Began with `openrouter/free` and the read-only probe.
- [ ] Recorded/disclosed router or resolved fixed-model identity honestly.
- [ ] Ran no more live journeys than the request budget allows.
- [ ] Reviewed evidence for secrets and personal identifiers.
- [ ] Unset and either retained deliberately or revoked the key.

## 19. Official references

- Strands OpenRouter integration: <https://strandsagents.com/docs/integrations/model-providers/openrouter/>
- OpenRouter quickstart: <https://openrouter.ai/docs/quickstart>
- OpenRouter API keys: <https://openrouter.ai/settings/keys>
- Current-key endpoint: <https://openrouter.ai/docs/api/api-reference/api-keys/get-current-key>
- Free Models Router: <https://openrouter.ai/openrouter/free>
- Pricing and current limits: <https://openrouter.ai/pricing>
- Provider data practices: <https://openrouter.ai/providers>
