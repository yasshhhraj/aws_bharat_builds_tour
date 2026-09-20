# Checkpoint 12 Implementation Plan — AWS Demo Deployment

**Plan version:** 1.0  
**Created:** 20 September 2026  
**Implementation branch:** `stage/deployment`  
**Baseline revision:** `c99711b`  
**Depends on:** Checkpoint 11 local candidate and Checkpoint 10 Bedrock Mantle evidence

## 1. Objective

Deploy the smallest reproducible public AWS demo of Manifest, verify the
governed journeys against the deployed URL, and capture the final walkthrough.

The deployment uses the already-proven Bedrock Mantle route and does not wait
for native Nova access. The deployed application must preserve the existing
governor, Cedar, approval, exact-once, and ledger behavior.

Checkpoint 12 is complete when a reviewer can open one HTTPS URL, run the
synthetic demo, inspect the governed trace, and see truthful AWS/provider
diagnostics without receiving any credential.

## 2. Selected architecture

```text
Reviewer browser
      |
      | HTTPS (App Runner managed domain)
      v
AWS App Runner — one container, maximum one instance
      |
      +-- FastAPI + static dashboard on 0.0.0.0:8080
      +-- Cedar 4.12.0 child process on 127.0.0.1:8765
      +-- Strands -> Bedrock Mantle / qwen.qwen3-coder-next
      +-- App Runner instance role -> DynamoDB

Private ECR --------> immutable application image
Secrets Manager ----> Mantle key and demo mutation secret
DynamoDB -----------> traces, approvals, receipts, and ledger records
CloudWatch Logs ----> container stdout/stderr without secrets or prompts
```

### Why this is the fastest acceptable path

- The existing dashboard is served by FastAPI, so no separate S3/CloudFront
  frontend or CORS configuration is required.
- Cedar keeps its loopback-only trust boundary inside the same container.
- App Runner supplies the public TLS endpoint and service lifecycle.
- Managed DynamoDB replaces DynamoDB Local without changing the repository
  contract.
- A private ECR image avoids granting a source-control connection to AWS.
- Maximum instance count one limits cost and keeps the demo deterministic.

## 3. Explicit non-goals

Do not add these before recording the demo:

- API Gateway, Lambda, ECS, Kubernetes, RDS, VPC connectors, a custom domain,
  Route 53, CloudFront, Amplify, Cognito, or WAF;
- native Nova support;
- real carrier, notification, inventory, or payment integrations;
- multi-tenant authentication or production identity;
- provider fallback, multiple App Runner instances, or autoscaling beyond one;
- policy, ledger, fixture, or storage-schema changes; or
- unrelated UI redesign.

## 4. Frozen safety invariants

1. Every protected tool attempt still crosses `ManifestGovernor` and Cedar.
2. Cedar stays authoritative; the model never authorizes itself.
3. Provider failure stops the trajectory before protected downstream effects.
4. There is no automatic provider fallback.
5. Approval binding and exact-once effect receipts remain unchanged.
6. The SHA-256 event chain and verification semantics remain unchanged.
7. Only synthetic fixtures may reach Bedrock Mantle.
8. No secret, AWS key, account ID, prompt body, or approval token enters Git,
   screenshots, evidence JSON, or normal logs.
9. Native AWS credentials come from the App Runner instance role, never from
   container environment variables.
10. Public mutation endpoints require a demo access secret to prevent anonymous
    users from spending hosted-model credits.
11. Cloud tampering is disabled. The local candidate retains the disposable
    tamper demonstration.

## 5. Deliverables

### Application changes

- cloud-aware DynamoDB client creation using the standard AWS credential chain;
- explicit `MANIFEST_DEPLOYMENT_MODE=aws` validation and health diagnostics;
- `DEMO_ACCESS_SECRET` protection for run/reset and other mutation endpoints;
- dashboard support for entering the demo access secret without persisting it
  outside browser session storage;
- no secret values in errors, health output, events, or logs;
- cloud-safe defaults: tamper disabled, fixed Mantle model, no fallback.

### Container

```text
Dockerfile
.dockerignore
scripts/start_checkpoint_12_cloud.sh
```

The image must:

- build the pinned Cedar binary with `cargo build --locked --release`;
- install the project with the pinned `bedrock_mantle` extra;
- contain fixtures, policies, dashboard assets, and the Cedar binary;
- run as a non-root user;
- start Cedar on loopback before FastAPI;
- listen on port 8080 for App Runner;
- forward termination signals and stop both processes cleanly;
- perform no table creation or infrastructure mutation during startup; and
- contain no `.git`, `.env`, test cache, local database, credential, or evidence
  secret.

