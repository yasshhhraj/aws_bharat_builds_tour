# Policies

Checkpoint 7 provides a validated Cedar `demo-v1` policy bundle for Manifest's
six policy families. The JSON Cedar schema is in `schema/`, the policies and
stable decision metadata are in `demo-v1/`, and the local PDP is implemented in
`services/cedar_pdp/` with the official `cedar-policy` crate pinned to 4.12.0.

The adapter choice is fixed at startup and shown by `/health/ready`, decisions,
evaluation evidence, and the release manifest. Cedar is authoritative when
`MANIFEST_POLICY_ENGINE=cedar`; startup fails if the sidecar, schema, version,
or optional pinned bundle hash does not match. The Python engine remains an
explicit reference/offline mode and is never selected as a silent fallback.
