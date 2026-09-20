# Checkpoint 11 Browser Smoke Evidence

**Status:** Manual visual smoke pending

The automated dashboard contracts pass, and the local launcher was verified to
start DynamoDB Local, the Cedar sidecar, and FastAPI on loopback. The health
endpoint reported the expected recorded Strands runtime, fixed model route,
authoritative Cedar policy engine, DynamoDB Local storage, and no provider
fallback.

Automated coverage verifies:

- runtime/provider/requested/resolved model diagnostics;
- safe, trace-linked provider failure rendering;
- approval, cancellation, exact-once, ledger, and tamper states;
- local/synthetic/recorded-model disclosure;
- no external dashboard assets.

The in-app browser could not open the loopback URL because its security policy
blocks local-network targets. This is not recorded as a visual pass. A human
must complete the browser, keyboard, responsive-layout, and screenshot checks
in [`../manual/CHECKPOINT_11_LOCAL_DEMO.md`](../manual/CHECKPOINT_11_LOCAL_DEMO.md).

