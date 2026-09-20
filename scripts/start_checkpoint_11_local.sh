#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)
cd "${PROJECT_ROOT}"

PYTHON="python3"
if [ -x .venv/bin/python ]; then PYTHON=".venv/bin/python"; fi
CEDAR_PORT="${CEDAR_PORT:-18769}"
API_PORT="${MANIFEST_API_PORT:-18080}"
CEDAR_ENDPOINT="http://127.0.0.1:${CEDAR_PORT}"
CEDAR_BINARY="services/cedar_pdp/target/debug/manifest-cedar-pdp"
CEDAR_LOG="${TMPDIR:-/tmp}/manifest-checkpoint-11-cedar.log"
API_LOG="${TMPDIR:-/tmp}/manifest-checkpoint-11-api.log"

# Keep the local demo isolated from Checkpoint 10 live-provider opt-ins.
unset MANIFEST_RUN_LIVE_OPENROUTER MANIFEST_RUN_LIVE_BEDROCK_MANTLE

for command in docker cargo; do
  if ! command -v "${command}" >/dev/null 2>&1; then
    echo "Checkpoint 11 requires ${command} on PATH." >&2
    exit 2
  fi
done
if [ "${DEMO_APPROVER_SECRET:-}" = "replace-with-a-local-demo-value" ] || \
   [ "${DEMO_TAMPER_SECRET:-}" = "replace-with-a-separate-local-demo-value" ]; then
  echo "Refusing placeholder demo secrets from .env.example." >&2
  exit 2
fi
if [ -z "${DEMO_APPROVER_SECRET:-}" ]; then
  DEMO_APPROVER_SECRET=$("${PYTHON}" -c 'import secrets; print(secrets.token_urlsafe(18))')
  export DEMO_APPROVER_SECRET
  GENERATED_APPROVER_SECRET=1
fi
if [ -z "${DEMO_TAMPER_SECRET:-}" ]; then
  DEMO_TAMPER_SECRET=$("${PYTHON}" -c 'import secrets; print(secrets.token_urlsafe(18))')
  export DEMO_TAMPER_SECRET
  GENERATED_TAMPER_SECRET=1
fi

export ENABLE_DEMO_TAMPER="${ENABLE_DEMO_TAMPER:-true}"
export MANIFEST_AGENT_RUNTIME=strands
export MANIFEST_MODEL_PROVIDER=recorded
export MANIFEST_MODEL_ID=manifest-recorded-v1
export MANIFEST_AGENT_MAX_TURNS="${MANIFEST_AGENT_MAX_TURNS:-8}"
export MANIFEST_AGENT_TIMEOUT_SECONDS="${MANIFEST_AGENT_TIMEOUT_SECONDS:-15}"
export MANIFEST_MODEL_MAX_OUTPUT_TOKENS="${MANIFEST_MODEL_MAX_OUTPUT_TOKENS:-1024}"
export MANIFEST_POLICY_ENGINE=cedar
export CEDAR_ENDPOINT
export CEDAR_POLICY_METADATA_PATH=policies/demo-v1/metadata.json
export CEDAR_TIMEOUT_MS="${CEDAR_TIMEOUT_MS:-1000}"
export MANIFEST_STORAGE_BACKEND=dynamodb
export MANIFEST_DYNAMODB_ENDPOINT="${MANIFEST_DYNAMODB_ENDPOINT:-http://127.0.0.1:18000}"
export MANIFEST_DYNAMODB_TABLE="${MANIFEST_DYNAMODB_TABLE:-manifest-local}"
export MANIFEST_DEMO_NAMESPACE="${MANIFEST_DEMO_NAMESPACE:-checkpoint-11-local-demo}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
export AWS_ACCESS_KEY_ID=local
export AWS_SECRET_ACCESS_KEY=local

echo "Checkpoint 11: start pinned DynamoDB Local"
docker compose up -d dynamodb-local
"${PYTHON}" scripts/setup_dynamodb.py
echo "Checkpoint 11: build and start authoritative Cedar"
cargo build --locked --manifest-path services/cedar_pdp/Cargo.toml
"${CEDAR_BINARY}" --listen "127.0.0.1:${CEDAR_PORT}" \
  --schema policies/schema/manifest.cedarschema.json \
  --policies policies/demo-v1/manifest.cedar --policy-version demo-v1 >"${CEDAR_LOG}" 2>&1 &
CEDAR_PID=$!
API_PID=""
cleanup() {
  if [ -n "${API_PID}" ]; then kill "${API_PID}" 2>/dev/null || true; wait "${API_PID}" 2>/dev/null || true; fi
  kill "${CEDAR_PID}" 2>/dev/null || true
  wait "${CEDAR_PID}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM
"${PYTHON}" scripts/check_cedar_ready.py --endpoint "${CEDAR_ENDPOINT}"

echo "Checkpoint 11: start loopback API"
"${PYTHON}" -m uvicorn apps.api.main:app --host 127.0.0.1 --port "${API_PORT}" >"${API_LOG}" 2>&1 &
API_PID=$!
"${PYTHON}" - "${API_PORT}" <<'PY'
import json
import sys
import time
from urllib.request import urlopen

url = f"http://127.0.0.1:{sys.argv[1]}/health/ready"
for _ in range(80):
    try:
        with urlopen(url, timeout=0.5) as response:
            payload = json.load(response)
        if payload.get("status") == "ready":
            break
    except Exception:
        time.sleep(0.1)
else:
    raise SystemExit("Manifest API did not become ready; inspect the API log.")
PY

echo "Manifest local dashboard: http://127.0.0.1:${API_PORT}/dashboard/"
echo "Runtime: Strands + recorded model | Policy: Cedar | Storage: DynamoDB Local"
echo "Data and logistics effects: synthetic and simulated"
if [ "${GENERATED_APPROVER_SECRET:-}" = "1" ]; then echo "Ephemeral approval secret for this process: ${DEMO_APPROVER_SECRET}"; fi
if [ "${GENERATED_TAMPER_SECRET:-}" = "1" ]; then echo "Ephemeral tamper secret for this process: ${DEMO_TAMPER_SECRET}"; fi
echo "Do not include the preceding demo secrets in screenshots or recordings. Press Ctrl-C to stop the API and Cedar."
wait "${API_PID}"
