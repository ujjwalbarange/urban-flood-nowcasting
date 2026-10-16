"""Stage 5: Historical Flood Event Replay System.

Replays known historical flood events through the complete physics pipeline
using REAL observed rainfall data (INSAT-3DR, GPM, AWS) instead of live forecasts.

This is the MAIN milestone: produce a reproducible, validated simulation
with full provenance for the July 8 2024 Mumbai cloudburst event.

Chain:
RAIN → FUSION → INFILTRATION → RUNOFF → 2D FLOW → DRAINAGE → TIDE → FLOOD → EXPOSURE → RISK
"""

from __future__ import annotations

import asyncio
import json
import os
import ssl
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import numpy as np
import structlog

logger = structlog.get_logger()


@dataclass
class HistoricalEvent:
    """Defines a historical flood event for replay."""
    event_id: str
    name: str
    start_time: datetime
    end_time: datetime
    description: str = ""
    known_flood_locations: List[str] = field(default_factory=list)
    expected_severity: str = "unknown"
    reference_rainfall_24h_mm: float = 0.0


@dataclass
class ReplayConfig:
    """Configuration for a historical replay simulation."""
    event: HistoricalEvent
    fusion_mode: str = "hem_only"           # Rainfall fusion mode
    insat_weight: float = 0.6
    gpm_weight: float = 0.4
    grid_size: int = 60                     # Max DEM grid dimension
    catchment: str = "mumbai"               # Catchment key
    tide_scenario: str = "observed"         # observed / normal / high / extreme
    tide_height_override_m: Optional[float] = None  # manual tide override
    include_drainage: bool = True
    routing_dt_s: float = 2.0
    notes: str = ""


@dataclass
class ReplayResult:
    """Complete output from a historical replay simulation."""
    simulation_id: str = ""
    event_id: str = ""
    event_name: str = ""
    status: str = "pending"
    error: Optional[str] = None

    # Timing
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    runtime_seconds: float = 0.0

    # Configuration
    fusion_mode: str = ""
    catchment: str = ""
    grid_shape: Tuple[int, int] = (0, 0)
    cell_size_m: float = 0.0
    tide_scenario: str = ""

    # Rainfall
    rainfall_source: str = ""
    rainfall_granules: int = 0
    rainfall_cumulative_mm: float = 0.0
    rainfall_peak_mmh: float = 0.0
    fusion_metadata: Dict = field(default_factory=dict)

    # Spatial parameters
    avg_imperviousness: float = 0.0
    avg_manning_n: float = 0.0
    spatial_param_source: str = ""
    spatial_coverage_pct: float = 0.0

    # Flood results
    max_depth_m: float = 0.0
    mean_depth_m: float = 0.0
    flooded_cells: int = 0
    flooded_area_km2: float = 0.0
    max_depth_grid: Optional[np.ndarray] = None

    # Drainage coupling
    drainage_nodes_coupled: int = 0
    coupling_events: int = 0

    # Tide and Coastal
    tide_peak_m_cd: float = 0.0
    tide_peak_m_msl: float = 0.0
    coastal_flooded_cells: int = 0
    coastal_flooded_area_km2: float = 0.0
    peak_timing_hours: float = 0.0
    total_tide_inflow_m3: float = 0.0

    # Mass balance
    total_rainfall_volume_m3: float = 0.0
    total_infiltration_volume_m3: float = 0.0
    total_surface_storage_m3: float = 0.0
    total_drainage_exchange_m3: float = 0.0
    mass_balance_error_pct: float = 0.0


    # Validation (filled later by Stage 7)
    hotspot_hit_rate: Optional[float] = None
    validation_metrics: Dict = field(default_factory=dict)

    # Provenance
    input_datasets: List[str] = field(default_factory=list)
    model_version: str = "mufns_v1.0_physics"
    assumptions: List[str] = field(default_factory=list)


