#!/usr/bin/env sh
set -eu

echo "Checkpoint 6: full regression suite"
python3 -m pytest -q

echo "Checkpoint 6: preserve Checkpoint 5 gate"
./scripts/run_checkpoint_5.sh

echo "Checkpoint 6: generate measured evaluation evidence"
python3 scripts/run_evaluation.py \
  --seed manifest-checkpoint-6-v1 \
  --warmup 1 \
  --iterations 10 \
  --json-output docs/results/checkpoint-6-evaluation.json \
  --markdown-output docs/results/checkpoint-6-evaluation.md

echo "Checkpoint 6: generate release manifest"
python3 scripts/build_release_manifest.py \
  --evaluation docs/results/checkpoint-6-evaluation.json \
  --output docs/releases/checkpoint-6-local-baseline.json

echo "Checkpoint 6: validate generated evidence"
python3 -c 'import json; from pathlib import Path; data=json.loads(Path("docs/results/checkpoint-6-evaluation.json").read_text()); assert data["summary"]["case_failed"] == 0; assert data["summary"]["attack_total"] >= 6; assert data["summary"]["benign_total"] >= 10'
test -f docs/results/browser-smoke.md
grep -q '^\*\*Status:\*\* PASS$' docs/results/browser-smoke.md

echo "Checkpoint 6 verification complete."
