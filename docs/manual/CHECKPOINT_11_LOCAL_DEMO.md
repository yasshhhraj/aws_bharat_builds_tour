# Checkpoint 11 Local Demo Runbook

This runbook starts and rehearses the complete local submission candidate. It
uses Strands with the recorded model, the loopback Cedar sidecar, DynamoDB
Local, synthetic logistics data, and simulated effects. It does not invoke a
hosted model and does not require AWS credentials.

## 1. Prerequisites

From the project root, confirm:

```bash
.venv/bin/python --version
docker version
cargo --version
```

Install project dependencies if needed:

```bash
.venv/bin/pip install -e '.[dev,bedrock_mantle]'
```

The Mantle optional dependency is installed only so its adapter contract can be
tested offline. The CP11 launcher selects `recorded` and makes no paid request.

## 2. Start the complete local stack

Run:

```bash
./scripts/start_checkpoint_11_local.sh
```

The script starts digest-pinned DynamoDB Local, validates the local table,
builds and starts Cedar on loopback, starts FastAPI on loopback, and validates
`/health/ready` before printing the dashboard URL.

If approval/tamper secrets were not exported, the script creates ephemeral
values and prints them for this process. Copy them only into the matching local
dashboard password fields. Do not paste them into source, chat, screenshots, or
recordings.

Press `Ctrl-C` in the launcher terminal to stop the API and Cedar. DynamoDB
Local remains available and its named volume is not deleted.

## 3. Verify the environment panel

Open the printed `http://127.0.0.1:<port>/dashboard/` URL and confirm:

```text
Runtime:          strands
Provider:         recorded
Requested model:  manifest-recorded-v1
Resolved model:   manifest-recorded-v1
Route:            fixed; fallback off
Policy:           cedar / demo-v1
Storage:          dynamodb_local
Ledger:           sha256 / ledger-event-v1
Data & effects:   synthetic / simulated
```

Stop if the provider is hosted, fallback is active, the policy engine is not
Cedar, or the page does not clearly label simulation.

## 4. Rehearsal A

1. Select `Benign`, `Enforce`, then run the shipment.
2. Confirm `COMPLETED`, INR 3,400 projected/committed spend, one confirmation,
   one notification, and a valid ledger.
3. Reset the demo.
4. Select `Adversarial`, `Enforce`, then run.
5. Confirm the 50 kg attempt was guided to 500 kg, the compliant cold-chain
   carrier was selected, and INR 4,550 projected spend paused against the INR
   4,000 ceiling.
6. Confirm the state says `APPROVAL REQUIRED` and no booking was confirmed.
7. Enter the ephemeral approval secret and approve once.
8. Confirm completion, one confirmation, one notification, and a valid ledger.
9. Record duration and any defect in
   `docs/results/checkpoint-11-rehearsal-1.md`.

## 5. Rehearsal B

1. Reset the demo and run `Adversarial` in `Shadow` mode.
2. Confirm interventions are labelled counterfactual and the simulated unsafe
   path is not described as an enforce-mode authorization.
3. Reset and repeat the adversarial enforce/approval journey.
4. If tamper mode is shown, create the separate disposable trace, enter the
   tamper secret, alter event 5, and confirm the first bad sequence is reported.
5. Confirm the primary trace remains valid.
6. Record duration and defects in
   `docs/results/checkpoint-11-rehearsal-2.md`.

## 6. Accessibility and viewport smoke

- Activate the skip link and all controls with the keyboard.
- Confirm focus is visible.
- Confirm run/error messages are announced and receive focus after failure.
- Verify state is communicated with words as well as color.
- Inspect at approximately 320, 768, and 1440 CSS pixels.
- Confirm there is no page-level horizontal scrolling or clipped approval
  control.
- Confirm secrets are password fields and are cleared after use.

## 7. Screenshot and recording safety

Before every capture, check for approval, tamper, provider, or AWS credentials;
AWS account IDs; email addresses; browser profiles; terminal history; personal
filesystem paths; unrelated tabs; and claims that the local application is
deployed on AWS.

Capture at least the environment/health view, adversarial pending approval,
approved exact-once receipt, and disposable tamper detection. The correct claim
is: “local Strands/Cedar/DynamoDB Local candidate with a recorded model;
separate Checkpoint 10 evidence proves Bedrock Mantle inference.”

Keep the raw video outside Git unless repository-size and submission rules have
been reviewed. Record its filename and SHA-256 digest in the completion report.

## 8. Automated gate

After the browser rehearsals, run:

```bash
./scripts/run_checkpoint_11.sh
```

It is successful only after the full regression, storage/restart checks, two
automated rehearsals, 22-case evaluation, functional-digest parity, hygiene
scan, and release-manifest generation all pass.