# Pre-defined historical events from the database
HISTORICAL_EVENTS = {
    "july_2024_cloudburst": HistoricalEvent(
        event_id="july_2024_cloudburst",
        name="July 8 2024 Mumbai Monsoon Deluge",
        start_time=datetime(2024, 7, 7, 18, 0, tzinfo=timezone.utc),
        end_time=datetime(2024, 7, 9, 6, 0, tzinfo=timezone.utc),
        description="Extreme rainfall causing widespread flooding across Mumbai. "
                    "Hindmata, Khar Subway, Andheri Subway, Milan Subway submerged.",
        known_flood_locations=[
            "Hindmata Cinema", "Khar Subway", "Andheri Subway",
            "Milan Subway", "King's Circle", "Sion Station",
            "Kurla Railway Tracks", "Malad Subway", "Dahisar Subway"
        ],
        expected_severity="Catastrophic",
        reference_rainfall_24h_mm=315.0,
    ),
    "july_2024_late": HistoricalEvent(
        event_id="july_2024_late",
        name="July 23-26 2024 Mumbai Monsoon Surge",
        start_time=datetime(2024, 7, 23, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2024, 7, 26, 0, 0, tzinfo=timezone.utc),
        description="Sustained heavy rainfall over 4 days causing drainage overload.",
        expected_severity="Severe",
    ),
    "aug_2025_monsoon": HistoricalEvent(
        event_id="aug_2025_monsoon",
        name="August 13-21 2025 Mumbai Heavy Rain",
        start_time=datetime(2025, 8, 13, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2025, 8, 21, 0, 0, tzinfo=timezone.utc),
        description="Extended heavy rainfall episode in August 2025.",
        expected_severity="Severe",
    ),
}


