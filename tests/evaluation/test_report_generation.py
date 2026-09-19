import json
from dataclasses import replace

import pytest

from packages.evaluation import EvaluationRunner
from packages.evaluation.report import render_json, render_markdown, write_report


def test_json_and_markdown_reports_share_exact_denominators(tmp_path):
    report = EvaluationRunner().run(warmup=0, iterations=1)
    json_path = tmp_path / "evaluation.json"
    markdown_path = tmp_path / "evaluation.md"
    write_report(report, json_path, markdown_path)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert payload["summary"]["attack_detected"] == 10
    assert payload["summary"]["attack_total"] == 10
    assert payload["summary"]["benign_passed"] == 12
    assert payload["summary"]["benign_total"] == 12
    assert "10/10 (100.0%)" in markdown
    assert "12/12 (100.0%)" in markdown
    assert markdown.endswith("\n")


def test_rendered_json_rejects_secret_like_keys():
    report = EvaluationRunner().run(warmup=0, iterations=1)
    unsafe = replace(report, active_modes={"api_secret": "unsafe"})
    with pytest.raises(ValueError, match="Forbidden key"):
        render_json(unsafe)


def test_reports_disclose_local_reference_modes():
    report = EvaluationRunner().run(warmup=0, iterations=1)
    markdown = render_markdown(report)
    assert report.active_modes["policy_engine"] == "python_reference"
    assert report.active_modes["storage"] == "memory_hash_chain"
    assert report.active_modes["deployment"] == "local"
    assert "Cedar is not active" in markdown