### Infrastructure as code

Use two CloudFormation stacks because the ECR repository must exist before the
image can be pushed.

```text
infra/aws/bootstrap.yaml
infra/aws/service.yaml
```

`bootstrap.yaml` creates:

- private ECR repository with encryption, immutable tags, lifecycle cleanup,
  and `EmptyOnDelete` for reliable teardown;
- DynamoDB table with `PK` hash key, `SK` range key, on-demand billing,
  encryption, and point-in-time recovery disabled for this disposable demo;
- empty Secrets Manager resources for the Mantle key and demo access secret;
- outputs containing resource names/ARNs, never secret values.

`service.yaml` creates:

- ECR access role trusted by `build.apprunner.amazonaws.com` and using the AWS
  managed `AWSAppRunnerServicePolicyForECRAccess` policy;
- App Runner instance role trusted by `tasks.apprunner.amazonaws.com`;
- least-privilege DynamoDB permissions on only the Manifest table:
  `DescribeTable`, `GetItem`, `PutItem`, `UpdateItem`, `Query`,
  `BatchWriteItem`, and `TransactWriteItems`;
- `secretsmanager:GetSecretValue` for only the two demo secrets;
- App Runner automatic-scaling configuration with minimum one and maximum one;
- one App Runner service using the immutable ECR image digest/tag;
- HTTP health check at `/health/ready`;
- environment variables listed in section 9; and
- stack outputs for the service ARN and HTTPS URL.

### Deployment and verification tools

```text
scripts/deploy_checkpoint_12.sh
scripts/check_checkpoint_12_ready.py
scripts/run_checkpoint_12_smoke.py
scripts/pause_checkpoint_12.sh
scripts/destroy_checkpoint_12.sh
docs/manual/CHECKPOINT_12_AWS_DEPLOYMENT.md
docs/results/checkpoint-12-deployed-smoke.json
docs/results/checkpoint-12-browser-smoke.md
docs/CHECKPOINT_12_COMPLETION_REPORT.md
```

The deploy script must be restartable and stop on the first failed command. It
must never accept a secret as a command-line argument or echo one.

## 6. Implementation sequence

### Phase 0 — Preserve the local release

1. Confirm branch and baseline:

   ```bash
   git branch --show-current
   git status --short
   git rev-parse HEAD
   ```

2. Expected branch: `stage/deployment`.
3. Expected baseline: `c99711b` or a documented descendant.
4. Run only the focused offline contracts before changing code; do not repeat
   the long Checkpoint 11 evaluation.

**Gate:** clean deployment branch based on the committed CP11 merge.

### Phase 1 — Make storage safe for managed AWS

1. Add a deployment-mode setting with allowed values `local` and `aws`.
2. In local mode, retain the explicit DynamoDB Local endpoint and fake local
   credentials.
3. In AWS mode:
   - require `MANIFEST_STORAGE_BACKEND=dynamodb`;
   - require a non-local table name and Region;
   - reject `MANIFEST_DYNAMODB_ENDPOINT`;
   - reject literal `AWS_ACCESS_KEY_ID=local` or `AWS_SECRET_ACCESS_KEY=local`;
   - create the boto3 client without `endpoint_url` or explicit credentials so
     the App Runner instance role is used.
4. Keep the existing table key/schema and repository operations unchanged.
5. Add unit tests with a fake client/session proving local and AWS construction.

**Gate:** local DynamoDB contracts still pass and cloud mode cannot silently
connect to localhost or use fake credentials.

### Phase 2 — Protect public paid mutations

1. Add a constant-time `X-Manifest-Demo-Secret` check.
2. Require it on all endpoints that start or mutate work, including:
   - starting a run;
   - approval/rejection;
   - reset;
   - tamper, if ever enabled.
3. Keep read-only health, fixture, trace, decision, event, projection, and
   verification endpoints public because they contain synthetic data only.
4. Return a generic `401` without disclosing whether configuration or the
   supplied value was wrong.
5. Add a dashboard access-secret prompt. Keep the value only in
   `sessionStorage`; never place it in the URL, DOM text, logs, or trace.
6. Preserve the existing separate approver-secret check. The deployment guide
   may use the same owner-held value for both secrets to simplify the recording,
   but the server interfaces remain distinct.
7. Disable cloud tamper with `ENABLE_DEMO_TAMPER=false`.

