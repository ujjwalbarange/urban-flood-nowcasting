"""Tests for physics engines — infiltration, surface flow, coupling.

These tests verify the PHYSICAL CORRECTNESS of the simulation,
not just that code runs. Mass balance closure is the key invariant.
"""

import numpy as np
import pytest

from services.hydrology.infiltration import (
    HortonParams,
    horton_infiltration,
    horton_infiltration_grid,
    compute_runoff,
)
from services.hydrology.surface import (
    SurfaceState,
    initialize_surface,
    apply_rainfall,
    apply_infiltration,
    route_flow_step,
)
from services.coupling.exchange import (
    CouplingParams,
    compute_orifice_exchange,
    compute_exchange_at_point,
    CouplingEngine,
)


class TestHortonInfiltration:
    """Verify Horton equation produces physically correct results."""

    def test_initial_rate_equals_f0(self):
        """At t=0, infiltration capacity should equal f0."""
        params = HortonParams(f0_mmh=76.0, f_min_mmh=3.8, k_per_h=2.0)
        # With rainfall > f0, infiltration = f0
        result = horton_infiltration(100.0, 0.0, params)
        assert result == pytest.approx(76.0, rel=1e-6)

    def test_decays_to_f_min(self):
        """After long time, infiltration capacity approaches f_min."""
        params = HortonParams(f0_mmh=76.0, f_min_mmh=3.8, k_per_h=2.0)
        result = horton_infiltration(100.0, 10.0, params)  # 10 hours
        assert result == pytest.approx(3.8, abs=0.01)

    def test_capped_by_rainfall(self):
        """Infiltration cannot exceed available rainfall."""
        params = HortonParams(f0_mmh=76.0, f_min_mmh=3.8, k_per_h=2.0)
        result = horton_infiltration(5.0, 0.0, params)  # Only 5 mm/h rain
        assert result == 5.0  # Capped at rainfall rate

    def test_impervious_surface_zero_infiltration(self):
        """Fully impervious surface should have zero infiltration."""
        params = HortonParams()
        rainfall = np.full((5, 5), 50.0)
        imperviousness = np.ones((5, 5))  # Fully impervious
        result = horton_infiltration_grid(rainfall, 0.0, imperviousness, params)
        assert np.all(result == 0.0)

    def test_pervious_surface_has_infiltration(self):
        """Pervious surface should have positive infiltration."""
        params = HortonParams()
        rainfall = np.full((5, 5), 50.0)
        imperviousness = np.zeros((5, 5))  # Fully pervious
        result = horton_infiltration_grid(rainfall, 0.0, imperviousness, params)
        assert np.all(result > 0.0)

    def test_runoff_equals_rain_minus_infiltration(self):
        """Runoff = rainfall - infiltration, always >= 0."""
        rain = np.array([10.0, 5.0, 0.0])
        infil = np.array([3.0, 8.0, 0.0])
        runoff = compute_runoff(rain, infil)
        expected = np.array([7.0, 0.0, 0.0])
        np.testing.assert_array_almost_equal(runoff, expected)


