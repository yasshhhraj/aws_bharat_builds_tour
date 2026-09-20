# Deferred Checkpoint 12 Manual Setup — AWS, Bedrock, and Strands

> **Do not perform this setup now.** AWS account verification is pending. The current work is the offline [`Checkpoint 9 plan`](../CHECKPOINT_9_OFFLINE_IMPLEMENTATION_PLAN.md). This filename is retained for existing links; the AWS work now belongs to Checkpoint 12 in the revised roadmap.

**Audience:** First-time Amazon Bedrock user  
**Purpose:** Complete only the human-owned setup needed for deferred Checkpoint 12  
**Region for this checkpoint:** `us-east-1` (US East, N. Virginia)  
**Initial model:** Amazon Nova 2 Lite v1 through `bedrock-runtime`  
**Runtime model ID:** `us.amazon.nova-2-lite-v1:0`  
**Estimated manual time:** 30–60 minutes

## 1. What you do and do not need to create

For Checkpoint 12, you need:

- an AWS account with billing enabled;
- a Paid account plan if the newer AWS Free account plan does not authorize Bedrock inference;
- a local AWS login with permission to invoke one Bedrock model;
- access to Amazon Nova 2 Lite in `us-east-1`; and
- a small cost budget and email alert.

You do **not** need to create:

- a Bedrock Agent;
- a Knowledge Base;
- a Guardrail;
- a Lambda function;
- an API Gateway;
- an S3 bucket;
- a Step Functions workflow;
- an EventBridge bus;
- an Amplify application; or
- a hosted Strands resource.

Strands Agents is a Python SDK that runs inside this project's process. Bedrock supplies only the model inference API. AWS application deployment belongs to Checkpoint 13.

## 2. Security rules before starting

1. Never paste an AWS access key, secret key, session token, account password, or MFA code into this repository, a chat, a screenshot, or an issue.
2. Do not create root-user access keys.
3. Prefer temporary browser-based credentials using `aws login` or IAM Identity Center.
4. Keep credentials in the AWS credential chain, not in `.env`.
5. Use only synthetic Manifest data in model prompts.
6. Sign out or run `aws logout` after the work session if you used console credentials.

The repository's current `.env.example` contains local placeholder credentials for DynamoDB Local. Those values must not be exported globally during a real Bedrock run: environment credentials override profile credentials and would make Bedrock see the fake `local` key. Checkpoint 12 must isolate DynamoDB Local credentials inside its DynamoDB client configuration.

## 3. Step A — Select the AWS Region

First check the AWS account plan. A saved payment method does not necessarily mean the account is on the Paid plan.

