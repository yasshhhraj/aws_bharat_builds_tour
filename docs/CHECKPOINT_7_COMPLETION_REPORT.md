# Checkpoint 7 Completion Report — Cedar Authorization Parity

**Verified:** 19 September 2026  
**Status:** Complete locally  
**Policy engine:** Cedar 4.12.0, local loopback sidecar  
**Policy version:** `demo-v1`

## Outcome

Cedar is now the authoritative policy engine whenever
`MANIFEST_POLICY_ENGINE=cedar`. The Python implementation remains available as
an explicit reference/offline mode; there is no automatic fallback. A missing,
unhealthy, incompatible, or hash-mismatched Cedar service prevents startup.

The implementation includes a typed Cedar schema, a versioned six-family policy
bundle, stable policy metadata, a bounded Python adapter, and a Rust PDP built on
the official `cedar-policy` crate. Health, decisions, ledger events, evaluation
evidence, and release evidence disclose the active engine and bundle identity.

## Verified results

The full gate completed successfully:

```text
./scripts/run_checkpoint_7.sh
Rust build/test:       passed
Python tests:          136 passed with live Cedar enabled
Rust tests:            2 passed
Evaluation:            22/22 passed
Attack detection:      10/10
Benign/boundary:       12/12
False positives:       0/12
Guide-back:            2/2
Functional parity:     exact match with Checkpoint 6
Functional digest:     sha256:99d44f22a833007bd2caa5121c2330b7222537633501590b1b43266c04b11120
```

The gate also completed benign enforce, adversarial enforce with bound approval,
and adversarial shadow journeys while Cedar was active. The approved financial
commitment was re-authorized and confirmed exactly once.

## Bundle identity

```text
Cedar runtime: 4.12.0
Bundle: sha256:28dbf5808a3e1f49f9ebf9653c4a90f7988a32b96459a9642f67e0d05e975667
Schema: sha256:53da87760937b3d7b3ca99e2cc62f0a1a0b0ed32197239526ed98ec40641f322
```

Generated evidence:

- [`results/checkpoint-7-cedar-evaluation.md`](results/checkpoint-7-cedar-evaluation.md)
- [`results/checkpoint-7-cedar-evaluation.json`](results/checkpoint-7-cedar-evaluation.json)
- [`releases/checkpoint-7-cedar-local.json`](releases/checkpoint-7-cedar-local.json)

## Security and compatibility properties

- The sidecar binds only to loopback, caps request/response bodies, and validates
  policies and requests against the schema.
- The adapter sends an explicit allowlist of typed fields, not trajectory dumps,
  raw PII, approval comments, credentials, or secret values.
- Unknown policy IDs, diagnostics, transport errors, correlation errors, version
  mismatches, and bundle mismatches fail closed.
- Existing API paths and shadow/enforce, guide-back, approval, exact-once,
  redaction, ledger, dashboard, and evaluation contracts are preserved.
- Checkpoint 6 evidence was not overwritten; Checkpoint 7 uses separate files.

## Deliberate boundary

Cedar evaluates typed authorization facts. Python performs deterministic input
normalization, cryptographic fact-hash verification, policy-ID translation, and
human-facing guidance construction because those operations are outside Cedar's
authorization expression role. Cedar still makes the authoritative allow/deny
decision for the configured Checkpoint 7 runtime.

Storage remains in-memory, agents remain deterministic Python roles, and the
deployment remains local. Those are explicitly deferred to Checkpoints 8–10.
