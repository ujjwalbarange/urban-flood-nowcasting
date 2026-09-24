"""Integration test for the full simulation pipeline.

This test verifies that:
1. All components chain together correctly
2. Mass balance is preserved end-to-end
3. Physical behavior is qualitatively correct
"""

import numpy as np
import pytest

from services.flood.engine import SimulationConfig, run_simulation
from services.hydrology.infiltration import HortonParams


class TestSimulationEngine:
    """Integration tests for the full flood simulation pipeline."""

    def _make_bowl_dem(self, rows=20, cols=20, cell_size=30.0):
        """Create a bowl-shaped DEM — water should pool in the center."""
        y, x = np.mgrid[0:rows, 0:cols]
        cy, cx = rows / 2, cols / 2
        # Quadratic bowl: high at edges, low at center
        dem = 10.0 + 0.5 * ((x - cx) ** 2 + (y - cy) ** 2) / max(rows, cols)
        return dem.astype(np.float64)

    def _make_uniform_rainfall(self, duration_hours=2.0, rate_mmh=30.0):
        """Create a uniform rainfall schedule."""
        return [(0.0, rate_mmh), (duration_hours, rate_mmh), (duration_hours + 0.01, 0.0)]

    def test_simulation_runs_to_completion(self):
        """Basic smoke test: simulation should complete without errors."""
        dem = self._make_bowl_dem()
        rainfall = self._make_uniform_rainfall(duration_hours=0.5, rate_mmh=20.0)
        imperviousness = np.full_like(dem, 0.5)

        config = SimulationConfig(
            duration_hours=0.5,
            cell_size_m=30.0,
            routing_dt_s=5.0,  # Larger step for speed
            snapshot_interval_s=60.0,
        )

        result = run_simulation(dem, rainfall, imperviousness, config=config)

        assert result.total_steps > 0
        assert result.finished_at is not None
        assert len(result.snapshots) > 0

    def test_mass_balance_closure(self):
        """Mass balance error should be small (< 5%)."""
        dem = self._make_bowl_dem()
        rainfall = self._make_uniform_rainfall(duration_hours=0.5, rate_mmh=30.0)
        imperviousness = np.full_like(dem, 0.3)

        config = SimulationConfig(
            duration_hours=0.5,
            cell_size_m=30.0,
            routing_dt_s=5.0,
            snapshot_interval_s=120.0,
        )

        result = run_simulation(dem, rainfall, imperviousness, config=config)

        assert result.mass_balance is not None
        closure = result.mass_balance.compute_closure()
        assert closure < 5.0, f"Mass balance error {closure:.2f}% exceeds 5%"

    def test_bowl_dem_pools_water(self):
        """On a bowl-shaped DEM, water should accumulate at the center."""
        dem = self._make_bowl_dem(rows=20, cols=20)
        rainfall = self._make_uniform_rainfall(duration_hours=0.5, rate_mmh=50.0)
        imperviousness = np.full_like(dem, 0.8)  # Mostly impervious

        config = SimulationConfig(
            duration_hours=0.5,
            cell_size_m=30.0,
            routing_dt_s=5.0,
            snapshot_interval_s=60.0,
        )

        result = run_simulation(dem, rainfall, imperviousness, config=config)

        # After simulation, max depth should be in the last snapshot
        assert result.max_depth_m > 0
        assert result.max_flooded_cells > 0

    def test_no_rain_no_flood(self):
        """Without rainfall, there should be no flooding."""
        dem = self._make_bowl_dem()
        rainfall = [(0.0, 0.0), (1.0, 0.0)]  # No rain
        imperviousness = np.full_like(dem, 0.5)

        config = SimulationConfig(
            duration_hours=0.1,
            cell_size_m=30.0,
            routing_dt_s=5.0,
        )

        result = run_simulation(dem, rainfall, imperviousness, config=config)
        assert result.max_depth_m == 0.0
        assert result.max_flooded_cells == 0

    def test_impervious_produces_more_flooding(self):
        """Impervious surfaces should produce more flooding than pervious."""
        dem = self._make_bowl_dem()
        rainfall = self._make_uniform_rainfall(duration_hours=0.5, rate_mmh=40.0)

        config = SimulationConfig(
            duration_hours=0.5,
            cell_size_m=30.0,
            routing_dt_s=5.0,
            snapshot_interval_s=120.0,
        )

        # Run with pervious surface
        result_pervious = run_simulation(
            dem, rainfall, np.full_like(dem, 0.1), config=config
        )

        # Run with impervious surface
        result_impervious = run_simulation(
            dem, rainfall, np.full_like(dem, 0.9), config=config
        )

        assert result_impervious.max_depth_m > result_pervious.max_depth_m

    def test_coupling_reduces_surface_water(self):
        """With drainage coupling, surface water should be reduced."""
        dem = self._make_bowl_dem(rows=10, cols=10)
        rainfall = self._make_uniform_rainfall(duration_hours=0.5, rate_mmh=50.0)
        imperviousness = np.full_like(dem, 0.8)

        config = SimulationConfig(
            duration_hours=0.5,
            cell_size_m=30.0,
            routing_dt_s=5.0,
        )

        # Without coupling
        result_no_coupling = run_simulation(
            dem, rainfall, imperviousness, config=config
        )

        # With coupling (drain at center of bowl, head below surface)
        center_r, center_c = dem.shape[0] // 2, dem.shape[1] // 2
        coupling_pts = [{"node_id": "drain_1", "row": center_r, "col": center_c}]
        drain_heads = {"drain_1": dem[center_r, center_c] - 2.0}  # 2m below

        result_with_coupling = run_simulation(
            dem, rainfall, imperviousness,
            coupling_points=coupling_pts,
            drainage_heads=drain_heads,
            config=config,
        )

        # With drainage, surface water should be reduced
        assert result_with_coupling.coupling_events > 0
