#!/usr/bin/env sh
set -eu

echo "Checkpoint 5: full regression suite"
python3 -m pytest -q

echo "Checkpoint 5: focused dashboard and projection contracts"
python3 -m pytest -q \
  tests/unit/test_dashboard_projection.py \
  tests/e2e/test_checkpoint_5_dashboard.py

echo "Checkpoint 5: primary CLI journeys"
python3 -m apps.runtime.run --order ORD-8842 --mode enforce --scenario benign
python3 -m apps.runtime.run --order ORD-8842 --mode enforce --scenario adversarial
python3 -m apps.runtime.run --order ORD-8842 --mode enforce --scenario adversarial --approval approve

echo "Checkpoint 5 verification complete."
