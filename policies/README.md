# Policies

Checkpoint 2 uses the deterministic `PythonReferencePolicyEngine` in
`packages/policy/`. It implements six policy families and supplies the
executable test contract for a future Cedar adapter.

Cedar is deliberately not reported as active. A Cedar bundle may replace the
reference engine only after it passes the same table-driven positive, negative,
boundary, and missing-context cases. Adapter choice is fixed at startup and is
shown by `/health/ready` and every run summary.
