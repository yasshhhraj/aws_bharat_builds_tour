# Manifest

Manifest is a learning-focused prototype that governs autonomous logistics
agent actions before they create physical, financial, or disclosure effects.

## Current status

**Checkpoint 8 is implemented locally.** One deterministic shipment runs through four
plain-Python agent roles in either shadow or enforce mode. Every registered tool
attempt receives an authoritative Cedar policy decision before its mock effect executes, and a
bound human approval can resume or cancel a paused commitment. Every retained
trace event is now part of an ordered SHA-256 hash chain that can be verified
through the API. A no-build browser dashboard now makes the trajectory, spend,
risk signals, approval, provenance, and ledger integrity visible in one place.

The implementation demonstrates:

- 500 kg to 50 kg provenance drift detection and guide-back;
- cold-chain vehicle and carrier enforcement;
- cumulative commitment-budget evaluation;
- prepare-before-confirm booking state;
- a versioned pending approval bound to the exact trace, action, state, and
  policy version;
- approve, reject, expiry, idempotency, and concurrent-decision handling;
- fresh policy evaluation before an approved booking confirms;
- exact-once confirmation, cancellation, spend movement, and notification;
- separation-of-duties and PII-boundary checks;
- atomic in-memory sequence/head updates and idempotent event append handling;
- verification before and after approval extends the same trace chain;
- a disabled-by-default disposable tamper demonstration;
- a read-only dashboard projection for spend, risk signals, and weight
  provenance; and
- a responsive local operator dashboard with approval and integrity controls.
- a labelled 22-case evaluation catalogue with exact denominators;
- separately measured policy and end-to-end latency;
- a canonical fixture-tree checksum and generated release manifest; and
- recorded browser evidence for health, shadow, enforce, approval, verification,
  tamper detection, and controlled error presentation;
- a loopback-only Rust PDP using the official Cedar 4.12.0 engine;
- a strictly validated `demo-v1` Cedar schema and policy bundle;
- fail-closed engine selection with bundle/schema identity disclosure; and
- exact functional parity across the 22-case Python/Cedar evaluation corpus; and
- optional durable single-table DynamoDB storage with optimistic revisions,
  transactional ledger writes, persisted approvals, and replay receipts.

The durable-storage specification is
[`docs/CHECKPOINT_8_IMPLEMENTATION_PLAN.md`](docs/CHECKPOINT_8_IMPLEMENTATION_PLAN.md),
with current results in
[`docs/CHECKPOINT_8_COMPLETION_REPORT.md`](docs/CHECKPOINT_8_COMPLETION_REPORT.md).

The generated evidence is in
[`docs/results/checkpoint-6-evaluation.md`](docs/results/checkpoint-6-evaluation.md),
with Cedar evidence in
[`docs/results/checkpoint-7-cedar-evaluation.md`](docs/results/checkpoint-7-cedar-evaluation.md)
and browser verification in
[`docs/results/browser-smoke.md`](docs/results/browser-smoke.md).

## Run the evaluation and checkpoint gate

Generate the measured evaluation evidence:

```bash
python3 scripts/run_evaluation.py --warmup 1 --iterations 10
python3 scripts/build_release_manifest.py
```

Run the complete Checkpoint 6 gate:

```bash
./scripts/run_checkpoint_6.sh
```

Run the complete Cedar-authoritative Checkpoint 7 gate:

```bash
./scripts/run_checkpoint_7.sh
```

Run the Checkpoint 8 durability gate:

```bash
./scripts/run_checkpoint_8.sh
```

The current labelled set contains 10 attack and 12 benign/boundary cases. The
committed results must always be read with their disclosed engine and with the
local deterministic and in-memory modes.

## Requirements and setup

- Python 3.10 or newer
- Rust stable with Cargo (for the Cedar sidecar)
- Docker with Compose (for durable DynamoDB Local mode)

From `/home/yashraj/p0/project`:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e '.[dev]'
```

No AWS account or credentials are required.

### Durable local storage

Start and initialize the pinned, loopback-only database:

```bash
docker compose up -d dynamodb-local
python3 scripts/setup_dynamodb.py
```

Select it before starting the API or CLI:

```bash
export MANIFEST_STORAGE_BACKEND=dynamodb
export MANIFEST_DYNAMODB_ENDPOINT=http://127.0.0.1:18000
export MANIFEST_DYNAMODB_TABLE=manifest-local
export MANIFEST_DEMO_NAMESPACE=local-demo
```

The table setup is idempotent and uses credential-shaped local dummy values;
never supply real AWS keys. Application restarts and `docker compose restart
dynamodb-local` retain data in a dedicated named volume. `POST /v1/demo/reset`
removes only the configured synthetic namespace.

Stop without deleting data using `docker compose stop dynamodb-local`. To use
the zero-service fallback, set `MANIFEST_STORAGE_BACKEND=memory`; memory mode is
intentionally non-durable. No manual image pull or AWS console setup is needed.

To run the API or CLI directly with Cedar, start the sidecar as documented in
[`services/cedar_pdp/README.md`](services/cedar_pdp/README.md), then set:

```bash
export MANIFEST_POLICY_ENGINE=cedar
export CEDAR_ENDPOINT=http://127.0.0.1:18765
```

The application validates Cedar at startup. It does not silently fall back to
the Python reference engine.

## Run the journeys

Benign enforce run:

```bash
python3 -m apps.runtime.run \
  --order ORD-8842 \
  --mode enforce \
  --scenario benign