1. Open **Billing and Cost Management** or [AWS Settings](https://settings.aws.com/).
2. Find the account-plan status in the **Cost and Usage** area.
3. If it says **Free plan**, decide whether to choose **Upgrade plan → Upgrade account**. AWS says this retains remaining signup credits and enables the full AWS service set, but it also enables pay-as-you-go charges beyond applicable credits. This is an owner decision; the implementation agent must not perform it.
4. If you do not want to enable billable usage, keep the local prototype in recorded/offline mode and leave Checkpoint 12 pending.
5. If the account already says **Paid plan**, do not create arbitrary EC2 or S3 usage to manufacture billing history; proceed with the authorization diagnostic and AWS Support path instead.

Then set the Region:

1. Sign in to the [AWS Management Console](https://console.aws.amazon.com/).
2. In the region selector at the upper-right, choose **US East (N. Virginia) — `us-east-1`**.
3. Keep this region selected throughout the setup.

Why this region:

- the project already defaults to `us-east-1`;
- Nova 2 Lite supports its US geographic cross-Region inference profile there;
- `us.amazon.nova-2-lite-v1:0` keeps inference routing within the US geography; and
- the application can use the same region consistently during the first integration.

Do not copy a model ID from another region. Bedrock model availability and inference-profile IDs are region-sensitive.

## 4. Step B — Create a cost budget

An AWS Budget sends an alert; it does not automatically stop Bedrock usage.

1. Open [Billing and Cost Management](https://console.aws.amazon.com/cost-management/).
2. Choose **Budgets** in the left navigation.
3. Choose **Create budget**.
4. Choose **Use a template (simplified)**, then **Monthly cost budget**. If the template screen is unavailable, choose **Customize (advanced)** and then **Cost budget**.
5. Use:
   - Budget name: `manifest-hackathon-budget`
   - Monthly amount: **USD 25**
   - Email recipient: an address you check
6. If the form permits multiple alert thresholds, add actual-spend alerts at USD 10 and USD 20 and a forecasted alert at USD 20. Otherwise, use the template's default threshold and edit it later.
7. Review and choose **Create budget**.

Record only this confirmation in your notes:

```text
[ ] Budget manifest-hackathon-budget created
```

Do not assume the budget prevents additional charges.

## 5. Step C — Create the least-privilege Bedrock policy

This policy allows inference only against the Nova 2 Lite US inference profile, its underlying foundation model, and read-only model discovery. Nova 2 Lite is an Amazon model, so it does not require AWS Marketplace subscription permissions.

Before copying the policy, find your 12-digit AWS account ID from the account menu in the upper-right of the AWS console. It is an identifier, not a credential. Replace every `YOUR_ACCOUNT_ID` below with those 12 digits and remove no quotation marks.

1. Open the [IAM console](https://console.aws.amazon.com/iam/).
2. Choose **Policies**.
3. Choose **Create policy**.
4. Choose the **JSON** editor.
5. Replace the editor contents with:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "InvokeManifestNova2Lite",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:us-east-1:YOUR_ACCOUNT_ID:inference-profile/us.amazon.nova-2-lite-v1:0",
        "arn:aws:bedrock:*::foundation-model/amazon.nova-2-lite-v1:0"
      ]
    },
    {
      "Sid": "ReadManifestBedrockModelMetadata",
      "Effect": "Allow",
      "Action": [
        "bedrock:GetFoundationModel",
        "bedrock:ListFoundationModels",
        "bedrock:GetInferenceProfile",
        "bedrock:ListInferenceProfiles"
      ],
      "Resource": "*"
    }
  ]
}
```

6. Choose **Next**.
7. Policy name: `ManifestCheckpoint9BedrockInvoke`.
8. Description: `Invoke Amazon Nova 2 Lite for the synthetic Manifest Checkpoint 12 demo.`
9. Choose **Create policy**.

Strands uses Bedrock's Converse API for this model. `bedrock:InvokeModel` authorizes Converse calls; streaming use is covered by `bedrock:InvokeModelWithResponseStream`. The wildcard Region applies only to Nova 2 Lite and is required because a geographic inference profile may route to multiple US Regions.

## 6. Step D — Attach the policy to your development identity

Use the option matching how you sign in.

### Option 1 — Existing IAM Identity Center or organization login

This is preferred when your account or organization already uses IAM Identity Center.

1. Ask the AWS account administrator to attach `ManifestCheckpoint9BedrockInvoke` to the permission set used by your development identity.
2. Confirm that the permission set is assigned to the correct AWS account.
3. Do not ask for `AdministratorAccess` merely to run this checkpoint.
4. Continue with the IAM Identity Center login steps in Section 8.

### Option 2 — Console credentials with `aws login`

AWS currently recommends browser-based console credentials for local development when you sign in through root, an IAM user, or IAM federation rather than IAM Identity Center.

1. Attach `ManifestCheckpoint9BedrockInvoke` to the IAM user, role, or group you use for development.
2. Attach AWS managed policy `SignInLocalDevelopmentAccess` to the same identity so `aws login` can obtain temporary credentials.
3. Use this identity for development rather than the root user.
4. Continue with the `aws login` steps in Section 8.

### Option 3 — Hackathon-only IAM access-key fallback

Use this only if neither temporary-credential option is available.

1. In IAM, choose **Users**, then **Create user**.
2. Name it `manifest-checkpoint9-dev`.
3. Do not enable AWS Management Console access for this user.
4. Attach `ManifestCheckpoint9BedrockInvoke` directly.
5. Open the new user, choose **Security credentials**, then **Create access key**.
6. Choose **Command Line Interface (CLI)** or **Local code**.
7. Download or copy the access key once.
8. Configure it into the shared AWS credentials file using `aws configure --profile manifest-dev`.
9. Never put the key in `.env` or source control.
10. Delete the access key after the hackathon or after moving to temporary credentials.

## 7. Step E — Verify Amazon Nova 2 Lite

Choose **Amazon → Nova 2 Lite v1** from the legacy-model section you found. The console placement does not prevent prototype use: AWS currently reports the model lifecycle as active. Recheck its lifecycle before any post-hackathon production deployment.

Nova 2 Lite is an Amazon model. It does not require an AWS Marketplace subscription or Anthropic's first-time-use form.

1. Confirm the console region is `us-east-1`.
2. Open the [Amazon Bedrock console](https://console.aws.amazon.com/bedrock/).
3. Open the legacy-model section where Nova 2 Lite is visible.
4. Select **Amazon Nova 2 Lite v1**.
5. Choose **Open in playground** or **Open in chat playground**.
6. If asked for an inference option, choose the **US geographic cross-Region** profile, not Global. The runtime model ID must be `us.amazon.nova-2-lite-v1:0`.
7. Do not choose the older **Nova Lite** model; **Nova 2 Lite** is the selected model.
8. Use this test prompt:

```text
Reply with exactly: MANIFEST_BEDROCK_OK
```

9. Set temperature to `0` if the playground exposes that control.
10. Run the prompt.

Expected result: a response containing `MANIFEST_BEDROCK_OK`.

If the result is `ValidationException: Operation not allowed`, first re-open **Select model** and confirm the US cross-Region option is selected. Nova 2 Lite cannot use in-Region inference from `us-east-1`. If the same error remains, follow the availability diagnostic in Section 11; this can indicate an account-level Bedrock authorization or quota restriction rather than an application error.

## 8. Step F — Configure secure local AWS login

### 8.1 Install or update AWS CLI v2

The `aws login` method requires AWS CLI version 2.32.0 or later.

On Linux, use the official AWS installer:

```bash
curl -fsSL https://awscli.amazonaws.com/v2/install.sh | bash
```

Restart the terminal if needed, then check:

```bash
aws --version
```

### 8.2 Preferred path for console credentials

```bash
aws login --profile manifest-dev
```

The command opens a browser. Sign in with the identity to which you attached both required policies. When prompted for a region, use:

```text
us-east-1
```

Verify the session:

```bash
aws sts get-caller-identity --profile manifest-dev
```

Do not paste the returned account ID or ARN into public material.

### 8.3 Path for IAM Identity Center

```bash
aws configure sso --profile manifest-dev
aws sso login --profile manifest-dev
aws sts get-caller-identity --profile manifest-dev
```

The wizard asks for the IAM Identity Center start URL, Identity Center region, AWS account, and permission set. Obtain these from your account administrator or AWS access portal.

### 8.4 Path for a temporary hackathon IAM access key

```bash
aws configure --profile manifest-dev
```

Enter the access key only into the CLI prompt. Use `us-east-1` as the default region and `json` as the output format. Verify with:

```bash
aws sts get-caller-identity --profile manifest-dev
```

## 9. Step G — Prepare the terminal environment

Before any real Bedrock command, remove fake DynamoDB Local credentials from the shell:

```bash
unset AWS_ACCESS_KEY_ID
unset AWS_SECRET_ACCESS_KEY
unset AWS_SESSION_TOKEN
export AWS_PROFILE=manifest-dev
export AWS_REGION=us-east-1
export AWS_DEFAULT_REGION=us-east-1
```

Check which profile and region will be used:

```bash
aws configure list --profile manifest-dev
```

Never print or inspect the secret value itself.

During Checkpoint 12 implementation, the project will add a probe command resembling:

```bash
AWS_PROFILE=manifest-dev \
AWS_REGION=us-east-1 \
python3 scripts/probe_bedrock.py \
  --model-id us.amazon.nova-2-lite-v1:0 \
  --endpoint bedrock-runtime
