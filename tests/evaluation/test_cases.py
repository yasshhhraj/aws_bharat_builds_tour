from packages.evaluation import EvaluationRunner


def test_all_attack_cases_detect_declared_violation_or_tamper():
    report = EvaluationRunner().run(warmup=0, iterations=1)
    attacks = [item for item in report.cases if item.case.classification == "attack"]
    assert len(attacks) == 10
    assert all(item.passed for item in attacks)
    assert report.summary["attack_detected"] == 10
    assert report.summary["synthetic_value_subject_to_approval_minor"] == 90000


def test_all_benign_and_boundary_cases_have_expected_behavior():
    report = EvaluationRunner().run(warmup=0, iterations=1)
    benign = [item for item in report.cases if item.case.classification == "benign"]
    assert len(benign) == 12
    assert all(item.passed for item in benign)
    assert report.summary["false_positive_count"] == 0


def test_guide_back_observes_safe_final_state():
    report = EvaluationRunner().run(warmup=0, iterations=1)
    guided = {
        item.case.case_id: item.observation
        for item in report.cases
        if item.case.expected.get("guide_back_succeeded") is True
    }
    assert guided["A-PROV-DRIFT"].details["final_weight_kg"] == 500
    assert guided["A-COLD-CARRIER"].details["selected_carrier_id"] == "CARRIER-COLD-01"
    assert all(item.guide_back_succeeded is True for item in guided.values())


def test_unsafe_pii_is_redacted_from_trace_evidence():
    report = EvaluationRunner().run(warmup=0, iterations=1)
    pii = next(item for item in report.cases if item.case.case_id == "A-PII-RAW")
    assert pii.passed
    assert pii.observation.details["trace_redacted"] is True
