# Checkpoint 6 Browser Smoke

**Status:** PASS

**Date:** 19 September 2026  
**Source baseline:** `705b1e86cb85c01562d96741a8faa9e2615bde5e` plus the Checkpoint 6 working-tree implementation  
**Browser:** Codex in-app browser  
**Application:** Host-visible local FastAPI server and same-origin static dashboard  
**Data:** Synthetic `ORD-8842` only

## Verified states

| State | Result | Evidence |
|---|---|---|
| Health and environment disclosure | PASS | Dashboard showed `deterministic`, `python_reference / demo-v1`, `memory_hash_chain`, and `local` modes |
| Benign enforce | PASS | Completed with 500 kg, `VEH-COLD-01`, `CARRIER-COLD-01`, INR 3,400 projected spend, zero risk signals, and a valid 37-event chain |
| Adversarial shadow | PASS | Completed while displaying provenance, cold-chain, and spend counterfactuals; unsafe synthetic choices remained visibly distinguishable as shadow behavior |
| Adversarial enforce | PASS | Guided 50 kg to 500 kg, guided the carrier to `CARRIER-COLD-01`, projected INR 4,550 against INR 4,000, and paused at `PENDING_APPROVAL` |
| Bound approval and resume | PASS | The exact prepared action resumed the same trace, confirmed once, wrote one synthetic notification, and completed with 51 ledger events |
| Clean verification | PASS | Dashboard reported `VALID` for the completed 51-event trace |
| Disposable tamper verification | PASS | Separate terminal trace was altered at sequence 5; `/verify` returned `EVENT_HASH_MISMATCH` and `first_bad_sequence: 5` |
| API error presentation | PASS | Loading `TR-UNKNOWN` showed the controlled `TRACE_NOT_FOUND` message without corrupting dashboard state |
| Browser console | PASS | No warning or error entries were recorded during the primary flow |

## Screenshots

- [Health and active modes](../assets/screenshots/checkpoint-6-health.png)
- [Adversarial shadow](../assets/screenshots/checkpoint-6-shadow.png)
- [Enforce pending approval](../assets/screenshots/checkpoint-6-enforce-pending.png)
- [Approved completed trajectory](../assets/screenshots/checkpoint-6-approved.png)
- [Clean verification](../assets/screenshots/checkpoint-6-verify.png)

## Security and disclosure

- Approval and tamper secrets are not present in screenshots or this report.
- Approval and tamper actions targeted only the local synthetic demo service.
- The tamper operation used a separate disposable trace, not the primary approval trace.
- The active implementation is local and deterministic; this evidence does not claim Cedar, Strands, Bedrock, DynamoDB, or AWS deployment.

## Limitation

The controlled 404/API error state was visually verified. A separate offline/disconnected screenshot was not retained because stopping the host-visible development server closed the temporary browser tab. Automated API/static-state tests remain part of the checkpoint gate.
