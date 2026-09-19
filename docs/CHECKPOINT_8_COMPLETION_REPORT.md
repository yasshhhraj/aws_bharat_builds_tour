# Checkpoint 8 Completion Report — Durable Storage and DynamoDB Parity

**Status:** Complete  
**Date:** 19 September 2026  
**Baseline:** `e8e8ab4` (Checkpoint 7)

## Delivered

- Database-independent `TraceRepository` with detached snapshots and optimistic revisions.
- Explicit versioned JSON codecs for state, events, decisions, approvals, heads,
  replay records, and effect receipts; no pickle or implicit object serialization.
- Memory and DynamoDB adapters implementing the same run/approval/replay contract.
- Strong DynamoDB reads and transactional event, ledger-head, state, and replay writes.
- Durable approval pointers and conditional versions, write-effect receipts,
  replay records, trace isolation, and namespace-scoped reset.
- Environment-driven, fail-closed backend selection with memory as the explicit
  zero-service fallback.
- Idempotent table setup and Checkpoint 8 gate scripts.
- DynamoDB Local 2.5.4 pinned to
  `sha256:cf8cebd061f988628c02daff10fdb950a54478feff9c52f6ddf84710fe3c3906`.

## Final verification

- Full live-Cedar Python gate: `164 passed, 9 skipped`.
- Shared memory/DynamoDB contract and durable integration gate: `11 passed`.
- Cedar sidecar: 2 Rust tests passed; runtime 4.12.0; bundle hash
  `sha256:28dbf5808a3e1f49f9ebf9653c4a90f7988a32b96459a9642f67e0d05e975667`.
- Nine DynamoDB-specific tests covered reconstruction, approval resume/replay,
  stale-write rejection, distributed approval race, event/effect replay, tamper
  detection, trace isolation, reject recovery, and namespace-safe reset.
- A benign database journey completed with 37 events and a valid ledger.
- An approval journey reconstructed and replayed across three fresh service instances.
- A pending trace survived a full DynamoDB Local container restart, was approved
  by a fresh application process, completed its original trace, and verified cleanly.
- All three Cedar+DynamoDB hero journeys completed.
- Evaluation: 22/22 cases passed; 10/10 attacks detected; 12/12 benign cases
  passed; functional digest remained
  `sha256:99d44f22a833007bd2caa5121c2330b7222537633501590b1b43266c04b11120`.
- Separate evaluation and release evidence were generated under `docs/results`
  and `docs/releases`.

## Manual setup required

No AWS account, AWS CLI, console table creation, real credentials, or manual image
pull is required. The only prerequisite is a running Docker daemon. Docker was
already available on this machine, so no manual owner action was needed. The
database binds to loopback port 18000 because port 8000 was already occupied.

## Gate command

`./scripts/run_checkpoint_8.sh` completed successfully. DynamoDB Local remains
running for development; the gate stopped the Cedar process it started.