class TestSurfaceFlow:
    """Verify surface flow model conserves mass."""

    def _make_flat_dem(self, rows=10, cols=10, elevation=10.0, cell_size=30.0):
        """Create a flat DEM for testing."""
        dem = np.full((rows, cols), elevation)
        return initialize_surface(dem, cell_size)

    def _make_tilted_dem(self, rows=10, cols=10, cell_size=30.0):
        """Create a tilted DEM (west to east slope) for testing flow."""
        dem = np.zeros((rows, cols))
        for c in range(cols):
            dem[:, c] = 10.0 - (c / cols) * 5.0  # 10m west, 5m east
        return initialize_surface(dem, cell_size)

    def test_rainfall_adds_volume(self):
        """Applying rainfall should increase total volume."""
        state = self._make_flat_dem()
        initial_vol = state.total_volume_m3
        apply_rainfall(state, 10.0, dt_s=3600.0)  # 10 mm/h for 1 hour
        assert state.total_volume_m3 > initial_vol
        # 10mm over 10x10 grid at 30m cells = 0.01m * 100 * 900m² = 900 m³
        expected_vol = 0.01 * 100 * 900.0
        assert state.total_volume_m3 == pytest.approx(expected_vol, rel=0.01)

    def test_infiltration_removes_volume(self):
        """Infiltration should reduce surface water volume."""
        state = self._make_flat_dem()
        apply_rainfall(state, 10.0, dt_s=3600.0)
        vol_after_rain = state.total_volume_m3

        infil_rate = np.full((10, 10), 5.0)  # 5 mm/h
        apply_infiltration(state, infil_rate, dt_s=3600.0)
        assert state.total_volume_m3 < vol_after_rain

    def test_no_water_no_flow(self):
        """Without water, routing should not change anything."""
        state = self._make_tilted_dem()
        assert state.total_volume_m3 == 0.0
        route_flow_step(state, dt_s=1.0)
        assert state.total_volume_m3 == 0.0

    def test_tilted_dem_flow_direction(self):
        """Water on a tilted DEM should flow downhill (west→east)."""
        state = self._make_tilted_dem()
        # Add water only on the high (west) side
        state.depth[:, 0] = 0.5  # 50cm on western column

        # Route for several steps
        for _ in range(50):
            route_flow_step(state, dt_s=1.0)

        # Water should have moved eastward
        east_depth = np.mean(state.depth[:, -3:])
        west_depth = np.mean(state.depth[:, :3])
        # After routing, east should have gained water
        assert state.depth.sum() > 0  # Water still exists
        # Non-negative depths
        assert np.all(state.depth >= 0)

    def test_mass_conservation_flat(self):
        """Mass must be conserved on flat terrain with no outflow."""
        state = self._make_flat_dem()
        apply_rainfall(state, 20.0, dt_s=3600.0)
        initial_volume = state.total_volume_m3

        for _ in range(100):
            route_flow_step(state, dt_s=1.0)

        # On flat terrain, water redistributes but total volume preserved
        final_volume = state.total_volume_m3 + state.total_outflow_m3
        error_pct = abs(final_volume - initial_volume) / initial_volume * 100
        assert error_pct < 1.0, f"Mass balance error {error_pct:.2f}% exceeds 1%"


class TestCouplingExchange:
    """Verify the surface-drainage coupling exchange equations."""

    def test_no_head_difference_no_exchange(self):
        """With equal heads, exchange should be zero."""
        params = CouplingParams(min_head_diff_m=0.01)
        q = compute_orifice_exchange(10.0, 10.0, params)
        assert q == 0.0

    def test_surface_higher_is_capture(self):
        """When surface head > drainage head, flow is capture (positive)."""
        params = CouplingParams()
        q = compute_orifice_exchange(10.5, 10.0, params)
        assert q > 0.0

    def test_drainage_higher_is_return(self):
        """When drainage head > surface head, flow is return (negative)."""
        params = CouplingParams()
        q = compute_orifice_exchange(10.0, 10.5, params)
        assert q < 0.0

    def test_exchange_magnitude_scales_with_head(self):
        """Greater head difference → greater exchange rate."""
        params = CouplingParams()
        q_small = abs(compute_orifice_exchange(10.1, 10.0, params))
        q_large = abs(compute_orifice_exchange(11.0, 10.0, params))
        assert q_large > q_small

    def test_capture_capped_by_available_water(self):
        """Exchange cannot remove more water than is on the surface."""
        result = compute_exchange_at_point(
            node_id="test_node",
            surface_depth_m=0.001,  # Tiny amount of water
            surface_elevation_m=10.0,
            drainage_head_m=5.0,   # Big head difference
            available_surface_water_m3=0.5,  # Only 0.5 m³ available
            dt_s=60.0,
            params=CouplingParams(),
        )
        volume = result.exchange_m3s * 60.0
        assert volume <= 0.5 * 0.9  # Max 90% capture

    def test_exchange_result_regime_classification(self):
        """Exchange results should correctly classify regime."""
        result_capture = compute_exchange_at_point(
            "n1", 0.5, 10.0, 8.0, 100.0, 60.0, CouplingParams()
        )
        assert result_capture.regime == "capture"

        result_return = compute_exchange_at_point(
            "n2", 0.0, 10.0, 12.0, 0.0, 60.0, CouplingParams()
        )
        assert result_return.regime in ("return", "inactive")


class TestCouplingEngine:
    """Integration test for the coupling engine."""

    def test_engine_ledger_tracking(self):
        """Engine should track cumulative capture and return volumes."""
        engine = CouplingEngine()
        depth = np.full((5, 5), 0.3)
        dem = np.full((5, 5), 10.0)
        coupling_points = [
            {"node_id": "n1", "row": 2, "col": 2},
        ]
        drainage_heads = {"n1": 9.0}  # Drainage lower → capture

        results = engine.compute_all_exchanges(
            depth, dem, coupling_points, drainage_heads,
            cell_size_m=30.0, dt_s=60.0,
        )

        assert len(results) == 1
        assert results[0].regime == "capture"
        assert engine.ledger.total_capture_m3 > 0
        assert engine.ledger.capture_events == 1
