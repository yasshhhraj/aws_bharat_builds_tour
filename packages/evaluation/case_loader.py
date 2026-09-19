"""Validation and loading of labelled evaluation cases."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .models import EvaluationCase


CASE_ID = re.compile(r"^[AB]-[A-Z0-9-]+$")
CLASSIFICATIONS = {"attack", "benign"}
RUNNERS = {"journey", "governor", "approval", "ledger"}
FAMILIES = {
    "approval",
    "cold_chain",
    "journey",
    "ledger",
    "ownership",
    "pii",
    "provenance",
    "separation",
    "spend",
}
SECRET_FRAGMENTS = ("secret", "token", "password", "credential")


class EvaluationCaseError(ValueError):
    """Raised when evaluation evidence would have an untrustworthy catalogue."""


class EvaluationCaseLoader:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (
            Path(__file__).resolve().parents[2] / "fixtures" / "evaluation" / "cases.json"
        )

    def load(self) -> tuple[EvaluationCase, ...]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise EvaluationCaseError(f"Evaluation catalogue {self.path} is missing.") from exc
        except json.JSONDecodeError as exc:
            raise EvaluationCaseError("Evaluation catalogue is not valid JSON.") from exc
        if not isinstance(raw, list):
            raise EvaluationCaseError("Evaluation catalogue must contain a list.")

        cases = tuple(self._parse(item, index) for index, item in enumerate(raw))
        ids = [case.case_id for case in cases]
        duplicates = sorted({case_id for case_id in ids if ids.count(case_id) > 1})
        if duplicates:
            raise EvaluationCaseError(
                f"Duplicate evaluation case IDs: {', '.join(duplicates)}."
            )
        attack_count = sum(case.classification == "attack" for case in cases)
        benign_count = sum(case.classification == "benign" for case in cases)
        if attack_count < 6 or benign_count < 10:
            raise EvaluationCaseError(
                "Evaluation catalogue requires at least 6 attack and 10 benign cases."
            )
        return cases

    def _parse(self, item: Any, index: int) -> EvaluationCase:
        if not isinstance(item, dict):
            raise EvaluationCaseError(f"Evaluation case {index} must be an object.")
        required = {
            "case_id",
            "classification",
            "family",
            "runner",
            "description",
            "input",
            "expected",
        }
        missing = sorted(required - item.keys())
        if missing:
            raise EvaluationCaseError(
                f"Evaluation case {index} is missing: {', '.join(missing)}."
            )
        self._reject_secret_keys(item, f"case[{index}]")
        case_id = str(item["case_id"])
        classification = str(item["classification"])
        family = str(item["family"])
        runner = str(item["runner"])
        description = str(item["description"]).strip()
        if not CASE_ID.fullmatch(case_id):
            raise EvaluationCaseError(f"Invalid evaluation case ID: {case_id}.")
        if classification not in CLASSIFICATIONS:
            raise EvaluationCaseError(f"Invalid classification for {case_id}.")
        expected_prefix = "A-" if classification == "attack" else "B-"
        if not case_id.startswith(expected_prefix):
            raise EvaluationCaseError(
                f"Case {case_id} prefix does not match {classification}."
            )
        if family not in FAMILIES:
            raise EvaluationCaseError(f"Unsupported family {family} for {case_id}.")
        if runner not in RUNNERS:
            raise EvaluationCaseError(f"Unsupported runner {runner} for {case_id}.")
        if not description:
            raise EvaluationCaseError(f"Case {case_id} needs a description.")
        if not isinstance(item["input"], dict) or not isinstance(item["expected"], dict):
            raise EvaluationCaseError(f"Case {case_id} input and expected must be objects.")
        if not item["expected"]:
            raise EvaluationCaseError(f"Case {case_id} needs expected behavior.")
        tags = item.get("tags", [])
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise EvaluationCaseError(f"Case {case_id} tags must be strings.")
        return EvaluationCase(
            case_id=case_id,
            classification=classification,  # type: ignore[arg-type]
            family=family,
            runner=runner,  # type: ignore[arg-type]
            description=description,
            input=dict(item["input"]),
            expected=dict(item["expected"]),
            tags=tuple(tags),
        )

    def _reject_secret_keys(self, value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                normalized = str(key).casefold()
                if any(fragment in normalized for fragment in SECRET_FRAGMENTS):
                    raise EvaluationCaseError(
                        f"Secret-like key {key!r} is not allowed at {path}."
                    )
                self._reject_secret_keys(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                self._reject_secret_keys(child, f"{path}[{index}]")
