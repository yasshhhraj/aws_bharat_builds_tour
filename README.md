# Manifest

Manifest is a learning-focused hackathon prototype for governing autonomous
logistics-agent actions before they create physical or financial effects.

The project is intentionally being built from plain Python first. Agent SDKs,
Cedar, cloud storage, APIs, and the dashboard will be added only after the core
shipment journey works locally.

## Current status

Project initialization is complete. Checkpoint 1—one deterministic shipment
journey through four plain-Python agents—is the next implementation step.

## Requirements

- Python 3.10 or newer

No third-party runtime dependencies are required yet.

## Layout

```text
apps/runtime/          Sequential agent workflow
apps/api/              HTTP API (later checkpoint)
packages/domain/       Shared data models
packages/tools/        Mock logistics tools and registry
packages/governor/     Governance decisions and trajectory state
packages/provenance/   Numeric source tracking
packages/commitments/  Prepare, approve, and confirm lifecycle
packages/ledger/       Ordered hash-chain events
fixtures/              Deterministic synthetic data
policies/              Cedar policies (later checkpoint)
tests/                 Unit, integration, and end-to-end tests
```

## Verify the initialized project

```bash
python3 -m compileall -q apps packages
```

See the detailed build plan in
[`../docs/Manifest_36_Hour_Hackathon_Prototype_Plan.md`](../docs/Manifest_36_Hour_Hackathon_Prototype_Plan.md).
