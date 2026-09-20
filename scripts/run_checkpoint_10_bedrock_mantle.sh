#!/usr/bin/env sh
set -eu

# Canonical Checkpoint 10 entry point after the live-provider pivot.
exec "$(dirname "$0")/run_checkpoint_12_bedrock_mantle.sh" "$@"
