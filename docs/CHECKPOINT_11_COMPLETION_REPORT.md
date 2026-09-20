# Checkpoint 11 Completion Report

**Status:** Implementation complete; manual evidence pending  
**Branch:** `checkpoint-11-hardening`  
**Baseline commit:** `3cfd17c`

## Outcome

Checkpoint 11 now provides a reproducible local submission candidate with a
one-command launcher and a no-paid-inference acceptance gate. The recorded
Strands model remains deterministic, Cedar remains authoritative, DynamoDB
Local preserves state, and provider failures fail closed with inspectable
trace-linked errors.

## Automated evidence

Two consecutive canonical gate executions passed before this report was
prepared:

| Gate | Result |
|---|---|
| Python suite | 206 passed, 13 skipped |
| DynamoDB Local contracts | 11 passed |
| Rust/Cedar suite | 2 passed |
| Scripted rehearsals per gate | 2 passed |
| Evaluation | 22/22 passed |
| Benign pass rate | 100% |
| Attack detection rate | 100% |
| Functional digest parity | Exact match with Checkpoint 9 |
| Submission hygiene | Passed |

Functional digest:
`sha256:99d44f22a833007bd2caa5121c2330b7222537633501590b1b43266c04b11120`

Evidence:

- [`results/checkpoint-11-local-evaluation.json`](results/checkpoint-11-local-evaluation.json)
- [`results/checkpoint-11-local-evaluation.md`](results/checkpoint-11-local-evaluation.md)
- [`results/checkpoint-11-rehearsal-1.md`](results/checkpoint-11-rehearsal-1.md)
- [`results/checkpoint-11-rehearsal-2.md`](results/checkpoint-11-rehearsal-2.md)
- [`results/checkpoint-11-browser-smoke.md`](results/checkpoint-11-browser-smoke.md)
- [`releases/checkpoint-11-local-candidate.json`](releases/checkpoint-11-local-candidate.json)

## Safety and claim review

- Hosted-provider credentials are not required by the canonical gate.
- Provider fallback is disabled.
- Protected effects still cross the governor and Cedar boundary.
- Error responses expose a safe category and trace ID, not provider secrets.
- Dashboard labels distinguish recorded inference, local infrastructure, and
  simulated logistics effects.
- Release evidence honestly records the dirty source tree until the owner
  commits the checkpoint and regenerates it.

## Remaining owner actions

Checkpoint 11 must not be marked fully closed until these manual actions are
complete:

1. Follow [`manual/CHECKPOINT_11_LOCAL_DEMO.md`](manual/CHECKPOINT_11_LOCAL_DEMO.md)
   for two browser and keyboard rehearsals.
2. Capture sanitized screenshots and review them for credentials, account IDs,
   personal paths, and misleading cloud claims.
3. Record the short backup demo video.
4. Commit the reviewed checkpoint, rerun `./scripts/run_checkpoint_11.sh`, and
   confirm the regenerated release manifest has `source.dirty: false`.
5. Mark Checkpoint 11 complete, then begin the separately authorized and
   billable AWS deployment in Checkpoint 12.

