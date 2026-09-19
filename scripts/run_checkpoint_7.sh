#!/usr/bin/env sh
set -eu

CEDAR_PORT="${CEDAR_PORT:-18765}"
CEDAR_ENDPOINT="http://127.0.0.1:${CEDAR_PORT}"
CEDAR_BINARY="services/cedar_pdp/target/debug/manifest-cedar-pdp"
CEDAR_LOG="${TMPDIR:-/tmp}/manifest-checkpoint-7-cedar.log"

echo "Checkpoint 7: build pinned Cedar sidecar"
cargo build --locked --manifest-path services/cedar_pdp/Cargo.toml
cargo test --locked --manifest-path services/cedar_pdp/Cargo.toml

echo "Checkpoint 7: start and validate Cedar policy service"
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
python3 scripts/check_cedar_ready.py --endpoint "${CEDAR_ENDPOINT}"

export MANIFEST_POLICY_ENGINE=cedar
export CEDAR_ENDPOINT
export CEDAR_TEST_ENDPOINT="${CEDAR_ENDPOINT}"
export CEDAR_POLICY_METADATA_PATH=policies/demo-v1/metadata.json

echo "Checkpoint 7: full regression and live Cedar integration suite"
python3 -m pytest -q

echo "Checkpoint 7: Cedar-authoritative hero journeys"
python3 -m apps.runtime.run --order ORD-8842 --mode enforce --scenario benign
python3 -m apps.runtime.run --order ORD-8842 --mode enforce --scenario adversarial --approval approve
python3 -m apps.runtime.run --order ORD-8842 --mode shadow --scenario adversarial

echo "Checkpoint 7: generate Cedar evaluation evidence"
python3 scripts/run_evaluation.py \
  --policy-engine cedar \
  --seed manifest-checkpoint-7-cedar-v1 \
  --warmup 1 \
  --iterations 10 \
  --json-output docs/results/checkpoint-7-cedar-evaluation.json \
  --markdown-output docs/results/checkpoint-7-cedar-evaluation.md

echo "Checkpoint 7: verify functional parity and release evidence"
python3 -c 'import json; from pathlib import Path; p=json.loads(Path("docs/results/checkpoint-6-evaluation.json").read_text()); c=json.loads(Path("docs/results/checkpoint-7-cedar-evaluation.json").read_text()); assert c["active_modes"]["policy_engine"] == "cedar"; assert c["summary"]["case_failed"] == 0; assert c["functional_digest"] == p["functional_digest"]'
python3 scripts/build_release_manifest.py \
  --evaluation docs/results/checkpoint-7-cedar-evaluation.json \
  --output docs/releases/checkpoint-7-cedar-local.json \
  --test-command ./scripts/run_checkpoint_7.sh

echo "Checkpoint 7 verification complete."

