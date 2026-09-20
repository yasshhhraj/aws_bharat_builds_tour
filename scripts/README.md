# Scripts

`run_checkpoint_1.sh` runs the complete automated test suite and then executes
the deterministic `ORD-8842` CLI journey.

`run_checkpoint_2.sh` verifies the governed shadow/enforce journeys.

`run_checkpoint_3.sh` verifies approval, resume, rejection, and cancellation.

`run_checkpoint_4.sh` runs the full regression suite, all primary CLI journeys,
and the focused hash-chain verification and disposable-tamper API tests.

`run_checkpoint_5.sh` runs the full regression suite, focused dashboard and
projection contracts, and the primary CLI journeys used by the operator UI.

`run_evaluation.py` executes the isolated labelled Checkpoint 6 catalogue,
collects policy and end-to-end latency, and generates JSON and Markdown evidence.

`build_release_manifest.py` binds that evidence to the source revision, fixture
tree checksum, policy version, active modes, dependency versions, and test count.

`run_checkpoint_6.sh` preserves the Checkpoint 5 gate, regenerates the measured
evidence and release manifest, and validates recorded browser-smoke evidence.

`run_checkpoint_7.sh` builds and starts the pinned loopback Cedar PDP, runs the
offline and live integration suites, exercises enforce and shadow journeys,
regenerates Cedar-specific evaluation evidence, verifies exact functional
digest parity with Checkpoint 6, and writes the Checkpoint 7 release manifest.

`check_cedar_ready.py` performs the bounded readiness check used by that gate.

`run_checkpoint_8.sh` proves DynamoDB Local durability, restart recovery, and
functional parity with Cedar.

`run_checkpoint_9_offline.sh` proves the bounded Strands runtime through the
recorded, no-network model.

`run_checkpoint_10_bedrock_mantle.sh` is the historical provider-portability
gate. It delegates to `run_bedrock_mantle_gate.sh`; live modes remain explicitly
billable and opt-in.

`start_checkpoint_11_local.sh` starts the loopback-only recorded/Cedar/
DynamoDB Local demo and cleans up only the API and Cedar child processes it
created.

`run_checkpoint_11.sh` is the canonical local candidate gate. It runs the
Python, Rust, Cedar, storage, restart, evaluation, parity, hygiene, and two-pass
automated rehearsal checks without invoking a hosted model.

`check_submission_hygiene.py` scans tracked and untracked text artifacts for
high-confidence credential leaks, personal paths on current submission
surfaces, external dashboard assets, and selected stale claims.

AWS application deployment remains Checkpoint 12.
