#!/usr/bin/env python3
"""Fail on high-confidence secret leaks and stale submission-facing claims."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".css", ".html", ".js", ".json", ".md", ".py", ".sh", ".toml", ".yaml", ".yml"}
SKIP_PARTS = {".git", ".venv", "__pycache__", "target", ".pytest_cache"}
SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "OpenRouter key": re.compile(r"\bsk-or-v1-[A-Za-z0-9_-]{20,}\b"),
    "bearer token": re.compile(r"\bAuthorization\s*:\s*Bearer\s+[A-Za-z0-9._~-]{20,}", re.I),
}
SUBMISSION_SURFACES = (
    ROOT / "README.md",
    ROOT / "docs" / "FOLLOWUP_CHECKPOINTS_TO_COMPLETION.md",
    ROOT / "docs" / "PROGRESS_SUBMISSION_REPORT.md",
    ROOT / "apps" / "api" / "main.py",
    ROOT / "apps" / "dashboard" / "static" / "index.html",
)
STALE_PATTERNS = {
    "stale API checkpoint title": re.compile(r"Manifest Checkpoint 7 API"),
    "stale branch status": re.compile(r"complete on the `checkpoint-9-offline-strands` branch"),
    "stale missing-Strands claim": re.compile(r"Strands, Bedrock, DynamoDB.*remain incomplete", re.I),
}


def candidate_files() -> list[Path]:
    output = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    files: list[Path] = []
    for relative in output.splitlines():
        path = ROOT / relative
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        files.append(path)
    return files


def main() -> int:
    failures: list[str] = []
    for path in candidate_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                failures.append(f"{path.relative_to(ROOT)}: possible {label}")

    for path in SUBMISSION_SURFACES:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"/home/[A-Za-z0-9._-]+/", text):
            failures.append(f"{path.relative_to(ROOT)}: personal absolute path")
        for label, pattern in STALE_PATTERNS.items():
            if pattern.search(text):
                failures.append(f"{path.relative_to(ROOT)}: {label}")

    dashboard = ROOT / "apps" / "dashboard" / "static" / "index.html"
    if re.search(r"(?:src|href)=[\"']https?://", dashboard.read_text(encoding="utf-8")):
        failures.append("apps/dashboard/static/index.html: external asset URL")

    if failures:
        print("Checkpoint 11 submission hygiene failed:")
        for failure in sorted(set(failures)):
            print(f"- {failure}")
        return 1
    print("Checkpoint 11 submission hygiene passed: no high-confidence leak or stale surface claim found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
