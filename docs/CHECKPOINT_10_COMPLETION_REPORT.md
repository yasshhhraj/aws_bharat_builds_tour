# Checkpoint 10 Completion Report — Bedrock Mantle Provider Portability

**Status:** COMPLETE

**Completed:** 20 September 2026

**Provider:** Amazon Bedrock Mantle

**Model:** `qwen.qwen3-coder-next`

**Region:** `us-east-1`

**Runtime:** Strands `1.56.0` using OpenAI-compatible Chat Completions

## Exit result

Checkpoint 10 proved that a paid Amazon Bedrock model can execute the same
bounded Strands roles and governed tools as the recorded provider without
changing orchestration, Cedar policy, approval semantics, persistence, or the
hash-chain ledger.

```text
Mantle model discovery:         ready; configured model present
Paid Inventory probe:          passed
Paid benign hero journey:      passed; status completed
Paid adversarial journey:      passed; status pending_approval
Live tests:                     3 passed in 55.83 seconds
Offline regression:            201 passed, 15 skipped
Application provider fallback: none
```

## Governance proof

The benign journey completed all nine governed operations, including dispatch,
booking confirmation, and the simulated tracking outbox. Cedar returned
`SPEND_WITHIN_CEILING` for the financial commitment, and the ledger verified.

The adversarial journey completed the bounded reads and reversible actions, then
Cedar returned an enforced `SPEND_APPROVAL_REQUIRED` escalation for
`confirm_freight_booking`. The run stopped in `pending_approval`; no confirmation
or notification was created, and the ledger verified.

## Evidence

- [`results/checkpoint-10-bedrock-mantle-inventory-probe.json`](results/checkpoint-10-bedrock-mantle-inventory-probe.json)
- [`results/checkpoint-10-bedrock-mantle-inventory-probe.md`](results/checkpoint-10-bedrock-mantle-inventory-probe.md)
- [`results/checkpoint-10-bedrock-mantle-benign.json`](results/checkpoint-10-bedrock-mantle-benign.json)
- [`results/checkpoint-10-bedrock-mantle-benign.md`](results/checkpoint-10-bedrock-mantle-benign.md)
- [`results/checkpoint-10-bedrock-mantle-adversarial.json`](results/checkpoint-10-bedrock-mantle-adversarial.json)
- [`results/checkpoint-10-bedrock-mantle-adversarial.md`](results/checkpoint-10-bedrock-mantle-adversarial.md)

All evidence identifies the paid hosted provider, requested fixed model, active
Cedar engine, governed tool outcomes, and ledger result. No API key, prompt,
authorization header, account identifier, or raw provider response is retained.

## OpenRouter disposition

OpenRouter remains implemented but is not the selected submission path. Its free
router and fixed free Nemotron route completed isolated probes but were not
reliable across the full multi-role gate. Those failures were not hidden or
reclassified as successful evidence.

## Cleanup

```bash
unset BEDROCK_MANTLE_API_KEY
unset MANIFEST_RUN_LIVE_BEDROCK_MANTLE
```

Short-term keys expire automatically. A long-term development key should be
deactivated or deleted in the Bedrock console after testing. Review AWS Billing
and Cost Management for the resulting model usage.

## Next checkpoint

Proceed to Checkpoint 11 — Local Prototype Hardening and Submission Candidate.
