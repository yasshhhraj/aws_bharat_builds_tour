#!/usr/bin/env sh
set -eu

python3 -m pytest -q
python3 -m apps.runtime.run --order ORD-8842 --mode enforce --scenario benign
python3 -m apps.runtime.run --order ORD-8842 --mode enforce --scenario adversarial
python3 -m apps.runtime.run --order ORD-8842 --mode shadow --scenario adversarial
