#!/usr/bin/env python3
import argparse
import json
from urllib.request import urlopen


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    args = parser.parse_args()
    with urlopen(args.url.rstrip("/") + "/health/ready", timeout=20) as response:
        body = json.load(response)
    expected = {
        "status": "ready",
        "deployment_mode": "aws",
        "runtime_mode": "strands",
        "model_provider": "bedrock_mantle",
        "requested_model_id": "qwen.qwen3-coder-next",
        "policy_engine": "cedar",
        "storage_mode": "dynamodb_aws",
        "provider_fallback_active": False,
        "demo_access_required": True,
        "demo_access_ready": True,
        "demo_tamper_enabled": False,
    }
    mismatches = {key: {"expected": value, "actual": body.get(key)} for key, value in expected.items() if body.get(key) != value}
    if mismatches:
        print(json.dumps({"status": "not_ready", "mismatches": mismatches}, sort_keys=True))
        return 1
    print(json.dumps({"status": "ready", "provider": body["model_provider"], "model": body["requested_model_id"], "policy": body["policy_engine"], "storage": body["storage_mode"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
