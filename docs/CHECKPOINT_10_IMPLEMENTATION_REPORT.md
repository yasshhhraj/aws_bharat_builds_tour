# Checkpoint 10 Implementation Report — Hosted Provider Portability

**Status:** COMPLETE — Bedrock Mantle full live gate passed

**Date:** 20 September 2026

**Source revision:** `c7731e1` plus the current uncommitted Checkpoint 8–10 working tree

## Outcome

Manifest now selects `recorded`, `openrouter`, `bedrock_mantle`, or `bedrock` models behind one
provider-neutral `StrandsRuntime`. OpenRouter uses Strands' OpenAI-compatible
model adapter and a fixed `https://openrouter.ai/api/v1` endpoint. Bedrock Mantle
uses a region-derived `bedrock-mantle.{region}.api.aws/v1` endpoint and a
dedicated bearer key. Native Bedrock remains construction-tested separately.

The recorded provider remains the deterministic default. There is no
application-level fallback: a hosted-provider failure closes the invocation and
fails the current trajectory.

## Implemented controls

- explicit provider/model/turn/timeout/output-limit validation;
- secrets read only from the process environment and excluded from diagnostics;
- fresh model, agent, and governed context for every role invocation;
- zero provider SDK retries and bounded model calls;
- provider-neutral completion predicates that reject prose-only responses;
- late-callback rejection after timeout or failure;
- sanitized authentication, billing, missing-model, rate-limit, timeout, and
  availability errors;
- provider, requested model, router/fixed route, limits, cycles, and nullable
  usage fields in runtime diagnostics/evidence;
- an opt-in live Inventory probe plus benign and adversarial live journeys;
- a key-metadata preflight that performs no inference; and
- a construction-only Bedrock branch using the normal AWS credential chain.

## Verification completed

```text
Checkpoint 10 no-network suite: 201 passed, 15 skipped
Hosted-provider tests:           skipped unless explicitly enabled
OpenAI-compatible client:        openai 2.54.0
Strands:                         strands-agents 1.56.0
Checkpoint 9 live-Cedar suite:   200 passed, 13 skipped
Storage/restart/concurrency:      11 passed
Rust/Cedar:                       2 passed
Evaluation:                       22/22 passed
Functional digest:               sha256:99d44f22a833007bd2caa5121c2330b7222537633501590b1b43266c04b11120
```

The no-network suite includes provider construction, configuration and error
mapping, fake-hosted execution, prose-only rejection, and proof that a delayed
tool callback cannot execute after timeout.

## Live verification

The Bedrock Mantle Inventory probe and full gate passed on 20 September 2026 with
`qwen.qwen3-coder-next`, authoritative Cedar decisions for `get_order` and
`check_inventory`, and a valid ledger. Sanitized evidence is stored in
`results/checkpoint-10-bedrock-mantle-inventory-probe.json` and `.md`.

```text
Inventory probe:       passed
Benign hero journey:   completed with valid ledger
Adversarial journey:   pending approval after Cedar spend escalation
Live tests:             3 passed in 55.83 seconds
Provider fallback:      disabled
```

OpenRouter completed isolated probes but was not reliable across the full
multi-role gate. Bedrock Mantle is the selected submission provider path.
Checkpoint 10 is complete; remove the temporary key and review AWS billing
before beginning Checkpoint 11.
