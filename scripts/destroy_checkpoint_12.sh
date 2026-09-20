#!/usr/bin/env bash
set -euo pipefail
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
SERVICE_STACK="${MANIFEST_SERVICE_STACK:-manifest-stage-service}"
BOOTSTRAP_STACK="${MANIFEST_BOOTSTRAP_STACK:-manifest-stage-bootstrap}"
aws cloudformation delete-stack --region "${REGION}" --stack-name "${SERVICE_STACK}"
aws cloudformation wait stack-delete-complete --region "${REGION}" --stack-name "${SERVICE_STACK}"
aws cloudformation delete-stack --region "${REGION}" --stack-name "${BOOTSTRAP_STACK}"
aws cloudformation wait stack-delete-complete --region "${REGION}" --stack-name "${BOOTSTRAP_STACK}"
echo "Manifest App Runner, DynamoDB, ECR, IAM roles, and secrets were deleted."
