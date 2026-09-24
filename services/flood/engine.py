"""Integrated simulation engine — orchestrates the full nowcasting pipeline.

This is the master orchestrator that chains:
1. Rainfall input → Nowcast (persistence / NWP)
2. Rainfall on grid → Infiltration (Horton)
3. Excess rainfall → Surface runoff
4. Surface flow routing (diffusive wave)
5. Surface ↔ Drainage coupling (signed orifice exchange)
6. Flood depth grid → Risk assessment
7. Risk → CAP v1.2 alerts

The simulation runs at two time scales:
- Surface routing: dt = 1-10 seconds (CFL stability)
- Coupling stride: Δt = 60 seconds (coupling frequency)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import structlog

from packages.contracts.flood import MassBalance
from services.hydrology.infiltration import HortonParams, horton_infiltration_grid
from services.hydrology.surface import (
    SurfaceState,
    initialize_surface,
    apply_rainfall,
    apply_infiltration,
    route_flow_step,
)
from services.coupling.exchange import CouplingEngine, CouplingParams

logger = structlog.get_logger()


@dataclass
class SimulationConfig:
    """Configuration for a flood simulation run."""

    city_id: str = "mumbai"
    duration_hours: float = 6.0
    cell_size_m: float = 30.0
    routing_dt_s: float = 2.0          # Surface flow time step
    coupling_stride_s: float = 60.0     # Coupling time step
    manning_n: float = 0.035            # Mixed urban roughness
    horton_params: HortonParams = field(default_factory=HortonParams)
    coupling_params: CouplingParams = field(default_factory=CouplingParams)
    snapshot_interval_s: float = 300.0  # Save snapshot every 5 min


@dataclass
class SimulationSnapshot:
    """A snapshot of the simulation state at a point in time."""

    time_s: float
    max_depth_m: float
    mean_depth_m: float
    flooded_cells: int
    total_volume_m3: float
    depth_grid: Optional[np.ndarray] = None  # Set to None if not storing full grids


@dataclass
class SimulationResult:
    """Complete result of a simulation run."""

    config: SimulationConfig
    started_at: datetime
    finished_at: Optional[datetime] = None
    snapshots: list[SimulationSnapshot] = field(default_factory=list)
    mass_balance: Optional[MassBalance] = None
    total_steps: int = 0
    coupling_events: int = 0
    max_depth_m: float = 0.0
    max_flooded_cells: int = 0
    final_depth_grid: Optional[np.ndarray] = None
    max_depth_grid: Optional[np.ndarray] = None


def run_simulation(
    dem: np.ndarray,
    rainfall_schedule: list[tuple[float, float]],
    imperviousness: np.ndarray,
    coupling_points: Optional[list[dict]] = None,
    drainage_heads: Optional[dict[str, float]] = None,
    config: Optional[SimulationConfig] = None,
) -> SimulationResult:
    """Run a complete flood simulation.

    Args:
        dem: 2D elevation grid (metres)
        rainfall_schedule: List of (time_hours, rate_mmh) pairs
        imperviousness: 2D imperviousness fraction grid (0-1)
        coupling_points: List of {node_id, row, col} for drain locations
        drainage_heads: Dict of node_id → hydraulic head (metres)
        config: Simulation configuration

    Returns:
        SimulationResult with snapshots and mass balance
    """
    if config is None:
        config = SimulationConfig()

    result = SimulationResult(
        config=config,
        started_at=datetime.now(timezone.utc),
    )

    # Initialize surface state
    state = initialize_surface(dem, config.cell_size_m, config.manning_n)

    # Initialize coupling engine
    coupling_engine = CouplingEngine(config.coupling_params)
    if coupling_points is None:
        coupling_points = []
    if drainage_heads is None:
        drainage_heads = {}

    # Simulation loop
    total_time_s = config.duration_hours * 3600.0
    coupling_accumulator_s = 0.0
    snapshot_accumulator_s = 0.0
    step = 0

    # Build rainfall interpolation
    def get_rainfall_rate(t_hours: float) -> float:
        """Interpolate rainfall rate at time t."""
        if not rainfall_schedule:
            return 0.0
        for i in range(len(rainfall_schedule) - 1):
            t0, r0 = rainfall_schedule[i]
            t1, r1 = rainfall_schedule[i + 1]
            if t0 <= t_hours <= t1:
                dt = t1 - t0
                if dt < 1e-12:  # Guard against duplicate timestamps
                    return r0
                frac = (t_hours - t0) / dt
                return r0 + frac * (r1 - r0)
        # Before first or after last: use nearest endpoint
        if t_hours <= rainfall_schedule[0][0]:
            return rainfall_schedule[0][1]
        return rainfall_schedule[-1][1]

    logger.info(
        "Starting simulation",
        city=config.city_id,
        duration_h=config.duration_hours,
        grid_shape=dem.shape,
        cell_size=config.cell_size_m,
    )

    max_depth_grid = state.depth.copy()

    while state.time_s < total_time_s:
        dt = config.routing_dt_s
        t_hours = state.time_s / 3600.0

        # 1. Get current rainfall rate
        rain_rate = get_rainfall_rate(t_hours)

        # 2. Apply rainfall
        if rain_rate > 0:
            apply_rainfall(state, rain_rate, dt)

        # 3. Compute and apply infiltration
        infil = horton_infiltration_grid(
            np.full_like(state.depth, rain_rate),
            t_hours,
            imperviousness,
            config.horton_params,
        )
        apply_infiltration(state, infil, dt)

        # 4. Route surface flow
        route_flow_step(state, dt)

        # Track max depth grid
        max_depth_grid = np.maximum(max_depth_grid, state.depth)

        # 5. Surface-drainage coupling (at coupling stride)
        coupling_accumulator_s += dt
        if coupling_accumulator_s >= config.coupling_stride_s and coupling_points:
            coupling_engine.compute_all_exchanges(
                state.depth, state.dem, coupling_points,
                drainage_heads, config.cell_size_m,
                config.coupling_stride_s,
            )
            coupling_accumulator_s = 0.0

        # 6. Record snapshot
        snapshot_accumulator_s += dt
        if snapshot_accumulator_s >= config.snapshot_interval_s:
            snapshot = SimulationSnapshot(
                time_s=state.time_s,
                max_depth_m=state.max_depth,
                mean_depth_m=float(np.mean(state.depth)),
                flooded_cells=state.flooded_cells,
                total_volume_m3=state.total_volume_m3,
                depth_grid=state.depth.copy(),
            )
            result.snapshots.append(snapshot)
            snapshot_accumulator_s = 0.0

            # Track maximums
            result.max_depth_m = max(result.max_depth_m, snapshot.max_depth_m)
            result.max_flooded_cells = max(result.max_flooded_cells, snapshot.flooded_cells)

        step += 1

    # Final mass balance
    result.mass_balance = MassBalance(
        total_rainfall_m3=state.total_rainfall_m3,
        total_infiltration_m3=state.total_infiltration_m3,
        total_boundary_outflow_m3=state.total_outflow_m3,
        initial_surface_volume_m3=0.0,
        final_surface_volume_m3=state.total_volume_m3,
    )
    result.total_steps = step
    result.coupling_events = coupling_engine.ledger.exchange_events
    result.finished_at = datetime.now(timezone.utc)
    result.final_depth_grid = state.depth.copy()
    result.max_depth_grid = max_depth_grid.copy()


    closure = result.mass_balance.compute_closure()
    logger.info(
        "Simulation complete",
        steps=step,
        max_depth_m=round(result.max_depth_m, 3),
        max_flooded_cells=result.max_flooded_cells,
        mass_balance_error_pct=round(closure, 2),
        coupling_events=result.coupling_events,
    )

    return result
