#!/usr/bin/env python3
"""Wait briefly for the local Checkpoint 7 Cedar sidecar."""

from __future__ import annotations

import argparse
import json
import time
from urllib.error import URLError
from urllib.request import urlopen


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--attempts", type=int, default=50)
    args = parser.parse_args()
    endpoint = args.endpoint.rstrip("/")
    if not endpoint.startswith(("http://127.0.0.1:", "http://localhost:")):
        parser.error("endpoint must use loopback HTTP")
    for _ in range(args.attempts):
        try:
            with urlopen(f"{endpoint}/health/ready", timeout=0.2) as response:
                value = json.loads(response.read(65_537))
            if (
                value.get("status") == "ready"
                and value.get("engine") == "cedar"
                and value.get("validation") == "passed"
            ):
                print(
                    f"Cedar ready: {value['cedar_version']} "
                    f"{value['bundle_hash']}"
                )
                return 0
        except (OSError, URLError, ValueError, KeyError):
            pass
        time.sleep(0.1)
    print("Cedar sidecar did not become ready.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

