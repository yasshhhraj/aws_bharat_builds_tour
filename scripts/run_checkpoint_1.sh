#!/usr/bin/env sh
set -eu

python3 -m pytest
python3 -m apps.runtime.run --order ORD-8842
