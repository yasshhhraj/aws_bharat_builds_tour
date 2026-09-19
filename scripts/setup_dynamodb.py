#!/usr/bin/env python3
"""Create or validate the local Manifest DynamoDB table."""

from __future__ import annotations

import argparse
import os
import time

import boto3
from botocore.exceptions import ClientError


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default=os.getenv("MANIFEST_DYNAMODB_ENDPOINT", "http://127.0.0.1:18000"))
    parser.add_argument("--table", default=os.getenv("MANIFEST_DYNAMODB_TABLE", "manifest-local"))
    parser.add_argument("--wait-seconds", type=float, default=45)
    args = parser.parse_args()
    client = boto3.client(
        "dynamodb", endpoint_url=args.endpoint,
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "local"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "local"),
    )
    deadline = time.monotonic() + args.wait_seconds
    while True:
        try:
            existing = client.list_tables()["TableNames"]
            break
        except Exception:
            if time.monotonic() >= deadline:
                raise SystemExit(f"DynamoDB Local was not ready at {args.endpoint}")
            time.sleep(0.5)
    if args.table not in existing:
        try:
            client.create_table(
                TableName=args.table,
                KeySchema=[
                    {"AttributeName": "PK", "KeyType": "HASH"},
                    {"AttributeName": "SK", "KeyType": "RANGE"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "PK", "AttributeType": "S"},
                    {"AttributeName": "SK", "AttributeType": "S"},
                ],
                BillingMode="PAY_PER_REQUEST",
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "ResourceInUseException":
                raise
        client.get_waiter("table_exists").wait(TableName=args.table)
        print(f"created or found {args.table} at {args.endpoint}")
    else:
        description = client.describe_table(TableName=args.table)["Table"]
        schema = {(item["AttributeName"], item["KeyType"]) for item in description["KeySchema"]}
        if schema != {("PK", "HASH"), ("SK", "RANGE")}:
            raise SystemExit(f"Existing table {args.table} has an incompatible key schema")
        print(f"validated {args.table} at {args.endpoint}")


if __name__ == "__main__":
    main()
