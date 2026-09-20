#!/usr/bin/env bash
set -euo pipefail
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
STACK="${MANIFEST_SERVICE_STACK:-manifest-stage-service}"
ARN=$(aws cloudformation describe-stacks --region "${REGION}" --stack-name "${STACK}" --query "Stacks[0].Outputs[?OutputKey=='ServiceArn'].OutputValue | [0]" --output text)
aws apprunner pause-service --region "${REGION}" --service-arn "${ARN}"
