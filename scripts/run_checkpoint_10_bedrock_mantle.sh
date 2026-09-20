#!/usr/bin/env sh
set -eu

# Historical Checkpoint 10 entry point retained for reproducible evidence.
exec "$(dirname "$0")/run_bedrock_mantle_gate.sh" "$@"
