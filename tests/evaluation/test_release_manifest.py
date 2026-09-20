import json
from pathlib import Path

from packages.evaluation import EvaluationRunner
from packages.evaluation.release_manifest import (
    build_release_manifest,
    fixture_tree_digest,
    write_release_manifest,
)
from packages.evaluation.report import write_report


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_fixture_digest_ignores_json_whitespace_and_key_order(tmp_path):
    root = tmp_path / "fixtures"
    root.mkdir()
    path = root / "case.json"
    path.write_text('{"a":1,"b":2}\n', encoding="utf-8")
    first = fixture_tree_digest(root)
    path.write_text('{\n  "b": 2,\n  "a": 1\n}\n', encoding="utf-8")
    second = fixture_tree_digest(root)
    assert first == second


def test_fixture_digest_changes_for_value_or_path(tmp_path):
    root = tmp_path / "fixtures"
    root.mkdir()
    path = root / "case.json"
    path.write_text('{"value":1}', encoding="utf-8")
    first = fixture_tree_digest(root)
    path.write_text('{"value":2}', encoding="utf-8")
    second = fixture_tree_digest(root)
    path.rename(root / "renamed.json")
    third = fixture_tree_digest(root)
    assert first["digest"] != second["digest"]
    assert second["digest"] != third["digest"]


def test_release_manifest_binds_source_fixtures_modes_tests_and_evaluation(tmp_path):
    report = EvaluationRunner().run(warmup=0, iterations=1)
    evidence_dir = PROJECT_ROOT / "docs" / "results"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evaluation_path = evidence_dir / "test-release-evaluation.json"
    markdown_path = tmp_path / "unused.md"
    try:
        write_report(report, evaluation_path, markdown_path)
        manifest = build_release_manifest(
            repo_root=PROJECT_ROOT, evaluation_path=evaluation_path
        )
    finally:
        evaluation_path.unlink(missing_ok=True)

    assert manifest["schema_version"] == "manifest-release-v1"
    assert manifest["source"]["commit"]
    assert isinstance(manifest["source"]["dirty"], bool)
    assert manifest["fixture_tree"]["digest"].startswith("sha256:")
    assert manifest["policy"] == {"engine": "python_reference", "version": "demo-v1"}
    assert manifest["evaluation"]["functional_digest"] == report.functional_digest
    assert manifest["runtime"]["requested_model_id"] == "manifest-recorded-v1"
    assert manifest["runtime"]["resolved_model_id"] == "manifest-recorded-v1"
    assert manifest["tests"]["collected"] >= 94
    assert manifest["tests"]["failed"] == 0
    assert "secret" not in json.dumps(manifest).casefold()

    output = tmp_path / "release.json"
    write_release_manifest(output, manifest)
    assert json.loads(output.read_text(encoding="utf-8")) == manifest
