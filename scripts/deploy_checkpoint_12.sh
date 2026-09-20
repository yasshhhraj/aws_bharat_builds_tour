#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
export AWS_REGION="${REGION}"
BOOTSTRAP_STACK="${MANIFEST_BOOTSTRAP_STACK:-manifest-stage-bootstrap}"
SERVICE_STACK="${MANIFEST_SERVICE_STACK:-manifest-stage-service}"

for command in aws docker git; do command -v "${command}" >/dev/null || { echo "Missing ${command}." >&2; exit 2; }; done
ARN=$(aws sts get-caller-identity --region "${REGION}" --query Arn --output text)
[[ "${ARN}" != *":root" ]] || { echo "Refusing deployment with the AWS root user." >&2; exit 2; }

aws cloudformation deploy --region "${REGION}" --stack-name "${BOOTSTRAP_STACK}" \
  --template-file infra/aws/bootstrap.yaml --no-fail-on-empty-changeset

output() { aws cloudformation describe-stacks --region "${REGION}" --stack-name "$1" --query "Stacks[0].Outputs[?OutputKey=='$2'].OutputValue | [0]" --output text; }
REPOSITORY_URI=$(output "${BOOTSTRAP_STACK}" RepositoryUri)
TABLE_NAME=$(output "${BOOTSTRAP_STACK}" TableName)
TABLE_ARN=$(output "${BOOTSTRAP_STACK}" TableArn)
MANTLE_SECRET_ARN=$(output "${BOOTSTRAP_STACK}" MantleSecretArn)
ACCESS_SECRET_ARN=$(output "${BOOTSTRAP_STACK}" DemoAccessSecretArn)

if [[ -n "${BEDROCK_MANTLE_API_KEY:-}" ]]; then
  .venv/bin/python -c 'import boto3, os, sys; boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"]).put_secret_value(SecretId=sys.argv[1], SecretString=os.environ["BEDROCK_MANTLE_API_KEY"])' "${MANTLE_SECRET_ARN}"
elif aws secretsmanager get-secret-value --region "${REGION}" --secret-id "${MANTLE_SECRET_ARN}" >/dev/null 2>&1; then
  echo "Reusing the existing Bedrock Mantle secret."
else
  read -rsp "Bedrock Mantle API key: " BEDROCK_MANTLE_API_KEY
  echo
  export BEDROCK_MANTLE_API_KEY
  .venv/bin/python -c 'import boto3, os, sys; boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"]).put_secret_value(SecretId=sys.argv[1], SecretString=os.environ["BEDROCK_MANTLE_API_KEY"])' "${MANTLE_SECRET_ARN}"
fi

aws ecr get-login-password --region "${REGION}" | docker login --username AWS --password-stdin "${REPOSITORY_URI%%/*}"
IMAGE_TAG="$(git rev-parse --short=12 HEAD)-$(date -u +%Y%m%d%H%M%S)"
IMAGE_IDENTIFIER="${REPOSITORY_URI}:${IMAGE_TAG}"
docker build --tag "${IMAGE_IDENTIFIER}" .
docker push "${IMAGE_IDENTIFIER}"

aws cloudformation deploy --region "${REGION}" --stack-name "${SERVICE_STACK}" \
  --template-file infra/aws/service.yaml --capabilities CAPABILITY_IAM \
  --parameter-overrides ImageIdentifier="${IMAGE_IDENTIFIER}" TableName="${TABLE_NAME}" TableArn="${TABLE_ARN}" MantleSecretArn="${MANTLE_SECRET_ARN}" DemoAccessSecretArn="${ACCESS_SECRET_ARN}" \
  --no-fail-on-empty-changeset

SERVICE_URL=$(output "${SERVICE_STACK}" ServiceUrl)
echo "Manifest URL: ${SERVICE_URL}/dashboard/"
echo "Access secret ARN: ${ACCESS_SECRET_ARN}"
echo "Run: .venv/bin/python scripts/check_checkpoint_12_ready.py ${SERVICE_URL}"