**Gate:** unauthenticated requests cannot invoke Mantle or mutate DynamoDB;
authenticated synthetic journeys remain green.

### Phase 3 — Build and test the production image

1. Create the multi-stage Dockerfile and strict `.dockerignore`.
2. Add the cloud process supervisor script.
3. Build locally with a commit-derived immutable tag.
4. Inspect the image history and filesystem for credentials and local files.
5. Run the image locally against DynamoDB Local while selecting the recorded
   model first.
6. Run the image locally with Mantle only after explicit paid-call opt-in.
7. Stop/restart the container and verify stored traces remain in DynamoDB.

**Gate:** container health is ready, Cedar hash matches CP11, dashboard loads,
and no credential exists in an image layer.

### Phase 4 — Add and validate CloudFormation

1. Add both templates with parameters for project name, environment, Region,
   image identifier, model ID, and namespace.
2. Use generated physical IDs where practical to avoid global-name collisions.
3. Set deletion policies deliberately; this is a disposable demo, so teardown
   must not strand chargeable resources.
4. Run:

   ```bash
   aws cloudformation validate-template \
     --template-body file://infra/aws/bootstrap.yaml
   aws cloudformation validate-template \
     --template-body file://infra/aws/service.yaml
   ```

5. Add template-contract tests that inspect roles, trust principals, table
   schema, App Runner maximum size, health check, and secret references.

**Gate:** templates validate and contain no wildcard data-plane permissions
except the AWS-managed ECR access policy where AWS requires it.

### Phase 5 — Deploy in a controlled order

The deployment script performs these operations:

1. Verify AWS identity and Region.
2. Refuse a root-user ARN and refuse an unexpected account/Region if the owner
   supplied allowlisted values.
3. Deploy the bootstrap stack.
4. Prompt privately for the Mantle key and demo secret.
5. Write secret values through the AWS SDK without command-line arguments.
6. Authenticate Docker to the stack's private ECR repository.
7. Build the image with the current Git commit tag.
8. Push the immutable tag.
9. Resolve and record its ECR digest.
10. Deploy the service stack using that exact image identifier.
11. Wait for CloudFormation and App Runner readiness.
12. Print only the public URL, Region, stack names, image digest, and safe next
    commands.

**Gate:** `GET /health/ready` returns HTTP 200 from the App Runner URL.

### Phase 6 — Deployed smoke and governed journey

The smoke tool accepts secrets via an interactive prompt or environment, never
as command-line flags. It records only safe evidence.

Required checks:

1. Health reports:
   - deployment mode `aws`;
   - runtime `strands`;
   - provider `bedrock_mantle`;
   - requested/resolved model `qwen.qwen3-coder-next`;
   - provider fallback `false`;
   - policy engine `cedar` and expected bundle hash;
   - storage `dynamodb` and the expected Region/table;
   - tamper disabled.
2. An unauthenticated start request returns `401` and makes no model call.
3. Benign enforce completes with one confirmation and one notification.
4. Adversarial enforce reaches pending approval.
5. Approval resumes and completes exactly once.
6. Replaying the decision does not duplicate confirmation or notification.
7. Rejection cancels the prepared commitment exactly once.
8. Ledger verification remains valid.
9. Provider failure, if deliberately simulated without rotating production
   secrets, fails closed with an inspectable trace.

**Gate:** safe JSON evidence contains the URL hostname, Region, image digest,
policy hash, trace IDs, statuses, receipt counts, and ledger results—but no
secret, prompt body, account ID, or user path.

### Phase 7 — Browser recording

Record one concise journey from the deployed HTTPS URL:

1. Open the dashboard and show the AWS environment panel.
2. Show `bedrock_mantle`, `qwen.qwen3-coder-next`, Cedar, DynamoDB, and no
   fallback.
3. Run benign enforce and show completed status, policy decisions, exact-once
   receipts, and valid ledger.
4. Run adversarial enforce and explain 50 kg to 500 kg guide-back, cold-chain
   correction, and budget escalation.
5. Approve once; show the final completion and receipts.
6. Refresh the page and show that the trace persists.
7. State aloud that logistics effects and data are simulated/synthetic.

Before recording:

- close AWS console tabs and terminals;
- clear browser autofill and unrelated history;
- ensure no access secret appears in a field or developer tools;
- use a clean browser window at 100% zoom;
- capture the App Runner hostname but not AWS account identifiers; and
- keep the local CP11 recording path as a fallback.

