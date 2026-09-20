#!/usr/bin/env sh
set -eu

echo "Deprecated: use scripts/run_checkpoint_10_bedrock_mantle.sh for the historical provider gate." >&2
exec "$(dirname "$0")/run_bedrock_mantle_gate.sh" "$@"
