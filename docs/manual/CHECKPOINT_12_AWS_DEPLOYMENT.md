# Checkpoint 12 — AWS Account and Deployment Guide

## 1. Account safety

1. Create/sign in to the AWS account and complete payment/contact verification.
2. Enable MFA on the root user.
3. Never create root access keys.
4. Create a non-root deployment identity using IAM Identity Center (preferred)
   or a temporary IAM user named `manifest-deployer`.
5. The deployment identity needs CloudFormation, ECR, App Runner, DynamoDB,
   Secrets Manager, CloudWatch Logs, IAM role creation, and `iam:PassRole`.
6. Remove temporary access keys/broad permissions after deployment.

## 2. Budget alert

In **Billing and Cost Management → Budgets**, create a monthly cost budget that
matches your limit (for example USD 10) with email alerts at 50%, 80%, and 100%.
Budget alerts are notifications, not a hard cap.

## 3. CLI setup

Install AWS CLI v2, then:

```bash
aws configure --profile manifest-deployer
export AWS_PROFILE=manifest-deployer
export AWS_REGION=us-east-1
export AWS_DEFAULT_REGION=us-east-1
aws sts get-caller-identity
```

Privately confirm that the ARN is not `:root`. Do not post the output because it
contains your account ID.

You do not manually create DynamoDB, ECR, App Runner, IAM service roles, or
Secrets Manager resources. CloudFormation creates them.

## 4. Pre-deployment checks

```bash
git branch --show-current
git status --short
aws cloudformation validate-template --template-body file://infra/aws/bootstrap.yaml
aws cloudformation validate-template --template-body file://infra/aws/service.yaml
```

The branch should be `stage/deployment`. Commit the reviewed implementation
before deployment so the image tag identifies stable source.

## 5. Deploy

Keep the Mantle key out of shell history. Either let the script prompt for it,
or export it from a secure local source. Then run:

```bash
./scripts/deploy_checkpoint_12.sh
```

The script verifies that the CLI identity is not root, creates the bootstrap
stack, stores the Mantle key, builds/pushes the image, deploys App Runner, and
prints the HTTPS URL. Deployment can take 10–20 minutes.

Retrieve the generated demo access secret privately:

```bash
aws secretsmanager get-secret-value \
  --secret-id "<Access secret ARN printed by deployment>" \
  --query SecretString --output text
```

Do not paste or record that value.

## 6. Verify and record

```bash
.venv/bin/python scripts/check_checkpoint_12_ready.py "https://<service-host>"
.venv/bin/python scripts/run_checkpoint_12_smoke.py "https://<service-host>"
```

Open `https://<service-host>/dashboard/`, enter the access secret in the masked
field, and record the benign and adversarial approval journeys. Show AWS mode,
Mantle, Qwen, Cedar, DynamoDB, exact-once receipts, and valid ledger. State that
all logistics data/effects are synthetic and simulated.

## 7. Stop charges

Pause after recording:

```bash
./scripts/pause_checkpoint_12.sh
```

Delete everything after submission when a live URL is no longer required:

```bash
./scripts/destroy_checkpoint_12.sh
```

Deletion removes App Runner, IAM service roles, DynamoDB data, ECR images, and
the two secrets. It is intentionally destructive.