### Phase 8 — Freeze, pause, and optionally destroy

1. Commit code, templates, safe smoke evidence, and documentation.
2. Do not commit a live URL if the service will be destroyed and the document
   could imply it remains available.
3. Record exact source commit and ECR digest.
4. Pause App Runner immediately after recording if judging does not require a
   continuously live URL.
5. Resume only for judging or a final check.
6. Delete the service stack and then bootstrap stack after submission when a
   persistent URL is no longer required.
7. Confirm App Runner, ECR images, DynamoDB table, and secrets were deleted.

**Gate:** final evidence is truthful and chargeable resources have an explicit
owner and teardown date.

## 7. Manual AWS setup for the owner

These actions cannot be safely inferred or performed without the account owner.

### 7.1 Create a non-root deployment identity

Do not create root access keys.

Preferred:

1. Sign in to the AWS console.
2. Open **IAM Identity Center**.
3. Create/select your user and an administrative deployment permission set.
4. Assign it to this AWS account.
5. Configure the CLI using the portal's `aws configure sso` instructions.

Fast temporary alternative for a time-limited hackathon account:

1. Use root only in the console to open **IAM**.
2. Create an IAM user named `manifest-deployer` with console disabled unless
   needed.
3. Enable MFA.
4. Grant the permissions needed to deploy CloudFormation, ECR, App Runner,
   DynamoDB, IAM roles, Secrets Manager, and read CloudWatch logs. Because the
   template creates service roles, the identity also needs tightly scoped
   `iam:PassRole` for the Manifest roles.
5. Create a CLI access key only for this deployment session.
6. Remove the key and broad deployment permissions after the stack is stable.

Never paste AWS keys or the output containing the account ID into chat,
screenshots, Git, or demo evidence.

### 7.2 Configure and verify the CLI

```bash
aws configure --profile manifest-deployer
export AWS_PROFILE=manifest-deployer
export AWS_REGION=us-east-1
export AWS_DEFAULT_REGION=us-east-1
aws sts get-caller-identity
```

Privately verify:

- `Arn` is a user, assumed role, or SSO role—not `:root`;
- the account is the intended account; and
- the Region is `us-east-1`.

Do not post the full command output. It contains the account ID.

### 7.3 Create a budget alert before deployment

1. Open **Billing and Cost Management → Budgets**.
2. Create a monthly cost budget appropriate for the account; `$10` is a
   reasonable short-demo warning threshold if that matches your constraints.
3. Add your email notification at 50%, 80%, and 100% actual/forecast spend.
4. Confirm the subscription email if AWS sends one.
5. Remember that budget notifications are not an immediate hard spending cap.

### 7.4 Confirm required service access

In `us-east-1`, verify that your identity can open:

- CloudFormation;
- ECR private repositories;
- App Runner;
- DynamoDB;
- Secrets Manager; and
- CloudWatch Logs.

The Bedrock Mantle key is separate from normal AWS SDK credentials. Keep the
working key ready locally, but do not place it in `.env`, shell history, or a
command argument.

### 7.5 Approve the deployment boundary

Before running the deploy script, explicitly accept that:

- App Runner and Mantle inference are billable;
- the App Runner URL is public;
- synthetic trace reads are public;
- mutations require the demo secret;
- the service is limited to one instance; and
- the service will be paused or deleted after recording.

## 8. Required environment configuration

Non-secret App Runner variables:

```text
MANIFEST_DEPLOYMENT_MODE=aws
MANIFEST_AGENT_RUNTIME=strands
MANIFEST_MODEL_PROVIDER=bedrock_mantle
MANIFEST_MODEL_ID=qwen.qwen3-coder-next
MANIFEST_BEDROCK_REGION=us-east-1
MANIFEST_AGENT_MAX_TURNS=8
MANIFEST_AGENT_TIMEOUT_SECONDS=60
MANIFEST_MODEL_MAX_OUTPUT_TOKENS=1024
MANIFEST_POLICY_ENGINE=cedar
CEDAR_ENDPOINT=http://127.0.0.1:8765
CEDAR_TIMEOUT_MS=1000
CEDAR_POLICY_METADATA_PATH=policies/demo-v1/metadata.json
MANIFEST_STORAGE_BACKEND=dynamodb
MANIFEST_DYNAMODB_TABLE=<bootstrap stack output>
MANIFEST_DEMO_NAMESPACE=checkpoint-12-aws-demo
AWS_DEFAULT_REGION=us-east-1
ENABLE_DEMO_TAMPER=false
```

