"""Unit tests for Phase B Satellite SAR Validation Engine and NASA IMERG Adapter."""

from datetime import datetime, timezone
import numpy as np
import pytest

from packages.contracts.provenance import DataOrigin, DataQuality, DataSource
from services.rainfall.imerg import IMERGProvider
from services.validation.satellite_sar import SatelliteSARValidator, ValidationMetrics
from services.nowcast.persistence import PersistenceNowcaster


def test_validation_metrics_calculation():
    """Verify standard contingency matrix and threat score mathematics."""
    validator = SatelliteSARValidator()

    # Create dummy 10x10 grids
    sim_depth = np.zeros((10, 10))
    obs_mask = np.zeros((10, 10), dtype=bool)

    # 4 True Positives (sim >= 0.08 and obs is True)
    sim_depth[2:4, 2:4] = 0.50
    obs_mask[2:4, 2:4] = True

    # 2 False Positives (sim >= 0.08, obs is False)
    sim_depth[0, 0:2] = 0.20

    # 3 False Negatives (sim < 0.08, obs is True)
    obs_mask[8, 0:3] = True

    metrics = validator.evaluate_model_extent(sim_depth, obs_mask, min_depth_threshold_m=0.08)

    assert metrics.true_positives == 4
    assert metrics.false_positives == 2
    assert metrics.false_negatives == 3
    assert metrics.true_negatives == 91
    assert metrics.total_cells == 100

    # CSI = TP / (TP + FP + FN) = 4 / (4 + 2 + 3) = 4/9 ≈ 0.4444
    assert round(metrics.critical_success_index, 4) == round(4 / 9, 4)
    # IoU = CSI
    assert round(metrics.iou, 4) == round(4 / 9, 4)
    # POD (Recall) = TP / (TP + FN) = 4 / 7 ≈ 0.5714
    assert round(metrics.recall_pod, 4) == round(4 / 7, 4)
    # Precision = TP / (TP + FP) = 4 / 6 ≈ 0.6667
    assert round(metrics.precision, 4) == round(4 / 6, 4)
    # FAR = FP / (TP + FP) = 2 / 6 ≈ 0.3333
    assert round(metrics.false_alarm_ratio, 4) == round(2 / 6, 4)


def test_spatial_confusion_geojson_generation():
    """Verify GeoJSON polygon generation with TP, FP, FN classifications."""
    validator = SatelliteSARValidator()

    sim_depth = np.zeros((4, 4))
    obs_mask = np.zeros((4, 4), dtype=bool)

    sim_depth[1, 1] = 0.35  # TP
    obs_mask[1, 1] = True

    sim_depth[2, 2] = 0.25  # FP
    obs_mask[2, 2] = False

    obs_mask[3, 3] = True   # FN

    georef = {
        "min_lon": 72.80,
        "max_lon": 72.90,
        "min_lat": 19.00,
        "max_lat": 19.10,
        "rows": 4,
        "cols": 4,
        "cell_size_m": 120.0,
    }

    geojson = validator.generate_spatial_confusion_geojson(sim_depth, obs_mask, georef)
    assert geojson["type"] == "FeatureCollection"
    assert geojson["feature_count"] == 3

    classifications = [f["properties"]["classification"] for f in geojson["features"]]
    assert "TP" in classifications
    assert "FP" in classifications
    assert "FN" in classifications


@pytest.mark.asyncio
async def test_imerg_provider_provenance_tagging():
    """Verify NASA GPM IMERG provider sets exact scientific provenance tags."""
    provider = IMERGProvider()
    assert "NASA GPM IMERG" in provider.provider_name

    obs = await provider.fetch_current(19.076, 72.877)
    assert len(obs) >= 1
    o = obs[0]
    assert o.source == DataSource.NASA_IMERG
    assert o.quality == DataQuality.ESTIMATED
    assert o.provenance is not None
    assert o.provenance.source == DataSource.NASA_IMERG
    assert o.provenance.origin == DataOrigin.PUBLIC_DATA
    assert "NASA" in (o.provenance.notes or "") or "IMERG" in (o.provenance.notes or "")


def test_persistence_nowcasting_decay():
    """Verify short-horizon nowcaster produces decreasing confidence and rate decay."""
    nowcaster = PersistenceNowcaster(decay_rate=0.15, time_step_minutes=15)
    forecasts = nowcaster.nowcast(current_rate_mmh=50.0, hours_ahead=2.0)

    assert len(forecasts) == 8  # 2 hours / 15 min = 8 steps
    # Rate should decay exponentially
    assert forecasts[0].mean_rate_mmh < 50.0
    assert forecasts[-1].mean_rate_mmh < forecasts[0].mean_rate_mmh
    # Confidence should decay linearly
    assert forecasts[0].confidence > forecasts[-1].confidence
    # Lead minutes should increment by 15
    assert forecasts[0].lead_minutes == 15
    assert forecasts[1].lead_minutes == 30
    assert forecasts[-1].lead_minutes == 120
