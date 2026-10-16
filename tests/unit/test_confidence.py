"""Unit tests for Confidence and Uncertainty Engine (Phase 2D)."""

import pytest
from services.nowcast.confidence import compute_nowcast_confidence, ConfidenceReport


def test_confidence_multi_factor_scoring():
    """Verify confidence score degradation under suboptimal conditions."""
    # Ideal conditions
    optimal = compute_nowcast_confidence(
        weather_provider_count=3,
        weather_latency_ms=800.0,
        weather_points_count=9,
        mass_balance_error_pct=0.03,
        has_live_tide=True,
        has_drainage_coupling=True,
    )
    assert optimal.score >= 85.0
    assert optimal.level == "HIGH"
    assert len(optimal.factors) == 5
    assert len(optimal.limitations) == 0

    # Degraded conditions (single provider, elevated mass balance error, no tide gauge)
    degraded = compute_nowcast_confidence(
        weather_provider_count=1,
        weather_latency_ms=4500.0,
        weather_points_count=5,
        mass_balance_error_pct=2.5,
        has_live_tide=False,
        has_drainage_coupling=False,
    )
    assert degraded.score < optimal.score
    assert degraded.level in ("MODERATE", "LOW")
    assert len(degraded.limitations) >= 3

    # Check that factors provide clear explainability
    for factor in optimal.factors:
        assert "factor" in factor
        assert "weight_pct" in factor
        assert "score_earned" in factor
        assert "description" in factor
