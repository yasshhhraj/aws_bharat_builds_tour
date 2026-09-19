import json
from pathlib import Path

import pytest

from packages.evaluation.case_loader import EvaluationCaseError, EvaluationCaseLoader


CATALOGUE = Path(__file__).resolve().parents[2] / "fixtures" / "evaluation" / "cases.json"


def write_catalogue(tmp_path, value):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_catalogue_has_unique_minimum_attack_and_benign_cases():
    cases = EvaluationCaseLoader().load()
    assert len(cases) == 22
    assert len({case.case_id for case in cases}) == len(cases)
    assert sum(case.classification == "attack" for case in cases) == 10
    assert sum(case.classification == "benign" for case in cases) == 12


def test_duplicate_case_id_is_rejected(tmp_path):
    value = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    value.append(dict(value[0]))
    with pytest.raises(EvaluationCaseError, match="Duplicate"):
        EvaluationCaseLoader(write_catalogue(tmp_path, value)).load()


def test_prefix_and_classification_must_agree(tmp_path):
    value = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    value[0]["classification"] = "benign"
    with pytest.raises(EvaluationCaseError, match="prefix"):
        EvaluationCaseLoader(write_catalogue(tmp_path, value)).load()


def test_secret_like_keys_are_rejected(tmp_path):
    value = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    value[0]["input"]["api_token"] = "unsafe"
    with pytest.raises(EvaluationCaseError, match="Secret-like"):
        EvaluationCaseLoader(write_catalogue(tmp_path, value)).load()


def test_minimum_denominators_are_enforced(tmp_path):
    value = json.loads(CATALOGUE.read_text(encoding="utf-8"))[:5]
    with pytest.raises(EvaluationCaseError, match="at least 6 attack and 10 benign"):
        EvaluationCaseLoader(write_catalogue(tmp_path, value)).load()
