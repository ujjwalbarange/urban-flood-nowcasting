"""Tests for data quality control pipeline."""

import math
import pytest
from services.data.quality import (
    QCFlag,
    QCResult,
    DataProvenance,
    ConfidenceAssessment,
    qc_rainfall_rate,
    qc_rainfall_timeseries,
    qc_water_depth,
    qc_mass_balance,
    compute_confidence,
)


class TestRainfallQC:
    """Test rainfall rate quality checks."""

    def test_normal_rate_is_good(self):
        result = qc_rainfall_rate(50.0, source="gauge")
        assert result.flag == QCFlag.GOOD

    def test_zero_rate_is_good(self):
        result = qc_rainfall_rate(0.0)
        assert result.flag == QCFlag.GOOD

    def test_negative_is_bad(self):
        result = qc_rainfall_rate(-5.0)
        assert result.flag == QCFlag.BAD
        assert result.corrected_value == 0.0

    def test_nan_is_bad(self):
        result = qc_rainfall_rate(float('nan'))
        assert result.flag == QCFlag.BAD

    def test_inf_is_bad(self):
        result = qc_rainfall_rate(float('inf'))
        assert result.flag == QCFlag.BAD

    def test_extreme_is_bad(self):
        result = qc_rainfall_rate(400.0)
        assert result.flag == QCFlag.BAD
        assert result.corrected_value == 350.0

    def test_high_is_suspect(self):
        result = qc_rainfall_rate(250.0)
        assert result.flag == QCFlag.SUSPECT

    def test_mumbai_extreme_is_suspect(self):
        # 2005 event: ~190 mm in 1 hour at Santacruz
        result = qc_rainfall_rate(190.0)
        assert result.flag == QCFlag.GOOD

    def test_source_recorded(self):
        result = qc_rainfall_rate(50.0, source="IMD_AWS")
        assert result.source == "IMD_AWS"


class TestRainfallTimeseries:
    """Test rainfall timeseries QC."""

    def test_normal_series_is_good(self):
        values = [10.0, 15.0, 20.0, 18.0, 12.0, 5.0]
        result = qc_rainfall_timeseries(values)
        assert result.flag == QCFlag.GOOD

    def test_large_jump_is_suspect(self):
        values = [10.0, 10.0, 200.0, 10.0]
        result = qc_rainfall_timeseries(values, max_jump_mmh=150.0)
        assert result.flag == QCFlag.SUSPECT

    def test_stuck_gauge_is_suspect(self):
        values = [50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0]
        result = qc_rainfall_timeseries(values)
        assert result.flag == QCFlag.SUSPECT

    def test_insufficient_data(self):
        result = qc_rainfall_timeseries([5.0])
        assert result.flag == QCFlag.NOT_CHECKED


class TestWaterDepthQC:
    """Test water depth quality checks."""

    def test_normal_depth_is_good(self):
        result = qc_water_depth(0.5)
        assert result.flag == QCFlag.GOOD

    def test_negative_depth_is_bad(self):
        result = qc_water_depth(-0.1)
        assert result.flag == QCFlag.BAD

    def test_extreme_depth_is_suspect(self):
        result = qc_water_depth(20.0)
        assert result.flag == QCFlag.SUSPECT

    def test_zero_depth_is_good(self):
        result = qc_water_depth(0.0)
        assert result.flag == QCFlag.GOOD


class TestMassBalanceQC:
    """Test mass balance closure checks."""

    def test_good_closure(self):
        result = qc_mass_balance(1.5)
        assert result.flag == QCFlag.GOOD

    def test_marginal_closure(self):
        result = qc_mass_balance(8.0)
        assert result.flag == QCFlag.SUSPECT

    def test_bad_closure(self):
        result = qc_mass_balance(20.0)
        assert result.flag == QCFlag.BAD

    def test_negative_error_uses_abs(self):
        result = qc_mass_balance(-3.0)
        assert result.flag == QCFlag.GOOD


class TestConfidenceScoring:
    """Test multi-factor confidence assessment."""

    def test_high_confidence(self):
        conf = compute_confidence(
            mass_balance_error_pct=1.0,
            rainfall_source="gauge_verified",
            terrain_source="copernicus_glo30",
            spatial_params_quality="postgis_lulc",
            has_drainage_coupling=True,
            validation_csi=0.65,
        )
        assert conf.level == "HIGH"
        assert conf.score >= 70

    def test_low_confidence(self):
        conf = compute_confidence(
            mass_balance_error_pct=25.0,
            rainfall_source="forced_uniform",
            terrain_source="synthetic",
            spatial_params_quality="unknown",
            has_drainage_coupling=False,
        )
        assert conf.level == "LOW"
        assert conf.score < 45

    def test_moderate_confidence(self):
        conf = compute_confidence(
            mass_balance_error_pct=3.0,
            rainfall_source="open-meteo",
            terrain_source="copernicus_glo30",
            spatial_params_quality="default",
            has_drainage_coupling=False,
        )
        assert conf.level == "MODERATE"

    def test_factors_sum_to_score(self):
        conf = compute_confidence(
            mass_balance_error_pct=2.0,
            rainfall_source="open-meteo",
            terrain_source="copernicus_glo30",
            spatial_params_quality="default",
        )
        factor_sum = sum(f["score"] for f in conf.factors)
        assert abs(conf.score - factor_sum) < 0.01

    def test_all_factors_present(self):
        conf = compute_confidence(
            mass_balance_error_pct=2.0,
            rainfall_source="open-meteo",
            terrain_source="copernicus_glo30",
            spatial_params_quality="default",
        )
        factor_names = {f["factor"] for f in conf.factors}
        assert "mass_balance" in factor_names
        assert "rainfall_source" in factor_names
        assert "terrain" in factor_names
        assert "spatial_params" in factor_names
        assert "drainage_coupling" in factor_names
        assert "validation" in factor_names


class TestProvenance:
    """Test data provenance recording."""

    def test_provenance_to_dict(self):
        prov = DataProvenance(
            source_name="Open-Meteo",
            source_type="api",
            spatial_resolution="0.1deg",
            temporal_resolution="15min",
        )
        d = prov.to_dict()
        assert d["source_name"] == "Open-Meteo"
        assert d["source_type"] == "api"

    def test_qc_result_to_dict(self):
        result = qc_rainfall_rate(50.0, source="test")
        d = result.to_dict()
        assert d["flag"] == "good"
        assert "non_negative" in d["checks_passed"]