async def run_historical_replay(config: ReplayConfig) -> ReplayResult:
    """Execute a complete historical flood event replay.

    Uses REAL observed data instead of live weather forecasts.
    Returns a fully-provenanced ReplayResult.
    """
    from services.rainfall.rainfall_fusion import RainfallFusionEngine, RainfallFusionMode
    from services.terrain.dem_loader import get_catchment_dem
    from services.terrain.conditioning import fill_sinks
    from services.terrain.spatial_params import load_spatial_parameters_async
    from services.flood.engine import SimulationConfig, run_simulation
    from services.hydrology.infiltration import HortonParams
    from services.nowcast.pipeline import map_drainage_nodes_to_grid

    sim_id = str(uuid4())
    result = ReplayResult(
        simulation_id=sim_id,
        event_id=config.event.event_id,
        event_name=config.event.name,
        started_at=datetime.now(timezone.utc).isoformat(),
        fusion_mode=config.fusion_mode,
        catchment=config.catchment,
        tide_scenario=config.tide_scenario,
    )

    t0 = time.time()

    try:
        # === STEP 1: RAINFALL FORCING FROM REAL HISTORICAL DATA ===
        logger.info(
            "Historical replay: fetching rainfall",
            event_name=config.event.name,
            mode=config.fusion_mode,
            window=f"{config.event.start_time} to {config.event.end_time}",
        )

        if config.tide_scenario == "tide_only":
            duration_hours = max(3.0, (config.event.end_time - config.event.start_time).total_seconds() / 3600.0)
            schedule = [(0.0, 0.0), (duration_hours, 0.0)]
            result.rainfall_source = "None (tide_only scenario)"
            result.rainfall_cumulative_mm = 0.0
            result.rainfall_peak_mmh = 0.0
            result.rainfall_granules = 0
            result.input_datasets = ["Tide: Apollo Bunder tide_observations"]
            logger.info("Historical replay: tide_only mode selected, rainfall forcing disabled")
        else:
            try:
                fusion_mode = RainfallFusionMode(config.fusion_mode)
            except ValueError:
                fusion_mode = RainfallFusionMode.HEM_ONLY

            engine = RainfallFusionEngine(
                mode=fusion_mode,
                insat_weight=config.insat_weight,
                gpm_weight=config.gpm_weight,
            )

            rainfall = await engine.get_rainfall_forcing(
                start_time=config.event.start_time,
                end_time=config.event.end_time,
            )

            result.rainfall_source = ", ".join(rainfall.get("sources_used", []))
            result.rainfall_cumulative_mm = rainfall.get("cumulative_mm", 0.0)
            result.rainfall_peak_mmh = rainfall.get("peak_rate_mmh", 0.0)
            result.fusion_metadata = rainfall.get("fusion_metadata", {})
            result.input_datasets = list(rainfall.get("sources_used", []))

            ts = rainfall.get("timeseries", [])
            result.rainfall_granules = len(ts)

            if not ts:
                result.status = "failed"
                result.error = f"No rainfall data found for {config.event.name} in mode {config.fusion_mode}"
                return result

            logger.info(
                "Rainfall forcing loaded",
                granules=len(ts),
                cumulative_mm=result.rainfall_cumulative_mm,
                peak_mmh=result.rainfall_peak_mmh,
            )

            # Build rainfall schedule: [(hour, rate_mmh), ...]
            event_start = config.event.start_time
            schedule = []
            for step in ts:
                t_str = step.get("time", "")
                rate = step.get("rate_mmh", step.get("mumbai_rate_mmh", 0.0))
                try:
                    t = datetime.fromisoformat(t_str) if isinstance(t_str, str) else t_str
                    offset_hours = (t - event_start).total_seconds() / 3600.0
                    schedule.append((offset_hours, float(rate)))
                except (ValueError, TypeError):
                    continue

            if not schedule:
                result.status = "failed"
                result.error = "Could not build rainfall schedule from timeseries"
                return result

            duration_hours = max(s[0] for s in schedule) - min(s[0] for s in schedule)
            if duration_hours < 0.5:
                duration_hours = 3.0

        # === STEP 2: LOAD DEM ===
        logger.info("Loading DEM and terrain data")
        dem_raw, georef = get_catchment_dem(config.catchment, max_dim=config.grid_size)
        dem = fill_sinks(dem_raw.astype(np.float64))

        result.grid_shape = dem.shape
        result.cell_size_m = georef["cell_size_m"]

        # === STEP 3: SPATIAL PARAMETERS (real LULC + imperviousness) ===
        logger.info("Loading spatial parameters from PostGIS")
        try:
            spatial = await load_spatial_parameters_async(georef, dem.shape)
            imperviousness = spatial.imperviousness
            result.avg_imperviousness = round(float(np.mean(imperviousness)), 3)
            result.avg_manning_n = round(float(np.mean(spatial.manning_n)), 4)
            result.spatial_param_source = spatial.lulc_source
            result.spatial_coverage_pct = spatial.coverage_pct
            result.assumptions.append(
                f"LULC-derived parameters from literature (quality: {spatial.quality_status})"
            )

            avg_f0 = float(np.mean(spatial.horton_f0))
            avg_fmin = float(np.mean(spatial.horton_fmin))
            avg_k = float(np.mean(spatial.horton_k))
            avg_manning = float(np.mean(spatial.manning_n))
        except Exception as e:
            logger.warning("Spatial params failed, using defaults", error=str(e))
            from services.config.lulc_params import DEFAULT_PARAMS
            imperviousness = np.full(dem.shape, DEFAULT_PARAMS["imperviousness"])
            avg_f0, avg_fmin, avg_k = 76.0, 3.8, 2.0
            avg_manning = 0.035
            result.avg_imperviousness = 0.80
            result.avg_manning_n = 0.035
            result.spatial_param_source = "default (PostGIS unavailable)"
            result.assumptions.append("Default imperviousness=0.80 (PostGIS unavailable)")

        # === STEP 4: DRAINAGE COUPLING ===
        logger.info("Mapping drainage nodes to DEM grid")
        coupling_points, drainage_heads = map_drainage_nodes_to_grid(georef, dem.shape)
        result.drainage_nodes_coupled = len(coupling_points)

        if not coupling_points:
            result.assumptions.append("No drainage coupling (nodes outside DEM grid or unavailable)")

        # === STEP 5: TIDE & COASTAL BOUNDARY INTEGRATION ===
        from services.coastal.tide_service import TideService, identify_coastal_boundary_mask
        tide_service = TideService()
        tide_sched = await tide_service.build_tide_schedule(
            scenario=config.tide_scenario,
            duration_hours=duration_hours,
            start_time=config.event.start_time,
        )
        result.tide_scenario = config.tide_scenario
        result.tide_peak_m_cd = tide_sched.peak_tide_m_cd
        result.tide_peak_m_msl = tide_sched.peak_tide_m_msl
        result.input_datasets.append(f"Tide: {tide_sched.provenance}")
        if tide_sched.quality_status != "observed":
            result.assumptions.append(f"Tidal boundary: {tide_sched.provenance} (status: {tide_sched.quality_status})")

        coastal_mask = identify_coastal_boundary_mask(dem, georef)

        # === STEP 6: CONFIGURE AND RUN SIMULATION ===
        sim_config = SimulationConfig(
            city_id="mumbai",
            duration_hours=duration_hours,
            cell_size_m=georef["cell_size_m"],
            routing_dt_s=config.routing_dt_s,
            coupling_stride_s=60.0,
            manning_n=avg_manning,
            horton_params=HortonParams(f0_mmh=avg_f0, f_min_mmh=avg_fmin, k_per_h=avg_k),
            tide_schedule=tide_sched.schedule,
            coastal_mask=coastal_mask,
        )

        logger.info(
            "Running 2D diffusive wave simulation",
            duration_hours=round(duration_hours, 1),
            grid_shape=dem.shape,
            manning_n=round(avg_manning, 4),
            horton_f0=round(avg_f0, 1),
            drainage_nodes=len(coupling_points),
            tide_scenario=config.tide_scenario,
            tide_peak_msl=result.tide_peak_m_msl,
        )

        sim_result = run_simulation(
            dem=dem,
            rainfall_schedule=schedule,
            imperviousness=imperviousness,
            coupling_points=coupling_points if coupling_points else None,
            drainage_heads=drainage_heads if drainage_heads else None,
            config=sim_config,
        )

        # === STEP 7: EXTRACT RESULTS ===
        result.max_depth_m = float(sim_result.max_depth_m)
        result.mean_depth_m = float(sim_result.mean_depth_m) if hasattr(sim_result, 'mean_depth_m') else 0.0
        result.max_depth_grid = sim_result.max_depth_grid
        result.coupling_events = sim_result.coupling_events if hasattr(sim_result, 'coupling_events') else 0
        result.coastal_flooded_cells = sim_result.coastal_flooded_cells
        result.coastal_flooded_area_km2 = sim_result.coastal_flooded_area_km2
        result.peak_timing_hours = sim_result.peak_timing_hours

        if sim_result.max_depth_grid is not None:
            depth_grid = sim_result.max_depth_grid
            flood_threshold_m = 0.05  # 5cm threshold
            flooded_mask = depth_grid > flood_threshold_m
            result.flooded_cells = int(np.sum(flooded_mask))
            result.flooded_area_km2 = round(
                result.flooded_cells * (result.cell_size_m ** 2) / 1e6, 4
            )
            if result.flooded_cells > 0:
                result.mean_depth_m = round(float(np.mean(depth_grid[flooded_mask])), 3)

        # === STEP 8: MASS BALANCE ===
        cell_area = result.cell_size_m ** 2
        n_cells = dem.shape[0] * dem.shape[1]
        total_area = n_cells * cell_area

        result.total_rainfall_volume_m3 = round(
            result.rainfall_cumulative_mm / 1000.0 * total_area, 1
        )

        if hasattr(sim_result, 'mass_balance') and sim_result.mass_balance:
            mb = sim_result.mass_balance
            result.total_tide_inflow_m3 = mb.total_tide_inflow_m3
            result.total_infiltration_volume_m3 = mb.total_infiltration_m3
            result.total_surface_storage_m3 = mb.final_surface_volume_m3
            result.total_drainage_exchange_m3 = mb.total_drainage_exchange_m3
            result.mass_balance_error_pct = mb.closure_error_pct

        else:
            # Estimate from grid
            if sim_result.max_depth_grid is not None:
                result.total_surface_storage_m3 = round(
                    float(np.sum(sim_result.max_depth_grid)) * cell_area, 1
                )
            result.assumptions.append("Mass balance estimated from final state (no timestep tracking)")

        # === STEP 8: RECORD PROVENANCE ===
        result.input_datasets.extend([
            "Copernicus GLO-30 DEM",
            f"LULC (69 classes, source={result.spatial_param_source})",
            f"Impervious surface ({result.spatial_coverage_pct}% coverage)",
            f"Drainage nodes ({result.drainage_nodes_coupled} coupled)",
        ])

        result.status = "completed"
        result.completed_at = datetime.now(timezone.utc).isoformat()
        result.runtime_seconds = round(time.time() - t0, 2)

        logger.info(
            "Historical replay completed",
            simulation_id=sim_id,
            event_name=config.event.name,
            max_depth_m=result.max_depth_m,
            flooded_area_km2=result.flooded_area_km2,
            runtime_s=result.runtime_seconds,
        )

    except Exception as e:
        result.status = "failed"
        result.error = f"{type(e).__name__}: {str(e)}"
        result.completed_at = datetime.now(timezone.utc).isoformat()
        result.runtime_seconds = round(time.time() - t0, 2)
        logger.error("Historical replay failed", error=str(e), event_name=config.event.name)

    return result


