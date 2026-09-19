# Scripts

`run_checkpoint_1.sh` runs the complete automated test suite and then executes
the deterministic `ORD-8842` CLI journey.

`run_checkpoint_2.sh` verifies the governed shadow/enforce journeys.

`run_checkpoint_3.sh` verifies approval, resume, rejection, and cancellation.

`run_checkpoint_4.sh` runs the full regression suite, all primary CLI journeys,
and the focused hash-chain verification and disposable-tamper API tests.

`run_checkpoint_5.sh` runs the full regression suite, focused dashboard and
projection contracts, and the primary CLI journeys used by the operator UI.

Durable seed, evaluation, and cloud scripts will be added in later checkpoints.