```

This confirms the synthetic INR 900 booking and completes at INR 3,400 total
spend.

Adversarial enforce run:

```bash
python3 -m apps.runtime.run \
  --order ORD-8842 \
  --mode enforce \
  --scenario adversarial
```

This corrects the weight and carrier, prepares the certified INR 900 booking,
and pauses at `PENDING_APPROVAL` because projected spend is INR 4,550 against a
ceiling of INR 4,000.

Adversarial shadow run:

```bash
python3 -m apps.runtime.run \
  --order ORD-8842 \
  --mode shadow \
  --scenario adversarial
```

This records the counterfactual `GUIDE` and `ESCALATE` decisions while allowing
the synthetic unsafe path to complete.

Add `--json` for a machine-readable run summary.

Resolve the adversarial approval in the same CLI process:

```bash
python3 -m apps.runtime.run \
  --order ORD-8842 \
  --mode enforce \
  --scenario adversarial \
  --approval approve
```

Use `--approval reject` to exercise cancellation. With DynamoDB selected, the
API can retrieve and resolve a previous trace after application or database
container restart.

## Run the API

```bash
export DEMO_APPROVER_SECRET='local-demo-only-change-me'
python3 -m uvicorn apps.api.main:app --reload
```

Open <http://127.0.0.1:8000/dashboard/> for the dashboard. Use the default
adversarial enforce run to see weight guide-back and a pending approval. Enter
the value of `DEMO_APPROVER_SECRET` only when approving or rejecting; the UI
keeps it in the password field and does not store it.

The API documentation remains at <http://127.0.0.1:8000/docs>. To start the
hero run without the dashboard:

```bash
curl -X POST http://127.0.0.1:8000/v1/runs \
  -H 'content-type: application/json' \
  -d '{"order_id":"ORD-8842","mode":"enforce","scenario":"adversarial"}'
```

Use the returned `trace_id` with:

```bash
curl http://127.0.0.1:8000/v1/runs/TR-REPLACE-ME
curl http://127.0.0.1:8000/v1/traces/TR-REPLACE-ME/events
curl http://127.0.0.1:8000/v1/traces/TR-REPLACE-ME/decisions
curl http://127.0.0.1:8000/v1/traces/TR-REPLACE-ME/projection
curl http://127.0.0.1:8000/v1/traces/TR-REPLACE-ME/verify
curl 'http://127.0.0.1:8000/v1/approvals?trace_id=TR-REPLACE-ME'
curl http://127.0.0.1:8000/v1/approvals/APR-REPLACE-ME
```

Approve the exact pending action:

```bash
curl -X POST http://127.0.0.1:8000/v1/approvals/APR-REPLACE-ME \
  -H 'content-type: application/json' \
  -H 'X-Demo-Approver-Secret: local-demo-only-change-me' \
  -d '{
    "decision":"approve",
    "approver_label":"DEMO-APPROVER-OPS-1",
    "comment":"Synthetic demo approval.",
    "expected_version":1,
    "idempotency_key":"approval-smoke-001"
  }'
```

| Method | Path | Purpose |
|---|---|---|
| GET | `/health/ready` | Report runtime, policy engine, storage, and fixtures |
| GET | `/v1/fixtures/orders` | List synthetic orders and scenarios |
| POST | `/v1/runs` | Run a mode/scenario synchronously |
| GET | `/v1/runs/{trace_id}` | Read run status, spend, and selected resources |
| GET | `/v1/traces/{trace_id}/events` | Read the ordered redacted trace |
| GET | `/v1/traces/{trace_id}/decisions` | Read typed policy decisions and guidance |
| GET | `/v1/traces/{trace_id}/projection` | Read dashboard spend, risk, and provenance data |
| GET | `/v1/traces/{trace_id}/verify` | Recompute the hash chain and report the first invalid sequence |
| GET | `/v1/approvals` | Read/filter synthetic approval records |
| GET | `/v1/approvals/{approval_id}` | Read one approval and its binding |
| POST | `/v1/approvals/{approval_id}` | Approve or reject and continue the run |
| POST | `/v1/demo/reset` | Clear the configured demo namespace and mock effects |
| POST | `/v1/demo/traces/{trace_id}/tamper` | Alter one disposable terminal trace when explicitly enabled |

The approval header is a demo-only shared secret, not production identity.
Secrets are never returned, traced, or passed to policy evaluation.

### Disposable tamper demonstration

The tamper route is disabled by default. Enable it only for a separate
disposable terminal trace:

```bash
export ENABLE_DEMO_TAMPER=true
export DEMO_TAMPER_SECRET='local-tamper-only-change-me'

