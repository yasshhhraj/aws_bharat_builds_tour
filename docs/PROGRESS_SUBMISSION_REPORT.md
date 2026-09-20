# Manifest Prototype Progress Submission Report

**Updated:** 20 September 2026

**Current branch:** `checkpoint-11-hardening`

**Baseline revision:** `3cfd17c`

**Current checkpoint:** Checkpoint 11 — Local Prototype Hardening

## Executive summary

Manifest is a working governed logistics-agent prototype. Its local acceptance
path runs four bounded Strands roles through an offline recorded model. Every
protected tool attempt crosses the Manifest governor and an authoritative Cedar
4.12.0 policy sidecar before simulated effects execute. DynamoDB Local preserves
runs, approvals, effect receipts, and the SHA-256 event chain across service
reconstruction.

Separate Checkpoint 10 evidence proves the same provider-neutral runtime with
the paid Amazon Bedrock Mantle endpoint and `qwen.qwen3-coder-next`. OpenRouter
remains implemented but was not reliable across the complete multi-role gate.

The application itself is not deployed to AWS yet. AWS demo deployment is
Checkpoint 12. Native Nova parity is optional Checkpoint 13 and does not block
deployment through the already-proven Mantle route.

## Implemented capabilities

- Four sequential Strands roles with role-specific governed tools.
- Recorded, OpenRouter, Bedrock Mantle, and native-Bedrock provider seams.
- No automatic provider fallback.
- Cedar policy enforcement for ownership/mandate, numeric provenance,
  cold-chain selection, cumulative commitments, separation of duties, and PII
  boundaries.
- 50 kg to 500 kg guide-back using an authoritative numeric fact.
- Prepare-before-confirm commitment handling.
- Bound approval, rejection, expiry, replay, and concurrency behavior.
- Exact-once booking confirmation, cancellation, and simulated notification.
- Durable local DynamoDB repository with optimistic and transactional writes.
- Ordered SHA-256 event chain, verification, and first-bad-sequence detection.
- FastAPI endpoints and a no-build local operator dashboard.
- Explicit runtime/provider/model/policy/storage/ledger and simulation labels.
- Safe provider failure categories and inspectable failed traces.
- One-command local startup and one-command no-paid-call acceptance paths.

## Verified Checkpoint 11 automated evidence

```text
Python suite:                      206 passed, 13 skipped
DynamoDB Local contracts:         11 passed
Checkpoint 10 live Mantle gate:   3 passed in 55.83 seconds
Rust/Cedar tests:                 2 passed
Evaluation:                       22/22 passed
Functional digest:                sha256:99d44f22a833007bd2caa5121c2330b7222537633501590b1b43266c04b11120
Provider fallback:                disabled
```

Two consecutive canonical Checkpoint 11 gates passed with the same evaluation
digest. The implementation is complete, but browser screenshots, accessibility
review, the backup video, and a clean post-commit release manifest remain manual
closeout items. See `CHECKPOINT_11_COMPLETION_REPORT.md`.

## Real, simulated, and pending

| Area | Status | Honest claim |
|---|---|---|
| Agent runtime | Implemented | Real Strands loops with bounded role/tool access |
| Authorization | Implemented locally | Real Cedar sidecar; policy decisions are authoritative |
| Persistence | Implemented locally | DynamoDB Local; not managed AWS DynamoDB yet |
| Ledger | Implemented | Tamper-evident SHA-256 chain; not immutable |
| Bedrock inference | Proven separately | Paid Mantle evidence exists for synthetic fixtures |
| Logistics systems | Simulated | Inventory, vehicles, carriers, bookings, and messages are mocks |
| Human identity | Demo only | Shared local secret and synthetic approver label |
| Application deployment | Pending | No Lambda/API Gateway/static AWS hosting claim yet |
| Native Nova | Optional/pending | Account/model availability must not block Mantle deployment |

## Current verification commands

Focused no-network provider contract:

```bash
./scripts/run_checkpoint_10_bedrock_mantle.sh --offline
```

Complete local stack:

```bash
./scripts/start_checkpoint_11_local.sh
```

Canonical CP11 acceptance gate:

```bash
./scripts/run_checkpoint_11.sh
```

The acceptance gate explicitly selects the recorded model and cannot incur a
hosted-model charge.

## Remaining work

1. Complete two manual browser rehearsals and privacy/accessibility review.
2. Capture sanitized screenshots and a short backup video.
3. Commit the reviewed CP11 changes and regenerate a clean release manifest.
5. Deploy the minimal application stack during Checkpoint 12.
6. Add native Nova parity only if access becomes available or submission rules
   require it.
7. Freeze evidence, claims, artifact hashes, and the final release in CP14.

## Safe submission wording

> Manifest is a governed logistics-agent prototype whose bounded Strands roles
> propose actions through narrow tools. Cedar authorizes every protected tool
> attempt, DynamoDB Local preserves the approval and exact-once state, and a
> verifiable SHA-256 chain records the trajectory. The local deterministic demo
> uses a recorded model; separate evidence proves the same governed path with
> Amazon Bedrock Mantle. Logistics data and effects are synthetic and the
> application is not yet deployed to AWS.
