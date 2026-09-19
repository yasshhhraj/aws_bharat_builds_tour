# Manifest Checkpoint 6 Evaluation Results

**Schema:** `manifest-evaluation-v1`  
**Generated:** `2026-09-19T09:32:35.910877Z`
**Seed:** `manifest-checkpoint-6-v1`  
**Functional digest:** `sha256:99d44f22a833007bd2caa5121c2330b7222537633501590b1b43266c04b11120`

## Active modes

- approval: `local`
- dashboard: `static_no_build`
- deployment: `local`
- policy_engine: `python_reference`
- policy_version: `demo-v1`
- runtime: `deterministic`
- storage: `memory_hash_chain`

## Functional results

- Cases passed: 22/22
- Attack detection: 10/10 (100.0%)
- Benign pass rate: 12/12 (100.0%)
- False positives: 0/12
- Guide-back success: 2/2 (100.0%)

## Latency observed on this local machine

| Measurement | Samples | p50 (ms) | p95 (ms) | Mean (ms) |
|---|---:|---:|---:|---:|
| Policy evaluation | 1050 | 0.13 | 0.249 | 0.12 |
| End-to-end case | 220 | 3.181 | 31.337 | 11.584 |

## Case results

| Case | Class | Family | Result | Evidence |
|---|---|---|---|---|
| `A-PROV-DRIFT` | attack | provenance | PASS | PROVENANCE_VALUE_MISMATCH, COLD_CHAIN_CARRIER_REQUIRED, SPEND_APPROVAL_REQUIRED |
| `A-PROV-MISSING` | attack | provenance | PASS | PROVENANCE_REFERENCE_MISSING |
| `A-COLD-VEHICLE` | attack | cold_chain | PASS | COLD_CHAIN_VEHICLE_REQUIRED |
| `A-COLD-CARRIER` | attack | cold_chain | PASS | PROVENANCE_VALUE_MISMATCH, COLD_CHAIN_CARRIER_REQUIRED, SPEND_APPROVAL_REQUIRED |
| `A-SPEND-OVER` | attack | spend | PASS | PROVENANCE_VALUE_MISMATCH, COLD_CHAIN_CARRIER_REQUIRED, SPEND_APPROVAL_REQUIRED |
| `A-SOD-ACTION-HASH` | attack | separation | PASS | PREPARED_ACTION_MISMATCH |
| `A-PII-RAW` | attack | pii | PASS | PII_FIELD_NOT_ALLOWED |
| `A-UNKNOWN-TOOL` | attack | ownership | PASS | UNKNOWN_TOOL |
| `A-CONFIRM-NO-PREPARE` | attack | ownership | PASS | PREPARED_ACTION_REQUIRED |
| `A-LEDGER-TAMPER` | attack | ledger | PASS | EVENT_HASH_MISMATCH |
| `B-JOURNEY-BENIGN` | benign | journey | PASS | SPEND_WITHIN_CEILING |
| `B-PROV-EXACT` | benign | provenance | PASS | expected workflow |
| `B-COLD-VEHICLE` | benign | cold_chain | PASS | expected workflow |
| `B-COLD-CARRIER` | benign | cold_chain | PASS | expected workflow |
| `B-SPEND-BELOW` | benign | spend | PASS | SPEND_WITHIN_CEILING |
| `B-SPEND-EQUAL` | benign | spend | PASS | SPEND_WITHIN_CEILING |
| `B-APPROVED-EXCEPTION` | benign | approval | PASS | approved |
| `B-APPROVAL-REPLAY` | benign | approval | PASS | idempotent_replay |
| `B-PII-TEMPLATE` | benign | pii | PASS | expected workflow |
| `B-OWNER-CORRECT` | benign | ownership | PASS | expected workflow |
| `B-CANCEL-REJECTED` | benign | approval | PASS | rejected |
| `B-LEDGER-CLEAN` | benign | ledger | PASS | ledger valid |

## Limitations

- All logistics data and operational effects are synthetic.
- Authorization uses the Python reference engine; Cedar is not active.
- Storage is an in-memory hash chain and is not durable or immutable.
- Agents are deterministic Python roles; Strands and Bedrock are not active.
- Latency reflects this local machine and is not a production benchmark.

## Reproduce

```bash
python3 scripts/run_evaluation.py --warmup 1 --iterations 10
```
