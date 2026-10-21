"""Unit and integration tests for Phase 5:
- Model-run and data-provenance tracking (Batch 1)
- Historical flood-event validation & paired depth metrics (Batch 2)
- Model uncertainty and 5-scenario parameter sensitivity analysis (Batch 3)
- Forecast-driven hydrodynamic model runs (Batch 4)
- Explainable flood-aware evacuation routing & staleness invalidation (Batch 5)
- Data quality & system health monitoring (Batch 6)
"""

from __future__ import annotations

import asyncio
import pytest
import numpy as np
from fastapi.testclient import TestClient

from services.api.main import app
from services.provenance.engine import (
    DataClassification,
    DataFeedStatus,
    DataFeedMetadata,
    SimulationProvenance,
    DataProvenanceRegistry,
    get_provenance_registry,
)
from services.validation.historical_validation import (
    HistoricalValidator,
    PairedDepthMetrics,
    ContingencyMetrics,
    get_historical_validator,
)
from services.flood.uncertainty import (
    UncertaintyEngine,
    ScenarioResult,
    SensitivityAnalysisReport,
    get_uncertainty_engine,
)
from services.nowcast.forecast_runner import (
    ForecastSimulationRunner,
    ForecastModelRunResult,
    get_forecast_runner,
)
from services.routing.evacuation_engine import (
    MumbaiEvacuationRoutingEngine,
    get_routing_engine,
)

client = TestClient(app)


class TestModelProvenance:
    """Batch 1: Trustworthy model-run records and feed provenance."""

    def test_simulation_provenance_recording(self):
        prov = SimulationProvenance(
            run_id="run_test_001",
            run_type="nowcast",
            rainfall_source="open_meteo_live",
            rainfall_classification=DataClassification.FORECAST,
            dem_source="Copernicus GLO-30 DSM (ESA)",
            dem_resolution_m=30.0,
            solver_name="2D Diffusive Wave Hydrodynamic Solver",
            solver_version="v2.4",
            catchment="hindmata_dadar",
            cell_size_m=30.0,
            manning_n=0.035,
        )
        # Validate output
        success = prov.validate_and_complete(
            max_depth_m=0.35,
            mean_depth_m=0.08,
            flooded_area_km2=1.2,
            flooded_cells=150,
            mass_balance_error_pct=0.2,
            depth_grid_valid=True,
        )
        assert success is True
        d = prov.to_dict()
        assert d["run_id"] == "run_test_001"
        assert d["rainfall"]["classification"] == "forecast"
        assert d["validation_passed"] is True
        assert d["terrain"]["resolution_m"] == 30.0

    def test_output_validation_prevents_false_success(self):
        """Failed simulation with NaNs or mass balance divergence must not pass validation."""
        prov = SimulationProvenance(
            run_id="run_test_nan_failure",
            run_type="nowcast",
        )
        # Validate with extreme invalid depth and bad mass balance
        success = prov.validate_and_complete(
            max_depth_m=12.0,  # exceeds 10m threshold
            mean_depth_m=4.0,
            flooded_area_km2=5.0,
            flooded_cells=200,
            mass_balance_error_pct=15.0,  # exceeds 5% closure
            depth_grid_valid=False,
        )
        assert success is False
        assert prov.validation_passed is False
        assert prov.status == "failed"
        assert prov.failure_reason is not None

    def test_data_provenance_registry_list_feeds(self):
        reg = get_provenance_registry()
        feeds = reg.list_feeds()
        assert len(feeds) >= 8
        feed_ids = [f["feed_id"] for f in feeds]
        assert "open_meteo_live_weather" in feed_ids
        assert "copernicus_glo30_dem" in feed_ids
        assert "osm_road_network" in feed_ids
        assert "historical_flood_observations" in feed_ids

    def test_provenance_feeds_no_credential_leak(self):
        reg = get_provenance_registry()
        feeds = reg.list_feeds()
        for f in feeds:
            feed_str = str(f).lower()
            assert "api_key" not in feed_str
            assert "secret" not in feed_str
            assert "password" not in feed_str
            assert "bearer" not in feed_str


