"""Generate a safe manifest that binds source, fixtures, modes, and evidence."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .report import write_atomic


RELEASE_SCHEMA_VERSION = "manifest-release-v1"


def fixture_tree_digest(fixture_root: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    files = tuple(
        path
        for path in sorted(fixture_root.rglob("*"))
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    )
    for path in files:
        relative = path.relative_to(fixture_root).as_posix()
        raw = path.read_bytes()
        if path.suffix == ".json":
            value = json.loads(raw.decode("utf-8"))
            raw = json.dumps(
                value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode("utf-8")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(raw)
        digest.update(b"\0")
    return {
        "algorithm": "sha256",
        "digest": "sha256:" + digest.hexdigest(),
        "file_count": len(files),
    }


def _git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def source_metadata(repo_root: Path) -> dict[str, Any]:
    commit = _git(repo_root, "rev-parse", "HEAD")
    branch = _git(repo_root, "branch", "--show-current") or "detached"
    status = _git(repo_root, "status", "--porcelain=v1")
    dirty = bool(status)
    metadata: dict[str, Any] = {
        "commit": commit,
        "branch": branch,
        "dirty": dirty,
    }
    if dirty:
        digest = hashlib.sha256()
        digest.update(status.encode("utf-8"))
        digest.update(b"\0")
        tracked_diff = subprocess.run(
            ["git", "diff", "--binary", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
        ).stdout
        digest.update(tracked_diff)
        for line in status.splitlines():
            if not line.startswith("?? "):
                continue
            relative = line[3:]
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
        metadata["diff_fingerprint"] = "sha256:" + digest.hexdigest()
    return metadata


def dependency_versions(names: tuple[str, ...] = ("boto3", "fastapi", "uvicorn", "httpx", "pytest")) -> dict[str, str]:
    versions: dict[str, str] = {}
    for name in names:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "not-installed"
    return versions


def collected_test_count(repo_root: Path) -> int:
    result = subprocess.run(
        ["python3", "-m", "pytest", "--collect-only", "-q"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    match = re.search(r"(\d+) tests collected", result.stdout)
    if match is None:
        raise ValueError("Could not determine the collected pytest count.")
    return int(match.group(1))


def build_release_manifest(
    *,
    repo_root: Path,
    evaluation_path: Path,
    test_status: str = "passed",
    test_command: str = "./scripts/run_checkpoint_6.sh",
) -> dict[str, Any]:
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    if evaluation.get("schema_version") != "manifest-evaluation-v1":
        raise ValueError("Evaluation evidence has an unsupported schema version.")
    summary = evaluation.get("summary", {})
    if summary.get("case_failed") != 0:
        raise ValueError("A release manifest cannot bind failing evaluation evidence.")
    if test_status != "passed":
        raise ValueError("A release manifest requires a passing test status.")
    try:
        package_version = importlib.metadata.version("manifest-governor")
    except importlib.metadata.PackageNotFoundError:
        package_version = "0.7.0"
    active_modes = evaluation.get("active_modes", {})
    policy = {
        "engine": str(active_modes.get("policy_engine", "unknown")),
        "version": str(active_modes.get("policy_version", "unknown")),
    }
    for key in ("policy_bundle_hash", "policy_schema_hash", "cedar_runtime_version"):
        if active_modes.get(key):
            policy[key] = str(active_modes[key])
    storage_mode = str(active_modes.get("storage", "memory_hash_chain"))
    limitations = [
        "Synthetic logistics data and effects only.",
        "Deterministic Python agents; Strands and Bedrock are not active.",
        (
            "DynamoDB Local is durable across application restart but is not a managed production deployment."
            if storage_mode.startswith("dynamodb")
            else "In-memory storage; runs and approvals do not survive restart."
        ),
        "Tamper-evident hash chain, not an immutable ledger.",
        "Local deployment only.",
    ]
    if policy["engine"] == "python_reference":
        limitations.insert(1, "Python reference policy engine; Cedar is not active.")
    elif policy["engine"] == "cedar":
        limitations.insert(1, "Cedar policy engine runs as a local loopback sidecar.")
    return {
        "schema_version": RELEASE_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": source_metadata(repo_root),
        "python": {"version": platform.python_version()},
        "package": {"name": "manifest-governor", "version": package_version},
        "dependencies": dependency_versions(),
        "fixture_tree": fixture_tree_digest(repo_root / "fixtures"),
        "policy": policy,
        "runtime": {"mode": "deterministic"},
        "storage": {
            "mode": storage_mode,
            **(
                {
                    "table": os.getenv("MANIFEST_DYNAMODB_TABLE", "manifest-local"),
                    "namespace": os.getenv("MANIFEST_DEMO_NAMESPACE", "local-demo"),
                    "local_image": os.getenv(
                        "MANIFEST_DYNAMODB_IMAGE", "not-recorded"
                    ),
                }
                if storage_mode.startswith("dynamodb") else {}
            ),
        },
        "approval": {"mode": "local"},
        "dashboard": {"mode": "static_no_build"},
        "deployment": {"mode": "local"},
        "evaluation": {
            "schema_version": evaluation["schema_version"],
            "case_catalog_digest": evaluation["case_catalog_digest"],
            "functional_digest": evaluation["functional_digest"],
            "result_path": evaluation_path.resolve().relative_to(repo_root.resolve()).as_posix(),
            "case_total": summary["case_total"],
            "case_passed": summary["case_passed"],
        },
        "tests": {
            "command": test_command,
            "status": test_status,
            "collected": collected_test_count(repo_root),
            "failed": 0,
        },
        "limitations": limitations,
    }


def write_release_manifest(path: Path, manifest: dict[str, Any]) -> None:
    content = json.dumps(
        manifest, indent=2, sort_keys=True, allow_nan=False
    ) + "\n"
    write_atomic(path, content)