curl -X POST \
  http://127.0.0.1:8000/v1/demo/traces/TR-DISPOSABLE/tamper \
  -H 'content-type: application/json' \
  -H 'X-Demo-Tamper-Secret: local-tamper-only-change-me' \
  -d '{"sequence":5,"replacement_summary":"Disposable demo alteration"}'

curl http://127.0.0.1:8000/v1/traces/TR-DISPOSABLE/verify
```

The second request reports `valid: false`, `first_bad_sequence: 5`, and
`EVENT_HASH_MISMATCH`. Reset the demo after showing it. Never use the primary
approval trace for tampering.

## Run tests

```bash
python3 -m pytest -q
```

Run the complete Checkpoint 8 verification:

```bash
./scripts/run_checkpoint_8.sh
```

The earlier Checkpoint 7 gate remains available:

```bash
./scripts/run_checkpoint_7.sh
```

## Architecture

```text
CLI / FastAPI / static browser dashboard
     |
     v
RunService -> ShipmentOrchestrator -> four deterministic agents
                                         |
                                         v
                                 ManifestGovernor
                                   |           |
                                   v           v
                          PolicyEngine port  Tool registry
                         (Cedar authoritative)  |
                                   |            v
                        loopback Rust PDP --> mock tools
                                         |
                                         v
                  TraceRepository (memory or DynamoDB Local)
                    + hash-chain ledger + versioned approvals
                                      |
                                      v
                         projections + read-only verifier
```

The active policy and storage engines are disclosed by `/health/ready`. The
Checkpoint 8 gate uses authoritative Cedar plus DynamoDB Local; the Python
policy engine and memory repository remain explicit offline/test fallbacks.

## Real and simulated behavior

Real in this checkpoint:

- agent sequencing and bounded guide-back;
- tool interception, ownership, and effect classification;
- all six deterministic policy families;
- weight provenance and cumulative spend state;
- prepare/approve/reject/expire/confirm/cancel state;
- exact-once local approval resolution and workflow resume;
- conditional distributed approval versioning and durable replay receipts;
- reconstruction of runs, approvals, decisions, effects, and ledger heads
  across application and DynamoDB Local container restarts;
- decision recording, reason codes, API responses, and trace isolation;
- canonical local event hashing, per-trace heads, and read-only verification;
- detection of retained-event edits, middle deletion, reorder, duplication,
  and tail truncation while the separately stored head remains trusted; and
- a same-origin dashboard composed from the existing run, decision, approval,
  verification, and new read-only projection APIs.

Simulated:

- WMS/inventory, vehicles, carrier rates and certifications;
- freight reservation and confirmation effects;
- recipient identity and notification outbox;
- all orders and operational data.

The ledger is **tamper-evident, not immutable**. A privileged attacker able to
rewrite both all retained events and the separately stored head can construct a
new internally consistent chain. This prototype does not claim otherwise.

Deferred:

- independently signed or Object-Locked ledger checkpoints;
- Strands, Bedrock, and managed AWS deployment;
- a production frontend framework, durable dashboard sessions, and real
  logistics integrations.

The original Checkpoint 1 specification remains in
[`docs/CHECKPOINT_1_IMPLEMENTATION_PLAN.md`](docs/CHECKPOINT_1_IMPLEMENTATION_PLAN.md).
The Checkpoint 2 specification remains in
[`docs/CHECKPOINT_2_IMPLEMENTATION_PLAN.md`](docs/CHECKPOINT_2_IMPLEMENTATION_PLAN.md).
The Checkpoint 3 specification remains in
[`docs/CHECKPOINT_3_IMPLEMENTATION_PLAN.md`](docs/CHECKPOINT_3_IMPLEMENTATION_PLAN.md).
The Checkpoint 4 specification remains in
[`docs/CHECKPOINT_4_IMPLEMENTATION_PLAN.md`](docs/CHECKPOINT_4_IMPLEMENTATION_PLAN.md).