Secrets injected by ARN:

```text
BEDROCK_MANTLE_API_KEY=<Secrets Manager ARN>
DEMO_ACCESS_SECRET=<Secrets Manager ARN>
DEMO_APPROVER_SECRET=<same or separate owner-held secret ARN>
```

Forbidden in App Runner configuration:

```text
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_SESSION_TOKEN
MANIFEST_DYNAMODB_ENDPOINT
OPENROUTER_API_KEY
MANIFEST_RUN_LIVE_OPENROUTER
MANIFEST_RUN_LIVE_BEDROCK_MANTLE
DEMO_TAMPER_SECRET
```

## 9. Failure handling and rollback

| Failure | Required response |
|---|---|
| Image build fails | Stop before AWS service deployment; fix locally |
| ECR push fails | Verify identity/Region and repository output; do not make repository public |
| CloudFormation rollback | Read stack events, fix the first failing resource, redeploy |
| App Runner cannot pull | Check ECR access-role trust and managed policy |
| App Runner cannot read secrets | Check instance-role secret ARN scope and Region |
| Health says storage unavailable | Check table name, Region, role policy, and cloud client mode |
| Health says Cedar unavailable | Inspect startup logs and policy paths; do not fall back to Python policy |
| Mantle fails | Preserve safe trace; do not switch to OpenRouter or recorded mode under the same claim |
| Unexpected public spend | Pause App Runner immediately, then rotate/delete the Mantle secret |
| Deployment is unstable near deadline | Use the completed CP11 local candidate and disclose that AWS deployment is unavailable |

Rollback is CloudFormation stack rollback or App Runner pause. Never weaken
Cedar, disable authentication, add embedded credentials, or silently select a
different provider to make deployment green.

## 10. Acceptance gates

### Code and container

- ordinary Python suite passes;
- Cedar Rust tests pass;
- managed-DynamoDB configuration tests pass;
- public mutation-authentication tests pass;
- container runs as non-root and has no secret-bearing layer;
- local recorded container smoke passes.

### Infrastructure

- both templates validate;
- CloudFormation stacks reach `CREATE_COMPLETE` or `UPDATE_COMPLETE`;
- ECR image digest is recorded;
- App Runner is `RUNNING` with maximum one instance;
- health endpoint is ready over HTTPS;
- IAM policies are resource-scoped;
- budget alert exists.

### Application

- deployed benign journey completes;
- adversarial journey guides and escalates correctly;
- approval/rejection and replay are exact-once;
- trace survives container/service restart;
- ledger verification passes;
- anonymous mutation is rejected;
- dashboard labels AWS, Mantle, Cedar, DynamoDB, and synthetic effects honestly.

### Evidence

- sanitized deployed smoke JSON;
- one browser smoke record;
- screenshots and short video;
- completion report with Region, source commit, image digest, policy hash, and
  known limitations;
- pause and teardown commands tested or dry-run reviewed.

## 11. Stop/go decisions

Proceed to deployment only when all are true:

- CP11 code is committed;
- the branch is `stage/deployment` and clean;
- AWS CLI identity is non-root;
- budget notification is configured;
- the owner approves a public billable service;
- the Mantle key still passes its metadata probe; and
- unauthenticated paid mutations are blocked.

Stop and use the local candidate if any of these cannot be satisfied before the
submission deadline. Do not spend time on Checkpoint 13; record it as
`NOT_REQUIRED` unless the judging rules explicitly demand native Nova.

## 12. Official AWS references

- App Runner image deployments: <https://docs.aws.amazon.com/apprunner/latest/dg/service-source-image.html>
- App Runner IAM roles: <https://docs.aws.amazon.com/apprunner/latest/dg/security_iam_service-with-iam.html>
- App Runner environment secrets: <https://docs.aws.amazon.com/apprunner/latest/dg/env-variable-manage.html>
- App Runner health checks: <https://docs.aws.amazon.com/apprunner/latest/dg/manage-configure-healthcheck.html>
- App Runner pause/resume: <https://docs.aws.amazon.com/apprunner/latest/dg/manage-pause.html>
- App Runner pricing: <https://aws.amazon.com/apprunner/pricing/>
- CloudFormation App Runner service: <https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-apprunner-service.html>
- CloudFormation ECR repository: <https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-ecr-repository.html>
- DynamoDB IAM actions: <https://docs.aws.amazon.com/service-authorization/latest/reference/list_dynamodb.html>