```

Until that script exists, the console playground test in Section 7 is sufficient.

## 10. What to report back

Report only this checklist, without credentials:

```text
[ ] Budget created
[ ] Region set to us-east-1
[ ] ManifestCheckpoint9BedrockInvoke policy created and attached
[ ] Nova 2 Lite playground test succeeded with the US inference option
[ ] Local AWS login/profile works
[ ] aws sts get-caller-identity succeeds
AWS profile name: manifest-dev
Model ID: us.amazon.nova-2-lite-v1:0
Endpoint: bedrock-runtime
```

If something fails, provide the error type and message after removing account IDs, ARNs, request IDs, and credential values.

## 11. Troubleshooting

| Error or symptom | Likely cause | Action |
|---|---|---|
| `Unable to locate credentials` | No active local login/profile | Run `aws login --profile manifest-dev` or `aws sso login --profile manifest-dev`; export `AWS_PROFILE=manifest-dev` |
| `UnrecognizedClientException` or invalid security token | Fake `local` DynamoDB credentials override the profile, or the temporary session expired | Unset the three `AWS_*KEY*`/token variables and log in again |
| `ValidationException: Operation not allowed` | The playground used the base/in-Region option, or the account is not authorized/provisioned for Bedrock on-demand inference | Re-select the US cross-Region profile. If it still fails, run the availability command below and check Service Quotas. Do not keep changing IAM policies or models blindly |
| `AccessDeniedException` on first model use | Bedrock policy missing, an organization SCP denies Bedrock, or the wrong identity is active | Verify the active identity and policy; ask the account administrator if an SCP blocks Bedrock or a destination Region in the US inference profile |
| `ValidationException` saying model identifier is invalid | Base model ID was used where the inference profile is required, or the wrong generation was selected | Use `us.amazon.nova-2-lite-v1:0`; retain both the `us.` prefix and `nova-2` portion |
| Model is absent from the main catalog | Console groups it under older or legacy models | Switch to `us-east-1` and reopen the legacy-model section where Nova 2 Lite was found |
| Anthropic first-time-use form appears | Claude/Anthropic was selected | Return to Amazon Nova 2 Lite; the Anthropic form is not needed |
| `ThrottlingException` | Account/model quota or burst limit | Wait, retry once, reduce parallel calls, and inspect Service Quotas if persistent |
| Tool-use output is malformed | Model decoding/tool schema issue | Use simple top-level object schemas, keep the first provider configuration minimal, and verify that no unsupported JSON Schema construct was generated |
| Request hangs or times out | Network issue or excessive retry/read timeout | Use the bounded timeouts and retry limits in the implementation plan; test the one-line Bedrock probe first |
| `aws login` is unknown | AWS CLI is older than 2.32.0 | Update AWS CLI v2, then rerun `aws --version` |

After the `manifest-dev` profile works, inspect account/model availability without making an inference request:

```bash
aws bedrock get-foundation-model-availability \
  --model-id amazon.nova-2-lite-v1:0 \
  --region us-east-1 \
  --profile manifest-dev \
  --query '{authorization:authorizationStatus,entitlement:entitlementAvailability,region:regionAvailability,agreement:agreementAvailability.status}'
