import json
import os
from pathlib import Path

import pytest

from packages.cedar_adapter import CedarClient, CedarPolicyEngine
from packages.evaluation import EvaluationRunner


ENDPOINT = os.environ.get("CEDAR_TEST_ENDPOINT")
pytestmark = pytest.mark.skipif(not ENDPOINT, reason="CEDAR_TEST_ENDPOINT is not set")


def cedar_engine():
    engine = CedarPolicyEngine(
        CedarClient(str(ENDPOINT), timeout_ms=500),
        metadata_path=Path("policies/demo-v1/metadata.json"),
    )
    engine.validate_startup()
    return engine


def test_live_cedar_health_is_validated():
    details = cedar_engine().describe()
    assert details["policy_engine"] == "cedar"
    assert details["policy_fallback_active"] is False
    assert str(details["policy_bundle_hash"]).startswith("sha256:")


def test_live_cedar_matches_checkpoint_6_functional_digest():
    expected = json.loads(
        Path("docs/results/checkpoint-6-evaluation.json").read_text(encoding="utf-8")
    )["functional_digest"]
    report = EvaluationRunner(engine_factory=cedar_engine).run(
        seed="manifest-checkpoint-7-live-test", warmup=0, iterations=1
    )
    assert report.summary["case_passed"] == report.summary["case_total"] == 22
    assert report.functional_digest == expected

