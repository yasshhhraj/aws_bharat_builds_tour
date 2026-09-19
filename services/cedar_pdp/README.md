# Manifest Cedar PDP

This loopback-only sidecar is Manifest's Checkpoint 7 authorization service. It
uses the official `cedar-policy` Rust crate pinned in `Cargo.lock`, validates the
schema and full policy set in strict mode before listening, and exposes only:

- `GET /health/ready`
- `POST /v1/authorize`

It accepts a maximum 64 KiB request, validates typed entities/context against
the Cedar schema, and returns the decision, determining policy IDs, validation
diagnostics, policy version, bundle hash, and evaluation time. It does not log
authorization bodies and refuses non-loopback listen addresses.

The supported launch path is `./scripts/run_checkpoint_7.sh`. Direct local use:

```bash
cargo run --locked --manifest-path services/cedar_pdp/Cargo.toml -- \
  --listen 127.0.0.1:18765 \
  --schema policies/schema/manifest.cedarschema.json \
  --policies policies/demo-v1/manifest.cedar \
  --policy-version demo-v1
```
