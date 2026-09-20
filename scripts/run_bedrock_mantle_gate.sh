#!/usr/bin/env sh
set -eu

PYTHON="python3"
if [ -x .venv/bin/python ]; then PYTHON=".venv/bin/python"; fi
MODE="${1:---offline}"

run_offline() {
  echo "Bedrock Mantle: no-network provider contract"
  MANIFEST_AGENT_RUNTIME=strands MANIFEST_MODEL_PROVIDER=recorded \
  MANIFEST_MODEL_ID=manifest-recorded-v1 "${PYTHON}" -m pytest -q \
    tests/agents tests/integration/test_strands_provider_runtime.py \
    tests/integration/test_strands_recorded_runtime.py
}

require_live_opt_in() {
  if [ "${MANIFEST_RUN_LIVE_BEDROCK_MANTLE:-}" != "1" ]; then
    echo "Refusing paid Bedrock calls without MANIFEST_RUN_LIVE_BEDROCK_MANTLE=1." >&2
    exit 2
  fi
  if [ -z "${BEDROCK_MANTLE_API_KEY:-}" ]; then
    echo "BEDROCK_MANTLE_API_KEY is missing from this process environment." >&2
    exit 2
  fi
}

run_live() {
  selector="$1"
  require_live_opt_in
  CEDAR_PORT="${CEDAR_PORT:-18768}"
  CEDAR_ENDPOINT="http://127.0.0.1:${CEDAR_PORT}"
  CEDAR_BINARY="services/cedar_pdp/target/debug/manifest-cedar-pdp"
  CEDAR_LOG="${TMPDIR:-/tmp}/manifest-bedrock-mantle-cedar.log"
  export MANIFEST_AGENT_RUNTIME=strands
  export MANIFEST_MODEL_PROVIDER=bedrock_mantle
  export MANIFEST_MODEL_ID="${MANIFEST_MODEL_ID:-qwen.qwen3-coder-next}"
  export MANIFEST_BEDROCK_REGION="${MANIFEST_BEDROCK_REGION:-us-east-1}"
  export MANIFEST_AGENT_MAX_TURNS="${MANIFEST_AGENT_MAX_TURNS:-8}"
  export MANIFEST_AGENT_TIMEOUT_SECONDS="${MANIFEST_AGENT_TIMEOUT_SECONDS:-60}"
  export MANIFEST_MODEL_MAX_OUTPUT_TOKENS="${MANIFEST_MODEL_MAX_OUTPUT_TOKENS:-1024}"
  export MANIFEST_STORAGE_BACKEND=memory

  echo "Bedrock Mantle: verify key, region, and model discovery without inference"
  "${PYTHON}" scripts/check_bedrock_mantle_ready.py
  echo "Bedrock Mantle: build and start authoritative Cedar"
  cargo build --locked --manifest-path services/cedar_pdp/Cargo.toml
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
  if [ "${selector}" = "probe" ]; then
    echo "Bedrock Mantle: paid governed Inventory probe"
    "${PYTHON}" -m pytest -q -x tests/integration/test_openrouter_live.py::test_openrouter_inventory_probe_uses_governed_read_tools
  else
    echo "Bedrock Mantle: paid governed live gate"
    "${PYTHON}" -m pytest -q -x tests/integration/test_openrouter_live.py
  fi
}

case "${MODE}" in
  --offline) run_offline ;;
  --probe) run_live probe ;;
  --live) run_live all ;;
  *) echo "Usage: $0 --offline|--probe|--live" >&2; exit 2 ;;
esac