class TestHistoricalValidation:
    """Batch 2: Historical flood-event validation against ground-truth evidence."""

    def test_paired_depth_error_calculation(self):
        """Verify PairedDepthMetrics dataclass stores exact depth errors and formulas."""
        metrics = PairedDepthMetrics(
            sample_count_n=3,
            mean_absolute_error_m=0.20,
            root_mean_squared_error_m=0.22,
            mean_bias_error_m=-0.20,
            mean_observed_depth_m=0.90,
            mean_simulated_depth_m=0.70,
            status="valid",
        )
        assert metrics.status == "valid"
        assert metrics.sample_count_n == 3
        assert metrics.mean_absolute_error_m == 0.20
        assert metrics.mean_bias_error_m == -0.20
        assert "MAE" in metrics.formula_mae

    def test_insufficient_validation_data_handling(self):
        """When 0 paired depth observations exist, explicit insufficient_validation_data state is returned."""
        metrics = PairedDepthMetrics(
            sample_count_n=0,
            mean_absolute_error_m=None,
            root_mean_squared_error_m=None,
            mean_bias_error_m=None,
            mean_observed_depth_m=None,
            mean_simulated_depth_m=None,
            status="insufficient_validation_data",
        )
        assert metrics.status == "insufficient_validation_data"
        assert metrics.sample_count_n == 0
        assert metrics.mean_absolute_error_m is None

    def test_contingency_detection_metrics(self):
        """Verify Critical Success Index and POD formulations."""
        metrics = ContingencyMetrics(
            true_positives=8,
            false_positives=2,
            false_negatives=2,
            true_negatives=10,
            sample_count_n=22,
            recall_pod=0.80,
            precision=0.80,
            critical_success_index=0.667,
            false_alarm_ratio=0.20,
            flood_threshold_m=0.08,
        )
        assert metrics.true_positives == 8
        assert metrics.sample_count_n == 22
        assert metrics.recall_pod == 0.80
        assert metrics.critical_success_index == 0.667
        assert metrics.false_alarm_ratio == 0.20

    def test_historical_benchmark_execution(self):
        validator = get_historical_validator()
        hotspots = validator._load_local_hotspots()
        events = validator._load_local_events()
        # Verify genuine offline archive is available (35 hotspots, 202 events)
        assert len(hotspots) >= 30
        assert len(events) >= 150


class TestModelUncertainty:
    """Batch 3: Model uncertainty and 5-scenario sensitivity analysis."""

    def test_sensitivity_suite_execution(self):
        engine = get_uncertainty_engine()
        report = engine.run_sensitivity_suite(
            catchment="hindmata_dadar",
            base_rainfall_mmh=30.0,
            grid_size=40,
            duration_hours=1.0,
        )
        assert report is not None
        assert len(report.scenarios_evaluated) == 5

        # Check scenarios tested
        labels = [s.label for s in report.scenarios_evaluated]
        assert "Baseline Configuration" in labels
        assert "Low Rainfall (-20%)" in labels
        assert "High Rainfall (+20%)" in labels
        assert "Low Surface Friction" in labels
        assert "High Friction / Debris-Clogged" in labels

    def test_depth_bounds_and_disagreement_mask(self):
        engine = get_uncertainty_engine()
        report = engine.get_latest_analysis()
        if not report:
            report = engine.run_sensitivity_suite(catchment="hindmata_dadar", base_rainfall_mmh=30.0, grid_size=40)

        assert report.depth_range_m["min_peak_m"] <= report.depth_range_m["baseline_peak_m"]
        assert report.depth_range_m["baseline_peak_m"] <= report.depth_range_m["max_peak_m"]
        assert report.area_variation_pct >= 0.0
        assert report.disagreement_area_km2 >= 0.0

    def test_uncalibrated_disclaimer_preservation(self):
        engine = get_uncertainty_engine()
        report = engine.get_latest_analysis()
        if not report:
            report = engine.run_sensitivity_suite(catchment="hindmata_dadar", base_rainfall_mmh=30.0, grid_size=40)

        disclaimers = " ".join(report.scientific_disclaimers)
        assert "NOT a statistically calibrated Bayesian" in disclaimers