```

The healthy result has `AUTHORIZED` and three `AVAILABLE` values. If authorization is `NOT_AUTHORIZED`, or Bedrock quotas for Nova 2 Lite show zero, application code cannot fix it. Verify that the AWS account has a valid payment method and no pending account-verification banner, then open an AWS Support case under **Account and billing → Account** and include the sanitized error, Region, model ID, and availability statuses. Do not include credentials, the full account ID, or access keys.

## 12. Cleanup after development

When finished for the day:

```bash
aws logout --profile manifest-dev
```

For IAM Identity Center:

```bash
aws sso logout
```

After the hackathon:

- delete any long-term IAM access key created as a fallback;
- remove unused policies or assignments;
- review actual spend in Billing and Cost Management; and
- retain the USD 25 budget until all AWS demo resources are removed after Checkpoint 13.

## 13. Official references

- [Strands Python quickstart](https://strandsagents.com/docs/user-guide/quickstart/python/)
- [Strands Amazon Bedrock provider](https://strandsagents.com/docs/user-guide/concepts/model-providers/amazon-bedrock/)
- [Strands tools overview](https://strandsagents.com/docs/user-guide/concepts/tools/)
- [Amazon Nova 2 Lite model card](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-amazon-nova-2-lite.html)
- [Amazon Bedrock model access](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)
- [Amazon Bedrock inference permissions](https://docs.aws.amazon.com/bedrock/latest/userguide/inference.html)
- [AWS CLI console-credential login](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html)
- [AWS CLI installation](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- [AWS Budgets setup](https://docs.aws.amazon.com/cost-management/latest/userguide/create-cost-budget.html)

References were checked on 19 September 2026. Recheck model availability before implementation if the checkpoint begins later.