async def persist_replay_result(result: ReplayResult) -> bool:
    """Persist replay result to PostGIS for reproducibility (Stage 9)."""
    from dotenv import load_dotenv
    load_dotenv()

    raw_url = os.environ.get("DATABASE_URL", "")
    url = raw_url.replace("postgresql+asyncpg://", "postgresql://").split("?")[0]
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        import asyncpg
        conn = await asyncpg.connect(url, ssl=ctx)

        from uuid import UUID as _UUID

        # Parse timestamps from ISO strings to datetime objects for asyncpg
        started_dt = datetime.fromisoformat(result.started_at) if isinstance(result.started_at, str) else result.started_at
        completed_dt = datetime.fromisoformat(result.completed_at) if isinstance(result.completed_at, str) else result.completed_at
        run_uuid = _UUID(result.simulation_id)

        # Insert into simulation_runs
        await conn.execute("""
            INSERT INTO simulation_runs (
                run_id, city_id, mode, status, created_at, started_at, completed_at,
                scenario_config, mass_balance, output_manifest, error
            ) VALUES ($1, $2, $3, $4, NOW(), $5, $6, $7, $8, $9, $10)
            ON CONFLICT (run_id) DO UPDATE SET
                status=$4, completed_at=$6, mass_balance=$8,
                output_manifest=$9, error=$10
        """,
            run_uuid,
            "mumbai",
            f"historical_replay_{result.fusion_mode}",
            result.status,
            started_dt,
            completed_dt,
            json.dumps({
                "event_id": result.event_id,
                "event_name": result.event_name,
                "fusion_mode": result.fusion_mode,
                "tide_scenario": result.tide_scenario,
                "tide_peak_m_cd": result.tide_peak_m_cd,
                "tide_peak_m_msl": result.tide_peak_m_msl,
                "grid_shape": list(result.grid_shape),
                "cell_size_m": result.cell_size_m,
                "avg_imperviousness": result.avg_imperviousness,
                "avg_manning_n": result.avg_manning_n,
                "spatial_param_source": result.spatial_param_source,
                "input_datasets": result.input_datasets,
                "assumptions": result.assumptions,
            }),
            json.dumps({
                "rainfall_volume_m3": result.total_rainfall_volume_m3,
                "tide_inflow_volume_m3": result.total_tide_inflow_m3,
                "infiltration_volume_m3": result.total_infiltration_volume_m3,
                "surface_storage_m3": result.total_surface_storage_m3,
                "drainage_exchange_m3": result.total_drainage_exchange_m3,
                "error_pct": result.mass_balance_error_pct,
            }),
            json.dumps({
                "max_depth_m": result.max_depth_m,
                "mean_depth_m": result.mean_depth_m,
                "flooded_cells": result.flooded_cells,
                "flooded_area_km2": result.flooded_area_km2,
                "coastal_flooded_cells": result.coastal_flooded_cells,
                "coastal_flooded_area_km2": result.coastal_flooded_area_km2,
                "peak_timing_hours": result.peak_timing_hours,
                "rainfall_cumulative_mm": result.rainfall_cumulative_mm,
                "rainfall_peak_mmh": result.rainfall_peak_mmh,
                "drainage_nodes_coupled": result.drainage_nodes_coupled,
                "runtime_seconds": result.runtime_seconds,
                "fusion_metadata": result.fusion_metadata,
            }),
            json.dumps({"message": result.error}) if result.error else None,
        )


        await conn.close()
        logger.info("Replay result persisted to PostGIS", sim_id=result.simulation_id)
        return True

    except Exception as e:
        logger.warning("Failed to persist replay result", error=str(e))
        return False


def list_available_events() -> List[dict]:
    """List all pre-defined historical events available for replay."""
    events = []
    for key, ev in HISTORICAL_EVENTS.items():
        events.append({
            "event_key": key,
            "event_id": ev.event_id,
            "name": ev.name,
            "start_time": ev.start_time.isoformat(),
            "end_time": ev.end_time.isoformat(),
            "severity": ev.expected_severity,
            "known_flood_locations": ev.known_flood_locations,
        })
    return events
