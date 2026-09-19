"""Exact-denominator and latency calculations for evaluation evidence."""

from __future__ import annotations

import math
from collections import Counter
from statistics import fmean
from typing import Iterable

from .models import CaseResult


def _valid_samples(samples: Iterable[float]) -> tuple[float, ...]:
    values = tuple(samples)
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Latency samples must be numeric.")
        if not math.isfinite(value) or value < 0:
            raise ValueError("Latency samples must be finite and non-negative.")
    return tuple(float(value) for value in values)


def nearest_rank_percentile(samples: Iterable[float], percentile: float) -> float:
    values = sorted(_valid_samples(samples))
    if not values:
        raise ValueError("A percentile requires at least one sample.")
    if not 0 < percentile <= 1:
        raise ValueError("Percentile must be greater than 0 and at most 1.")
    rank = max(math.ceil(percentile * len(values)) - 1, 0)
    return values[rank]


def latency_summary(samples: Iterable[float]) -> dict[str, float | int]:
    values = _valid_samples(samples)
    if not values:
        raise ValueError("A latency summary requires at least one sample.")
    return {
        "count": len(values),
        "min": round(min(values), 3),
        "max": round(max(values), 3),
        "mean": round(fmean(values), 3),
        "p50": round(nearest_rank_percentile(values, 0.50), 3),
        "p95": round(nearest_rank_percentile(values, 0.95), 3),
    }


def summarize_results(results: Iterable[CaseResult]) -> dict[str, object]:
    items = tuple(results)
    attacks = tuple(item for item in items if item.case.classification == "attack")
    benign = tuple(item for item in items if item.case.classification == "benign")
    attack_detected = sum(item.passed for item in attacks)
    benign_passed = sum(item.passed for item in benign)
    guided = tuple(
        item for item in attacks if item.case.expected.get("guide_back_succeeded") is True
    )
    guided_succeeded = sum(
        item.observation.guide_back_succeeded is True and item.passed for item in guided
    )
    outcomes = Counter(
        outcome
        for item in items
        for outcome in item.observation.policy_outcomes
    )
    return {
        "case_total": len(items),
        "case_passed": sum(item.passed for item in items),
        "case_failed": sum(not item.passed for item in items),
        "attack_total": len(attacks),
        "attack_detected": attack_detected,
        "attack_detection_rate": attack_detected / len(attacks) if attacks else None,
        "benign_total": len(benign),
        "benign_passed": benign_passed,
        "benign_pass_rate": benign_passed / len(benign) if benign else None,
        "false_positive_count": len(benign) - benign_passed,
        "false_positive_rate": (
            (len(benign) - benign_passed) / len(benign) if benign else None
        ),
        "guide_back_total": len(guided),
        "guide_back_succeeded": guided_succeeded,
        "guide_back_success_rate": (
            guided_succeeded / len(guided) if guided else None
        ),
        "policy_outcome_counts": dict(sorted(outcomes.items())),
        "synthetic_value_subject_to_approval_minor": sum(
            int(item.observation.details.get("subject_to_approval_minor", 0))
            for item in items
        ),
    }