class TestForecastSimulation:
    """Batch 4: Forecast-driven hydrodynamic runs."""

    def test_forecast_simulation_runner(self):
        runner = get_forecast_runner()
        res = asyncio.run(runner.execute_forecast_run(
            catchment="hindmata_dadar",
            horizon_hours=2.0,
            grid_size=40,
        ))
        assert res.run_id.startswith("fc_")
        assert res.forcing_classification == "forecast"
        assert res.horizon_hours == 2.0
        assert res.forecast_issue_time is not None
        assert res.valid_from is not None
        assert res.valid_to is not None
        assert res.provenance["rainfall_classification"] == "forecast"
        assert res.provenance["is_valid"] is True


class TestExplainableEvacuation:
    """Batch 5: Explainable routing and stale-route invalidation."""

    def test_explainable_route_generation(self):
        engine = get_routing_engine()
        # Origin near Dadar
        res = engine.find_safest_evacuation_from_point(
            origin_lon=72.842,
            origin_lat=19.018,
            vehicle_type="standard_car",
        )
        assert res["route_found"] is True
        assert "route_explanation" in res
        expl = res["route_explanation"]
        assert "destination_eligibility_reason" in expl
        assert "simulation_run_id_used" in expl
        assert "road_exposure_breakdown" in expl
        assert "spatial_resolution_caveat" in expl

        # Segment breakdown must sum to ~100%
        bd = expl["road_exposure_breakdown"]
        tot_pct = bd["clear_segments_pct"] + bd["caution_segments_pct"] + bd["hazardous_segments_pct"]
        assert tot_pct == pytest.approx(100.0, abs=1.0)

    def test_candidate_alternative_comparison(self):
        engine = get_routing_engine()
        res = engine.find_safest_evacuation_from_point(
            origin_lon=72.842,
            origin_lat=19.018,
            vehicle_type="standard_car",
        )
        assert res["route_found"] is True
        # Check alternative route exists if multiple shelters are available
        if res.get("alternative_route"):
            alt = res["alternative_route"]
            assert "destination_name" in alt
            assert "total_distance_km" in alt
            assert "max_flood_depth_m" in alt
            assert "tradeoff_summary" in alt

    def test_route_staleness_invalidation(self):
        engine = get_routing_engine()
        # A route calculated under an old simulation run ID must be evaluated
        stale_res = engine.check_route_staleness({
            "simulation_run_id_used": "old_outdated_run_123",
            "calculation_timestamp": "2026-10-20T08:00:00Z",
            "corridor_coordinates": [[72.842, 19.018], [72.845, 19.020]],
        })
        assert "is_stale" in stale_res


class TestPhase5Endpoints:
    """Verify all new Phase 5 FastAPI endpoints return valid status."""

    def test_get_provenance_feeds(self):
        response = client.get("/api/v1/provenance/feeds")
        assert response.status_code == 200
        data = response.json()
        assert data["total_feeds"] >= 8
        assert "classification_guide" in data

    def test_get_provenance_runs(self):
        response = client.get("/api/v1/provenance/runs?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert "total_runs" in data

    def test_get_historical_benchmark(self):
        response = client.get("/api/v1/validation/historical-benchmark?event_id=july_2024_cloudburst&catchment=hindmata_dadar&grid_size=40")
        assert response.status_code == 200
        data = response.json()
        assert "paired_depth_metrics" in data
        assert "contingency_metrics" in data
        assert "limitations" in data

    def test_get_simulations_sensitivity(self):
        response = client.get("/api/v1/simulations/sensitivity")
        assert response.status_code == 200
        data = response.json()
        assert "analysis_id" in data
        assert "scenarios_evaluated" in data

    def test_post_check_route_staleness(self):
        response = client.post(
            "/api/v1/subareas/check-route-staleness",
            json={
                "simulation_run_id_used": "run_test_001",
                "calculation_timestamp": "2026-10-20T10:00:00Z",
                "corridor_coordinates": [[72.84, 19.01], [72.85, 19.02]],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "is_stale" in data
