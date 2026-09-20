#!/usr/bin/env python3
import argparse
import getpass
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen


def call(base, method, path, secret, body=None, *, approval=False):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Accept": "application/json", "X-Manifest-Demo-Secret": secret}
    if approval:
        headers["X-Demo-Approver-Secret"] = secret
    if body is not None:
        headers["Content-Type"] = "application/json"
    with urlopen(Request(base + path, data=data, headers=headers, method=method), timeout=240) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--output", default="docs/results/checkpoint-12-deployed-smoke.json")
    args = parser.parse_args()
    base = args.url.rstrip("/")
    secret = os.getenv("DEMO_ACCESS_SECRET") or getpass.getpass("Demo access secret: ")
    benign = call(base, "POST", "/v1/runs", secret, {"order_id":"ORD-8842","mode":"enforce","scenario":"benign"})
    adversarial = call(base, "POST", "/v1/runs", secret, {"order_id":"ORD-8842","mode":"enforce","scenario":"adversarial"})
    approval = call(base, "GET", f"/v1/approvals/{adversarial['pending_approval_id']}", secret)
    decided = call(base, "POST", f"/v1/approvals/{approval['approval_id']}", secret, {"decision":"approve","approver_label":"DEMO-APPROVER-AWS-1","comment":"Checkpoint 12 deployed smoke","expected_version":approval["version"],"idempotency_key":"checkpoint-12-deployed-approve-001"}, approval=True)
    verification = call(base, "GET", f"/v1/traces/{adversarial['trace_id']}/verify", secret)
    projection = call(base, "GET", f"/v1/traces/{adversarial['trace_id']}/projection", secret)
    assert benign["status"] == "completed"
    assert decided["run"]["status"] == "completed"
    assert verification["valid"] is True
    assert projection["booking_confirmation_count"] == 1
    assert projection["notification_count"] == 1
    evidence = {"schema_version":"manifest-checkpoint-12-smoke-v1","base_url":base,"benign_trace_id":benign["trace_id"],"adversarial_trace_id":adversarial["trace_id"],"benign_status":benign["status"],"approved_status":decided["run"]["status"],"ledger_valid":True,"booking_confirmation_count":1,"notification_count":1}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps(evidence, sort_keys=True))


if __name__ == "__main__":
    main()
