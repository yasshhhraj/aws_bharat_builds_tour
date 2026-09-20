# Checkpoint 10 Manual Setup — Amazon Bedrock Mantle

**Purpose:** Run one paid, governed Bedrock tool-use proof after OpenRouter proved unreliable

**Initial model:** `qwen.qwen3-coder-next`

**API:** OpenAI-compatible Chat Completions through `bedrock-mantle`

**Data rule:** Synthetic Manifest fixtures only

## 1. Before you begin

Bedrock Mantle is a real Amazon Bedrock endpoint, but inference is billable. The
script never invokes a model unless `MANIFEST_RUN_LIVE_BEDROCK_MANTLE=1` is set.
It stops at the first failure and never retries or changes providers silently.

Use the same AWS Region in which the model answered in the Bedrock playground.
The default below is `us-east-1`; change it if your working playground Region is
different. The zero-inference preflight will reject a model that is not listed in
that Region.

AWS recommends `bedrock-runtime` for new applications. Manifest is using Mantle
here because it is the endpoint currently working for this account and exposes
the OpenAI-compatible tool-calling API. This choice remains explicit in evidence.

## 2. Create a temporary development API key

1. Open the Amazon Bedrock console in the Region where the playground worked.
2. In the left navigation, select **API keys**.
3. Prefer **Short-term API keys** and choose **Generate short-term API key**.
4. The key lasts no longer than 12 hours and is restricted to its creation Region.
5. Copy it once. Do not paste it into chat, source files, `.env`, screenshots,
   shell history, or documentation.

For exploration only, AWS also offers expiring long-term keys. Do not create one
unless the short-term option is unavailable for your account.

## 3. Load the key without shell-history exposure

Install the OpenAI-compatible Strands adapter once:

```zsh
.venv/bin/pip install -e '.[dev,bedrock_mantle]'
```

From `/home/yashraj/p0/project`, use zsh's hidden input:

```zsh
read -s "BEDROCK_MANTLE_API_KEY?Paste the temporary Bedrock API key: "
echo
export BEDROCK_MANTLE_API_KEY
```

Confirm presence without printing the value:

```zsh
if [[ -n "${BEDROCK_MANTLE_API_KEY:-}" ]]; then
  echo "Bedrock Mantle key is set."
else
  echo "Bedrock Mantle key is missing."
fi
```

## 4. Select the explicit provider, Region, and model

```zsh
export MANIFEST_AGENT_RUNTIME=strands
export MANIFEST_MODEL_PROVIDER=bedrock_mantle
export MANIFEST_MODEL_ID=qwen.qwen3-coder-next
export MANIFEST_BEDROCK_REGION=us-east-1
export MANIFEST_AGENT_MAX_TURNS=8
export MANIFEST_AGENT_TIMEOUT_SECONDS=60
export MANIFEST_MODEL_MAX_OUTPUT_TOKENS=1024
```

If your working playground is not N. Virginia, replace `us-east-1` with that
exact Region code before continuing.

## 5. Run the zero-inference preflight

This lists models through `GET /v1/models`; it does not invoke a model:

```zsh
.venv/bin/python scripts/check_bedrock_mantle_ready.py
```

Continue only when it reports `status: ready` and
`configured_model_available: true`. For HTTP 401/403, check the key's Region,
expiry, and permissions; do not use root credentials as a workaround.

## 6. Run exactly one paid Inventory probe

Review the current model price in the Bedrock console, then explicitly opt in:

```zsh
export MANIFEST_RUN_LIVE_BEDROCK_MANTLE=1
./scripts/run_checkpoint_10_bedrock_mantle.sh --probe
```

This runs only `get_order` and `check_inventory`. It must pass with Cedar active
and a valid ledger before a full journey is allowed.

## 7. Run the full paid gate

Only after the probe passes:

```zsh
./scripts/run_checkpoint_10_bedrock_mantle.sh --live
```

The gate stops after its first failure. It writes sanitized evidence under
`docs/results/checkpoint-10-bedrock-mantle-*`. It never runs the 22-case
evaluation against the paid provider.

## 8. Cleanup

```zsh
unset BEDROCK_MANTLE_API_KEY
unset MANIFEST_RUN_LIVE_BEDROCK_MANTLE
```

Short-term keys expire automatically. Deactivate or delete a long-term
development key in **Bedrock → API keys** after testing.

## Official AWS references

- <https://docs.aws.amazon.com/bedrock/latest/userguide/endpoints.html>
- <https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys.html>
- <https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-qwen-qwen3-coder-next.html>
- <https://docs.aws.amazon.com/bedrock/latest/userguide/inference-chat-completions.html>
