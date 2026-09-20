#!/usr/bin/env bash
set -euo pipefail

cd /app

required=(
  BEDROCK_MANTLE_API_KEY
  DEMO_ACCESS_SECRET
  DEMO_APPROVER_SECRET
  MANIFEST_DYNAMODB_TABLE
)
for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "Manifest cloud startup is missing required configuration: ${name}." >&2
    exit 2
  fi
done

if [[ "${MANIFEST_DEPLOYMENT_MODE:-}" != "aws" ]]; then
  echo "Manifest cloud startup requires MANIFEST_DEPLOYMENT_MODE=aws." >&2
  exit 2
fi
if [[ -n "${MANIFEST_DYNAMODB_ENDPOINT:-}" ]]; then
  echo "Manifest cloud startup refuses a custom DynamoDB endpoint." >&2
  exit 2
fi
if [[ -n "${AWS_ACCESS_KEY_ID:-}" || -n "${AWS_SECRET_ACCESS_KEY:-}" ]]; then
  echo "Manifest cloud startup requires the App Runner instance role credential chain." >&2
  exit 2
fi
if [[ "${ENABLE_DEMO_TAMPER:-false}" != "false" ]]; then
  echo "Manifest cloud startup requires ENABLE_DEMO_TAMPER=false." >&2
  exit 2
fi

CEDAR_PID=""
API_PID=""
cleanup() {
  [[ -n "${API_PID}" ]] && kill "${API_PID}" 2>/dev/null || true
  [[ -n "${CEDAR_PID}" ]] && kill "${CEDAR_PID}" 2>/dev/null || true
  [[ -n "${API_PID}" ]] && wait "${API_PID}" 2>/dev/null || true
  [[ -n "${CEDAR_PID}" ]] && wait "${CEDAR_PID}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

/app/bin/manifest-cedar-pdp \
  --listen 127.0.0.1:8765 \
  --schema policies/schema/manifest.cedarschema.json \
  --policies policies/demo-v1/manifest.cedar \
  --policy-version demo-v1 &
CEDAR_PID=$!

python scripts/check_cedar_ready.py --endpoint http://127.0.0.1:8765

python -m uvicorn apps.api.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8080}" \
  --no-access-log &
API_PID=$!

wait -n "${CEDAR_PID}" "${API_PID}"
exit_code=$?
echo "Manifest cloud process exited unexpectedly." >&2
exit "${exit_code}"
