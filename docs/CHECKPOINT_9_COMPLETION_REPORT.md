# Checkpoint 9 Completion Report — Offline Strands Runtime

**Status:** Complete  
**Date:** 20 September 2026  
**Branch:** `checkpoint-9-offline-strands`  
**Baseline commit:** `c7731e1a0ca370cb78365dee7c65f6bf1973756a`

## Delivered

- `strands-agents==1.56.0` pinned as the only new runtime dependency; the broad
  `strands-agents-tools` package is intentionally not installed.
- Explicit `legacy/deterministic` and `strands/recorded` runtime combinations,
  with bounded turns and timeout validation and no automatic provider fallback.
- A project-owned role-runtime seam and fresh Strands `Agent` per role invocation.
- `RecordedManifestModel`, implementing the current Strands model contract and
  driving deterministic offline tool calls through the real agent loop.
- Exact role tool allow-lists with model-controlled arguments separated from
  role, trace, governance mode, idempotency, approval, and action-hash authority.
- A single governed invocation bridge that calls `ManifestGovernor.execute_tool`
  and a shared result projector used by both legacy and Strands roles.
- Inventory, Dispatch, Carrier, and Customer Communications adapters, including
  guide-back, approval pause/resume, rejection, expiry, and fail-closed limits.
- Runtime/provider/model/limit disclosure in health output, run-start events,
  evaluation evidence, and the release manifest.
- A reproducible `scripts/run_checkpoint_9_offline.sh` acceptance gate.

## Parity and safety proof

- Four protected-outcome parity journeys compare legacy and Strands execution:
  benign enforce, adversarial enforce/approve, adversarial enforce/reject, and
  adversarial shadow.
- The comparison covers final status and stage, selected resources, commitment
  totals, notification/confirmation/cancellation effects, and the ordered Cedar
  decision projection.
- Tool schemas do not expose role, trace ID, policy mode, action hashes,
  idempotency keys, or cancellation authority to the model.
- Effectful calls remain sequential, pass through the governor, retain the
  existing approval binding, and preserve exact-once behavior.
- Turn exhaustion fails the run before an effectful stage; there is no silent
  fallback to the legacy runtime or a hosted model.

## Final verification

The full Checkpoint 9 gate passed **twice consecutively**.

- Live-Cedar Python gate on each pass: `181 passed, 10 skipped`.
- Shared memory/DynamoDB contract and durable integration gate on each pass:
  `11 passed`.
- Cedar sidecar on each pass: 2 Rust tests passed; runtime `4.12.0`; bundle hash
  `sha256:28dbf5808a3e1f49f9ebf9653c4a90f7988a32b96459a9642f67e0d05e975667`.
- Offline Strands hero paths completed for benign enforce, adversarial
  enforce/approve, adversarial enforce/reject, and adversarial shadow.
- Evaluation: 22/22 cases passed; 10/10 attacks detected; 12/12 benign cases
  passed; 2/2 guide-back cases succeeded; false positives were 0/12.
- Functional digest matched Checkpoint 8 on both passes:
  `sha256:99d44f22a833007bd2caa5121c2330b7222537633501590b1b43266c04b11120`.
- The ordinary default-runtime regression also passed: `179 passed, 12 skipped`.
- The generated release manifest records Python `3.14.6`, Strands `1.56.0`,
  Cedar and storage identities, 191 collected tests, and the dirty branch/source
  state used for this implementation.

## Evidence

- Evaluation JSON: `docs/results/checkpoint-9-offline-strands-evaluation.json`
- Evaluation report: `docs/results/checkpoint-9-offline-strands-evaluation.md`
- Release manifest: `docs/releases/checkpoint-9-offline-strands.json`
- Gate command: `./scripts/run_checkpoint_9_offline.sh`

## Manual setup and cloud status

No AWS account, Bedrock access, hosted-model credential, or provider API key was
used. Docker is required only for the inherited DynamoDB Local durability gate;
the AWS-shaped values used there are fixed local dummy values, not credentials.
The runtime itself is offline after the Strands package has been installed.

DynamoDB Local remains running for development. Each gate stopped the Cedar
sidecar process it started. Bedrock work remains deferred to Checkpoint 12 after
AWS account verification.

## Handoff

Checkpoint 10 can now add one explicitly selected local/no-cost live model behind
the same runtime and governed tool contracts. It must keep recorded mode as the
deterministic acceptance oracle and must not weaken Cedar, approval, persistence,
or ledger behavior.

The selected route is OpenRouter. See
[`CHECKPOINT_10_IMPLEMENTATION_PLAN.md`](CHECKPOINT_10_IMPLEMENTATION_PLAN.md) and
[`manual/CHECKPOINT_10_OPENROUTER_SETUP.md`](manual/CHECKPOINT_10_OPENROUTER_SETUP.md).
