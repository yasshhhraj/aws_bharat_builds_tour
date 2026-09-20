#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)
cd "${PROJECT_ROOT}"
PYTHON="python3"
if [ -x .venv/bin/python ]; then PYTHON=".venv/bin/python"; fi
CEDAR_PORT="${CEDAR_PORT:-18770}"
CEDAR_ENDPOINT="http://127.0.0.1:${CEDAR_PORT}"
CEDAR_BINARY="services/cedar_pdp/target/debug/manifest-cedar-pdp"
CEDAR_LOG="${TMPDIR:-/tmp}/manifest-checkpoint-11-gate-cedar.log"

# This gate is deliberately offline. Ignore live-provider opt-ins inherited
# from an earlier Checkpoint 10 shell session.
unset MANIFEST_RUN_LIVE_OPENROUTER MANIFEST_RUN_LIVE_BEDROCK_MANTLE

export MANIFEST_AGENT_RUNTIME=strands
export MANIFEST_MODEL_PROVIDER=recorded
export MANIFEST_MODEL_ID=manifest-recorded-v1
export MANIFEST_AGENT_MAX_TURNS=8
export MANIFEST_AGENT_TIMEOUT_SECONDS=15
export MANIFEST_MODEL_MAX_OUTPUT_TOKENS=1024
export MANIFEST_STORAGE_BACKEND=memory
export MANIFEST_DYNAMODB_ENDPOINT="${MANIFEST_DYNAMODB_ENDPOINT:-http://127.0.0.1:18000}"
export MANIFEST_DYNAMODB_TABLE="${MANIFEST_DYNAMODB_TABLE:-manifest-local}"
export MANIFEST_DEMO_NAMESPACE="${MANIFEST_DEMO_NAMESPACE:-checkpoint-11-gate}"
export MANIFEST_DYNAMODB_IMAGE="amazon/dynamodb-local:2.5.4@sha256:cf8cebd061f988628c02daff10fdb950a54478feff9c52f6ddf84710fe3c3906"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
export AWS_ACCESS_KEY_ID=local
export AWS_SECRET_ACCESS_KEY=local

echo "Checkpoint 11: verify pinned dependencies"
"${PYTHON}" -c 'import importlib.metadata; assert importlib.metadata.version("strands-agents") == "1.56.0"'
echo "Checkpoint 11: start pinned DynamoDB Local"
docker compose up -d dynamodb-local
"${PYTHON}" scripts/setup_dynamodb.py
echo "Checkpoint 11: build and test authoritative Cedar"
cargo build --locked --manifest-path services/cedar_pdp/Cargo.toml
cargo test --locked --manifest-path services/cedar_pdp/Cargo.toml
"${CEDAR_BINARY}" --listen "127.0.0.1:${CEDAR_PORT}" \
  --schema policies/schema/manifest.cedarschema.json \
  --policies policies/demo-v1/manifest.cedar --policy-version demo-v1 >"${CEDAR_LOG}" 2>&1 &
CEDAR_PID=$!
cleanup() { kill "${CEDAR_PID}" 2>/dev/null || true; wait "${CEDAR_PID}" 2>/dev/null || true; }
trap cleanup EXIT INT TERM
"${PYTHON}" scripts/check_cedar_ready.py --endpoint "${CEDAR_ENDPOINT}"
export MANIFEST_POLICY_ENGINE=cedar
export CEDAR_ENDPOINT
export CEDAR_TEST_ENDPOINT="${CEDAR_ENDPOINT}"
export CEDAR_POLICY_METADATA_PATH=policies/demo-v1/metadata.json
export CEDAR_TIMEOUT_MS=1000

echo "Checkpoint 11: complete Python regression with live Cedar"
"${PYTHON}" -m pytest -q
echo "Checkpoint 11: shared storage, restart, and concurrency contracts"
MANIFEST_DYNAMODB_TESTS=1 "${PYTHON}" -m pytest -q tests/storage/test_repository_contract.py tests/storage/test_dynamodb_integration.py

export MANIFEST_STORAGE_BACKEND=dynamodb
rehearse() {
  pass_number="$1"
  # A fresh namespace is a clean state without deleting retained evidence from
  # another run. The shell PID keeps two concurrent/local reruns isolated.
  export MANIFEST_DEMO_NAMESPACE="checkpoint-11-rehearsal-${pass_number}-$$"
  echo "Checkpoint 11: automated rehearsal ${pass_number}/2"
  "${PYTHON}" -m apps.runtime.run --order ORD-8842 --mode enforce --scenario benign
  "${PYTHON}" -m apps.runtime.run --order ORD-8842 --mode enforce --scenario adversarial --approval approve
  "${PYTHON}" -m apps.runtime.run --order ORD-8842 --mode enforce --scenario adversarial --approval reject
  "${PYTHON}" -m apps.runtime.run --order ORD-8842 --mode shadow --scenario adversarial
}
rehearse 1
rehearse 2

export MANIFEST_DEMO_NAMESPACE="checkpoint-11-evaluation-$$"
echo "Checkpoint 11: generate separate evaluation evidence"
"${PYTHON}" scripts/run_evaluation.py --policy-engine cedar \
  --seed manifest-checkpoint-11-local-candidate-v1 --warmup 1 --iterations 10 \
  --json-output docs/results/checkpoint-11-local-evaluation.json \
  --markdown-output docs/results/checkpoint-11-local-evaluation.md
echo "Checkpoint 11: verify functional parity"
"${PYTHON}" -c 'import json; from pathlib import Path; p=json.loads(Path("docs/results/checkpoint-9-offline-strands-evaluation.json").read_text()); c=json.loads(Path("docs/results/checkpoint-11-local-evaluation.json").read_text()); assert c["active_modes"]["runtime"] == "strands"; assert c["active_modes"]["model_provider"] == "recorded"; assert c["active_modes"]["policy_engine"] == "cedar"; assert c["active_modes"]["storage"] == "dynamodb_local"; assert c["summary"]["case_failed"] == 0; assert c["functional_digest"] == p["functional_digest"]'
echo "Checkpoint 11: submission hygiene"
"${PYTHON}" scripts/check_submission_hygiene.py
echo "Checkpoint 11: build separate release evidence"
"${PYTHON}" scripts/build_release_manifest.py \
  --evaluation docs/results/checkpoint-11-local-evaluation.json \
  --output docs/releases/checkpoint-11-local-candidate.json \
  --test-command ./scripts/run_checkpoint_11.sh
echo "Checkpoint 11 automated verification complete. Manual browser rehearsals and recording remain owner tasks."
