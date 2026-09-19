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

Durable storage and cloud scripts remain deferred to later checkpoints.
