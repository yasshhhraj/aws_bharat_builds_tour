import math

import pytest

from packages.evaluation.metrics import latency_summary, nearest_rank_percentile


def test_nearest_rank_percentiles_cover_boundaries():
    assert nearest_rank_percentile([4], 0.5) == 4
    assert nearest_rank_percentile([1, 2, 3, 4], 0.5) == 2
    assert nearest_rank_percentile([1, 2, 3, 4], 0.95) == 4
    assert nearest_rank_percentile([1, 1, 1], 0.95) == 1


def test_latency_summary_reports_exact_sample_count_and_ordered_percentiles():
    result = latency_summary([0.1, 0.2, 0.3, 0.4])
    assert result == {
        "count": 4,
        "min": 0.1,
        "max": 0.4,
        "mean": 0.25,
        "p50": 0.2,
        "p95": 0.4,
    }


@pytest.mark.parametrize("samples", [[], [-1], [math.nan], [math.inf], [True]])
def test_invalid_latency_samples_are_rejected(samples):
    with pytest.raises(ValueError):
        latency_summary(samples)
