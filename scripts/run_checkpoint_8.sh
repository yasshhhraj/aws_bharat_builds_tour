#!/usr/bin/env sh
set -eu

PYTHON="python3"
if [ -x .venv/bin/python ]; then
  PYTHON=".venv/bin/python"
fi

CEDAR_PORT="${CEDAR_PORT:-18766}"
CEDAR_ENDPOINT="http://127.0.0.1:${CEDAR_PORT}"
CEDAR_BINARY="services/cedar_pdp/target/debug/manifest-cedar-pdp"
CEDAR_LOG="${TMPDIR:-/tmp}/manifest-checkpoint-8-cedar.log"

export MANIFEST_DYNAMODB_ENDPOINT="${MANIFEST_DYNAMODB_ENDPOINT:-http://127.0.0.1:18000}"
export MANIFEST_DYNAMODB_TABLE="${MANIFEST_DYNAMODB_TABLE:-manifest-local}"
export MANIFEST_DEMO_NAMESPACE="${MANIFEST_DEMO_NAMESPACE:-checkpoint-8-gate}"
export MANIFEST_DYNAMODB_IMAGE="amazon/dynamodb-local:2.5.4@sha256:cf8cebd061f988628c02daff10fdb950a54478feff9c52f6ddf84710fe3c3906"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-local}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-local}"

echo "Checkpoint 8: start pinned DynamoDB Local"
docker compose up -d dynamodb-local
"${PYTHON}" scripts/setup_dynamodb.py

echo "Checkpoint 8: build and start pinned Cedar sidecar"
cargo build --locked --manifest-path services/cedar_pdp/Cargo.toml
cargo test --locked --manifest-path services/cedar_pdp/Cargo.toml
"${CEDAR_BINARY}" \
  --listen "127.0.0.1:${CEDAR_PORT}" \
  --schema policies/schema/manifest.cedarschema.json \
  --policies policies/demo-v1/manifest.cedar \
  --policy-version demo-v1 >"${CEDAR_LOG}" 2>&1 &
CEDAR_PID=$!
cleanup() {
  kill "${CEDAR_PID}" 2>/dev/null || true
  wait "${CEDAR_PID}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM
"${PYTHON}" scripts/check_cedar_ready.py --endpoint "${CEDAR_ENDPOINT}"

export MANIFEST_POLICY_ENGINE=cedar
export CEDAR_ENDPOINT
export CEDAR_TEST_ENDPOINT="${CEDAR_ENDPOINT}"
export CEDAR_POLICY_METADATA_PATH=policies/demo-v1/metadata.json

echo "Checkpoint 8: full regression with live Cedar"
"${PYTHON}" -m pytest -q

echo "Checkpoint 8: shared storage and restart/concurrency suite"
MANIFEST_DYNAMODB_TESTS=1 "${PYTHON}" -m pytest -q \
  tests/storage/test_repository_contract.py \
  tests/storage/test_dynamodb_integration.py

echo "Checkpoint 8: DynamoDB + Cedar hero journeys"
export MANIFEST_STORAGE_BACKEND=dynamodb
"${PYTHON}" -m apps.runtime.run --order ORD-8842 --mode enforce --scenario benign
"${PYTHON}" -m apps.runtime.run --order ORD-8842 --mode enforce --scenario adversarial --approval approve
"${PYTHON}" -m apps.runtime.run --order ORD-8842 --mode shadow --scenario adversarial

echo "Checkpoint 8: generate durable Cedar evaluation evidence"
"${PYTHON}" scripts/run_evaluation.py \
  --policy-engine cedar \
  --seed manifest-checkpoint-8-dynamodb-v1 \
  --warmup 1 \
  --iterations 10 \
  --json-output docs/results/checkpoint-8-dynamodb-evaluation.json \
  --markdown-output docs/results/checkpoint-8-dynamodb-evaluation.md

echo "Checkpoint 8: verify parity and build release evidence"
"${PYTHON}" -c 'import json; from pathlib import Path; p=json.loads(Path("docs/results/checkpoint-7-cedar-evaluation.json").read_text()); c=json.loads(Path("docs/results/checkpoint-8-dynamodb-evaluation.json").read_text()); assert c["active_modes"]["policy_engine"] == "cedar"; assert c["active_modes"]["storage"] == "dynamodb_local"; assert c["summary"]["case_failed"] == 0; assert c["functional_digest"] == p["functional_digest"]'
"${PYTHON}" scripts/build_release_manifest.py \
  --evaluation docs/results/checkpoint-8-dynamodb-evaluation.json \
  --output docs/releases/checkpoint-8-dynamodb-local.json \
  --test-command ./scripts/run_checkpoint_8.sh

echo "Checkpoint 8 verification complete. DynamoDB Local remains running; Cedar was stopped."
