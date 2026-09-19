from packages.evaluation import EvaluationRunner
import packages.evaluation.runner as runner_module


def test_repeated_runs_have_the_same_functional_and_catalogue_digests():
    first = EvaluationRunner().run(warmup=0, iterations=1)
    second = EvaluationRunner().run(warmup=0, iterations=1)
    assert first.case_catalog_digest == second.case_catalog_digest
    assert first.functional_digest == second.functional_digest
    assert first.summary == second.summary


def test_latency_is_separate_from_functional_digest():
    report = EvaluationRunner().run(warmup=0, iterations=2)
    assert report.summary["case_total"] == 22
    assert report.latency["policy_ms"]["count"] > 22
    assert report.latency["end_to_end_ms"]["count"] == 44
    assert report.latency["policy_ms"]["p95"] >= report.latency["policy_ms"]["p50"]
    assert report.latency["end_to_end_ms"]["p95"] >= report.latency["end_to_end_ms"]["p50"]


def test_one_case_executor_failure_is_reported_without_losing_denominators(monkeypatch):
    original = runner_module.execute_case

    def fail_one(case):
        if case.case_id == "A-PROV-MISSING":
            raise RuntimeError("synthetic executor failure")
        return original(case)

    monkeypatch.setattr(runner_module, "execute_case", fail_one)
    report = EvaluationRunner().run(warmup=0, iterations=1)
    failed = [item for item in report.cases if not item.passed]
    assert report.summary["case_total"] == 22
    assert [item.case.case_id for item in failed] == ["A-PROV-MISSING"]
    assert "RuntimeError" in failed[0].failure_summary
