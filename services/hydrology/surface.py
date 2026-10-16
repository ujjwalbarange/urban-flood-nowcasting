"""Surface flow model — diffusive wave approximation.

This is the 2D overland flow solver that routes water across the terrain.
Uses the de Almeida et al. (2012) diffusive wave equation:

    ∂h/∂t + ∂(q_x)/∂x + ∂(q_y)/∂y = R - I

where:
    h = water depth (m)
    q = unit discharge (m²/s)
    R = rainfall rate (m/s)
    I = infiltration rate (m/s)

The discharge between adjacent cells is computed as:
    q = (h_flow^(5/3) / n) * S^(1/2) * dt / dx

where:
    h_flow = depth of water available to flow
    n = Manning's roughness coefficient
    S = water surface slope between cells
    dt = time step (s)
    dx = cell size (m)

This implements a simplified 2D diffusive wave. For production-grade
accuracy, we would use Landlab's OverlandFlow component or our own
HLL solver (future C++ integration).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np
import structlog

logger = structlog.get_logger()


@dataclass
class SurfaceState:
    """State of the surface flow model at a given time step."""

    depth: np.ndarray              # Water depth grid (m)
    dem: np.ndarray                # Ground elevation (m)
    manning_n: np.ndarray          # Manning's roughness coefficient
    cell_size_m: float             # Grid cell size (m)
    time_s: float = 0.0           # Current simulation time (s)
    total_rainfall_m3: float = 0.0
    total_tide_inflow_m3: float = 0.0
    total_infiltration_m3: float = 0.0
    total_outflow_m3: float = 0.0


    @property
    def water_surface(self) -> np.ndarray:
        """Water surface elevation = DEM + depth."""
        return self.dem + self.depth

    @property
    def total_volume_m3(self) -> float:
        """Total water volume on the surface."""
        return float(np.sum(self.depth) * self.cell_size_m ** 2)

    @property
    def flooded_cells(self) -> int:
        """Number of cells with depth > 5cm."""
        return int(np.sum(self.depth > 0.05))

    @property
    def max_depth(self) -> float:
        return float(np.max(self.depth))


def initialize_surface(
    dem: np.ndarray,
    cell_size_m: float,
    manning_n: float = 0.035,
) -> SurfaceState:
    """Initialize surface state from DEM.

    Args:
        dem: 2D elevation grid (m)
        cell_size_m: Grid cell size (m)
        manning_n: Default Manning's roughness (0.035 for mixed urban)
    """
    rows, cols = dem.shape
    return SurfaceState(
        depth=np.zeros((rows, cols), dtype=np.float64),
        dem=dem.astype(np.float64),
        manning_n=np.full((rows, cols), manning_n, dtype=np.float64),
        cell_size_m=cell_size_m,
    )


def apply_rainfall(
    state: SurfaceState,
    rainfall_rate_mmh: np.ndarray | float,
    dt_s: float,
) -> None:
    """Apply rainfall to the surface as water depth increase.

    Args:
        state: Current surface state (modified in-place)
        rainfall_rate_mmh: Rainfall rate (mm/h), scalar or 2D grid
        dt_s: Time step in seconds
    """
    # Convert mm/h → m/s → m per time step
    rainfall_m = np.asarray(rainfall_rate_mmh, dtype=np.float64) / 1000.0 / 3600.0 * dt_s
    if rainfall_m.ndim == 0:
        rainfall_m = np.full(state.depth.shape, rainfall_m, dtype=np.float64)
    state.depth += rainfall_m
    state.total_rainfall_m3 += float(np.sum(rainfall_m)) * (state.cell_size_m ** 2)


def apply_infiltration(
    state: SurfaceState,
    infiltration_rate_mmh: np.ndarray,
    dt_s: float,
) -> None:
    """Remove infiltrated water from the surface.

    Cannot infiltrate more than what's on the surface.
    """
    infiltration_m = infiltration_rate_mmh / 1000.0 / 3600.0 * dt_s
    actual_infiltration = np.minimum(infiltration_m, state.depth)
    state.depth -= actual_infiltration
    state.total_infiltration_m3 += (
        float(np.sum(actual_infiltration)) * state.cell_size_m ** 2
    )


def route_flow_step(
    state: SurfaceState,
    dt_s: float,
    tide_level_m: Optional[float] = None,
    coastal_mask: Optional[np.ndarray] = None,
) -> None:
    """Route surface water for one time step using diffusive wave.

    Water flows from higher water surface to lower water surface.
    The flow rate depends on depth, slope, and Manning's roughness.

    Supports downstream tidal boundary conditions:
    - If tide_level_m is provided and coastal_mask is active, coastal cells
      with DEM < tide_level_m receive tidal inflow (ocean surge/inundation).
    - Downstream boundary outflow is governed by the water surface head difference:
      if WSE_land <= tide_level_m, outflow is blocked (tidal locking / backwater).
      if WSE_land > tide_level_m, gravity drainage into the sea is throttled by tidal head.

    Fully vectorized using 2D NumPy array operations for high performance.
    Modifies state.depth in-place.
    """
    rows, cols = state.depth.shape
    dx = state.cell_size_m
    cell_area = dx * dx

    # 1. Tidal seawater intrusion in coastal cells below sea level
    if tide_level_m is not None and coastal_mask is not None and np.any(coastal_mask):
        submerged = coastal_mask & (state.dem < tide_level_m)
        if np.any(submerged):
            target_depth = tide_level_m - state.dem[submerged]
            deficit = np.maximum(0.0, target_depth - state.depth[submerged])
            # Tidal inflow advances stably into coastal cells
            inflow_rate = np.minimum(deficit, 0.1 * deficit + 0.01 * (dt_s / 2.0))
            actual_inflow = np.minimum(inflow_rate, deficit)
            state.depth[submerged] += actual_inflow
            state.total_tide_inflow_m3 += float(np.sum(actual_inflow)) * cell_area

    wse = state.water_surface

    flux_x = np.zeros((rows, cols + 1), dtype=np.float64)
    flux_y = np.zeros((rows + 1, cols), dtype=np.float64)

    # 2. Vectorized X-direction fluxes (vertical cell interfaces)
    slope_x = (wse[:, :-1] - wse[:, 1:]) / dx
    h_flow_pos_x = np.where(state.dem[:, 1:] > wse[:, :-1], np.maximum(wse[:, :-1] - state.dem[:, 1:], 0.0), state.depth[:, :-1])
    h_flow_neg_x = np.where(state.dem[:, :-1] > wse[:, 1:], np.maximum(wse[:, 1:] - state.dem[:, :-1], 0.0), state.depth[:, 1:])
    h_flow_x = np.where(slope_x > 0, h_flow_pos_x, h_flow_neg_x)
    n_avg_x = 0.5 * (state.manning_n[:, :-1] + state.manning_n[:, 1:])

    q_x = np.sign(slope_x) * (np.maximum(h_flow_x, 0.0) ** (5.0 / 3.0)) / np.maximum(n_avg_x, 1e-4) * np.sqrt(np.abs(slope_x))
    vol_flux_x = q_x * dx * dt_s

    avail_left = state.depth[:, :-1] * cell_area * 0.25
    avail_right = state.depth[:, 1:] * cell_area * 0.25
    vol_flux_x = np.where(vol_flux_x > 0, np.minimum(vol_flux_x, avail_left), np.maximum(vol_flux_x, -avail_right))
    flux_x[:, 1:-1] = vol_flux_x

    # 3. Vectorized Y-direction fluxes (horizontal cell interfaces)
    slope_y = (wse[:-1, :] - wse[1:, :]) / dx
    h_flow_pos_y = np.where(state.dem[1:, :] > wse[:-1, :], np.maximum(wse[:-1, :] - state.dem[1:, :], 0.0), state.depth[:-1, :])
    h_flow_neg_y = np.where(state.dem[:-1, :] > wse[1:, :], np.maximum(wse[1:, :] - state.dem[:-1, :], 0.0), state.depth[1:, :])
    h_flow_y = np.where(slope_y > 0, h_flow_pos_y, h_flow_neg_y)
    n_avg_y = 0.5 * (state.manning_n[:-1, :] + state.manning_n[1:, :])

    q_y = np.sign(slope_y) * (np.maximum(h_flow_y, 0.0) ** (5.0 / 3.0)) / np.maximum(n_avg_y, 1e-4) * np.sqrt(np.abs(slope_y))
    vol_flux_y = q_y * dx * dt_s

    avail_top = state.depth[:-1, :] * cell_area * 0.25
    avail_bot = state.depth[1:, :] * cell_area * 0.25
    vol_flux_y = np.where(vol_flux_y > 0, np.minimum(vol_flux_y, avail_top), np.maximum(vol_flux_y, -avail_bot))
    flux_y[1:-1, :] = vol_flux_y

    # 4. Handle boundary outflow (incorporating tidal head / backwater)
    if tide_level_m is not None:
        # Southern boundary (row = rows - 1)
        head_diff_y = wse[-1, :] - tide_level_m
        allowed_flux_y = np.where(head_diff_y > 0.0, np.maximum(flux_y[rows, :], 0.0), 0.0)
        # Eastern boundary (col = cols - 1)
        head_diff_x = wse[:, -1] - tide_level_m
        allowed_flux_x = np.where(head_diff_x > 0.0, np.maximum(flux_x[:, cols], 0.0), 0.0)
        flux_y[rows, :] = allowed_flux_y
        flux_x[:, cols] = allowed_flux_x
        boundary_outflow = float(np.sum(allowed_flux_y) + np.sum(allowed_flux_x))
    else:
        boundary_outflow = float(np.sum(np.maximum(flux_y[rows, :], 0.0)) + np.sum(np.maximum(flux_x[:, cols], 0.0)))

    # 5. Apply net fluxes to update depth
    net_flux = (flux_x[:, :-1] - flux_x[:, 1:]) + (flux_y[:-1, :] - flux_y[1:, :])
    state.depth += net_flux / cell_area
    state.total_outflow_m3 += boundary_outflow

    # Ensure non-negative depth
    state.depth = np.maximum(state.depth, 0.0)
    state.time_s += dt_s

