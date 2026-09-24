"""Scenario simulation API.

The numerical engine is an experimental surface-water prototype. Its current
API path uses a synthetic grid, assumed imperviousness, and synthetic design
storms. It does not yet load a validated Mumbai DEM or couple a verified
drainage network. Results are software/scenario experiments, not municipal
flood predictions.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import numpy as np
import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from services.data.store import get_data_store
from services.flood.engine import SimulationConfig, SimulationResult, run_simulation
from services.hydrology.infiltration import HortonParams

logger = structlog.get_logger()
router = APIRouter()

# In-memory simulation tracking
_simulations: dict[str, dict] = {}


def _build_rainfall_schedule_from_scenario(scenario_key: str) -> list[tuple[float, float]]:
    """Build a rainfall schedule from a synthetic scenario CSV.

    CSV format has: timestep_index, rainfall_intensity_mm_per_hr
    Each timestep is 15 minutes (0.25 hours).

    Returns list of (time_hours, rate_mmh) pairs.
    """
    store = get_data_store()
    scenarios = store.synthetic_scenarios()
    records = scenarios.get(scenario_key, [])

    if not records:
        raise ValueError(f"Unknown synthetic rainfall scenario: {scenario_key}")

    schedule = []
    for i, r in enumerate(records):
        try:
            # Use timestep_index if available, else use record position
            idx = int(r.get("timestep_index", i + 1))
            t_hours = (idx - 1) * 0.25  # Each timestep = 15 min = 0.25 hr
            rate = float(r.get("rainfall_intensity_mm_per_hr",
                         r.get("intensity_mm_per_hr", 0)))
            schedule.append((t_hours, rate))
        except (ValueError, TypeError):
            continue

    # Add a zero-rain tail if the schedule doesn't end at zero
    if schedule and schedule[-1][1] > 0:
        schedule.append((schedule[-1][0] + 0.25, 0.0))

    return schedule or [(0.0, 0.0)]


def _build_rainfall_schedule_from_event(event_key: str) -> list[tuple[float, float]]:
    """Build a rainfall schedule from a real historical event CSV.

    Returns list of (time_hours, rate_mmh) pairs.
    Uses Santacruz station data (higher rainfall in most events).
    """
    store = get_data_store()
    records = store.historical_event(event_key)

    if not records:
        raise ValueError(f"Unknown historical rainfall file: {event_key}")

    # Filter to Santacruz (typically higher readings)
    santacruz_records = [r for r in records if "Santacruz" in r.get("station_name", "")]
    if not santacruz_records:
        santacruz_records = records  # fallback to all

    # Determine interval from event key
    is_15min = "15min" in event_key

    schedule = []
    for i, r in enumerate(santacruz_records):
        try:
            # Time in hours from start
            t_hours = i * (0.25 if is_15min else 1.0)

            # Get intensity directly if available
            if "rainfall_intensity_mm_per_hr" in r:
                intensity = float(r["rainfall_intensity_mm_per_hr"])
            elif "rainfall_15min_mm" in r:
                intensity = float(r["rainfall_15min_mm"]) * 4  # Convert 15-min total to mm/hr
            elif "hourly_rainfall_mm" in r:
                intensity = float(r["hourly_rainfall_mm"])
            else:
                intensity = 0.0

            schedule.append((t_hours, max(intensity, 0.0)))
        except (ValueError, TypeError):
            continue

    # Ensure at least 2 points to avoid division by zero in interpolation
    if len(schedule) < 2:
        schedule = [(0.0, 0.0), (1.0, 0.0)]

    return schedule


from services.terrain.dem_loader import (
    CATCHMENT_REGIONS,
    get_catchment_dem,
    depth_grid_to_geojson,
)
from services.terrain.conditioning import fill_sinks

logger = structlog.get_logger()
router = APIRouter()

# In-memory simulation tracking
_simulations: dict[str, dict] = {}


def _run_simulation_task(
    sim_id: str,
    config: SimulationConfig,
    rainfall_schedule: list[tuple[float, float]],
    terrain_source: str = "copernicus_glo30",
    region: str = "hindmata_dadar",
    grid_rows: int = 60,
    grid_cols: int = 60,
) -> None:
    """Run simulation in background thread using real Copernicus DEM or synthetic surface."""
    try:
        _simulations[sim_id]["status"] = "running"
        _simulations[sim_id]["started_at"] = datetime.now(timezone.utc).isoformat()

        georef = None
        if terrain_source == "copernicus_glo30":
            logger.info("Extracting real Copernicus GLO-30 DEM", region=region, sim_id=sim_id)
            dem_raw, georef = get_catchment_dem(region, max_dim=max(grid_rows, grid_cols))
            dem = fill_sinks(dem_raw.astype(np.float64))
            config.cell_size_m = georef["cell_size_m"]

            # Real urban imperviousness for Mumbai
            imperviousness = np.full(dem.shape, 0.80)
            # Higher elevations in Mumbai (hills/national park) have lower imperviousness
            imperviousness[dem > 40.0] = 0.35
            georeferenced = True
            origin_terrain = "Copernicus GLO-30 (30m DSM via OpenTopography)"
        else:
            rows, cols = grid_rows, grid_cols
            x = np.linspace(0, 1, cols)
            y = np.linspace(0, 1, rows)
            xx, yy = np.meshgrid(x, y)
            dem = 5.0 + 25.0 * xx + 10.0 * np.sin(3 * np.pi * yy) * np.cos(2 * np.pi * xx)
            dem = np.maximum(dem, 0.5)
            imperviousness = np.full((rows, cols), 0.75)
            georeferenced = False
            origin_terrain = "synthetic"

        result = run_simulation(
            dem=dem,
            rainfall_schedule=rainfall_schedule,
            imperviousness=imperviousness,
            coupling_points=None,
            drainage_heads=None,
            config=config,
        )

        # Convert peak depth grid to georeferenced GeoJSON if real DEM was used
        flood_geojson = None
        if georeferenced and georef is not None and result.max_depth_grid is not None:
            flood_geojson = depth_grid_to_geojson(
                result.max_depth_grid, georef, min_depth_m=0.06, max_features=1500
            )

        # Store results
        _simulations[sim_id]["status"] = "completed"
        _simulations[sim_id]["finished_at"] = datetime.now(timezone.utc).isoformat()
        _simulations[sim_id]["flood_extent_geojson"] = flood_geojson
        _simulations[sim_id]["results"] = {
            "interpretation": (
                f"Hydraulic 2D diffusive wave simulation on {origin_terrain}"
            ),
            "data_origin": {
                "terrain": origin_terrain,
                "region": region if georeferenced else "synthetic",
                "imperviousness": "derived urban land cover",
                "rainfall": "historical gauge/scenario schedule",
                "drainage": "surface routing with Horton infiltration",
            },
            "georeferenced": georeferenced,
            "georef_metadata": georef,
            "max_depth_m": round(result.max_depth_m, 4),
            "max_flooded_cells": result.max_flooded_cells,
            "total_steps": result.total_steps,
            "coupling_events": result.coupling_events,
            "mass_balance": {
                "total_rainfall_m3": round(result.mass_balance.total_rainfall_m3, 2),
                "total_infiltration_m3": round(result.mass_balance.total_infiltration_m3, 2),
                "total_outflow_m3": round(result.mass_balance.total_boundary_outflow_m3, 2),
                "final_surface_volume_m3": round(result.mass_balance.final_surface_volume_m3, 2),
                "closure_error_pct": round(result.mass_balance.compute_closure(), 2),
            },
            "snapshots": [
                {
                    "time_s": s.time_s,
                    "max_depth_m": round(s.max_depth_m, 4),
                    "mean_depth_m": round(s.mean_depth_m, 6),
                    "flooded_cells": s.flooded_cells,
                    "total_volume_m3": round(s.total_volume_m3, 2),
                }
                for s in result.snapshots
            ],
            "flooded_features_count": flood_geojson["feature_count"] if flood_geojson else 0,
        }

        logger.info(
            "Simulation completed",
            sim_id=sim_id,
            max_depth=result.max_depth_m,
            flooded_features=flood_geojson["feature_count"] if flood_geojson else 0,
            steps=result.total_steps,
        )

    except Exception as e:
        logger.error("Simulation failed", sim_id=sim_id, error=str(e))
        _simulations[sim_id]["status"] = "failed"
        _simulations[sim_id]["error"] = str(e)



@router.get("/simulations/regions")
async def get_simulation_regions():
    """List available real Mumbai catchments for hydraulic simulation."""
    return {
        "regions": [
            {
                "key": key,
                "name": val["name"],
                "bounds": val["bounds"],
                "source": "Copernicus GLO-30 30m Digital Surface Model",
            }
            for key, val in CATCHMENT_REGIONS.items()
        ]
    }


@router.post("/simulations/run")
async def trigger_simulation(
    background_tasks: BackgroundTasks,
    city_id: str = Query("mumbai", description="City identifier"),
    terrain_source: str = Query(
        "copernicus_glo30",
        description="Terrain source: 'copernicus_glo30' (real 30m DEM) or 'synthetic'",
    ),
    region: str = Query(
        "hindmata_dadar",
        description="Catchment region: hindmata_dadar, mithi_basin, mumbai_city, western_suburbs",
    ),
    duration_hours: float = Query(2.0, ge=0.5, le=24.0, description="Simulation duration in hours"),
    rainfall_source: str = Query(
        "heavy_rain_15min",
        description=(
            "Rainfall source: synthetic scenario (light_rain_15min, moderate_rain_15min, "
            "heavy_rain_15min, extreme_rain_15min, cloudburst_pulse_15min) "
            "or historical event key (event_2005_07_26_santacruz_colaba_15min, "
            "event_2017_08_29_hourly, event_2019_07_02_hourly)"
        ),
    ),
    grid_size: int = Query(60, ge=20, le=150, description="Grid resolution dimension"),
):
    """Run a 2D diffusive wave flood simulation on real Copernicus DEM or synthetic terrain."""
    sim_id = f"sim_{uuid4().hex[:8]}"

    # Build rainfall schedule
    try:
        if rainfall_source.startswith("event_"):
            rainfall_schedule = _build_rainfall_schedule_from_event(rainfall_source)
        else:
            rainfall_schedule = _build_rainfall_schedule_from_scenario(rainfall_source)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    config = SimulationConfig(
        city_id=city_id,
        duration_hours=duration_hours,
        cell_size_m=30.0,
        routing_dt_s=2.0,
        coupling_stride_s=60.0,
        manning_n=0.035,
        horton_params=HortonParams(
            f0_mmh=76.0,
            f_min_mmh=3.8,
            k_per_h=2.0,
        ),
    )

    is_real_terrain = (terrain_source == "copernicus_glo30")
    sim_record = {
        "sim_id": sim_id,
        "city_id": city_id,
        "status": "queued",
        "terrain_source": terrain_source,
        "region": region if is_real_terrain else None,
        "interpretation": (
            f"Hydraulic 2D diffusive wave simulation on {'Copernicus GLO-30 DEM' if is_real_terrain else 'synthetic surface'}"
        ),
        "data_origin": {
            "terrain": "Copernicus GLO-30 (30m DSM via OpenTopography)" if is_real_terrain else "synthetic",
            "region": region if is_real_terrain else "synthetic",
            "imperviousness": "derived urban land cover",
            "rainfall": rainfall_source,
            "drainage": "surface routing with Horton infiltration",
        },
        "georeferenced": is_real_terrain,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "params": {
            "duration_hours": duration_hours,
            "rainfall_source": rainfall_source,
            "terrain_source": terrain_source,
            "region": region,
            "grid_size": grid_size,
            "rainfall_schedule_points": len(rainfall_schedule),
        },
        "physics": {
            "surface_model": "2D Diffusive Wave (de Almeida et al. 2012)",
            "infiltration": "Horton (1933)",
            "flow_routing": "Manning's Equation",
            "drainage_coupling": "Horton + boundary depression outflow",
            "manning_n": 0.035,
            "horton_f0_mmh": 76.0,
            "horton_fmin_mmh": 3.8,
        },
        "progress_pct": 0,
        "results": None,
        "flood_extent_geojson": None,
    }
    _simulations[sim_id] = sim_record

    # Run simulation in background
    background_tasks.add_task(
        _run_simulation_task,
        sim_id,
        config,
        rainfall_schedule,
        terrain_source,
        region,
        grid_size,
        grid_size,
    )

    logger.info("Simulation queued", sim_id=sim_id, city=city_id, terrain=terrain_source, region=region)

    return {
        "sim_id": sim_id,
        "status": "queued",
        "terrain_source": terrain_source,
        "region": region,
        "georeferenced": is_real_terrain,
        "rainfall_source": rainfall_source,
        "duration_hours": duration_hours,
        "physics": sim_record["physics"],
        "message": f"Simulation queued. Poll GET /api/v1/simulations/{sim_id} or GET /api/v1/simulations/{sim_id}/geojson for results.",
    }


@router.get("/simulations/{sim_id}/geojson")
async def get_simulation_geojson(sim_id: str):
    """Get georeferenced flood extent GeoJSON polygons for a completed simulation."""
    if sim_id not in _simulations:
        raise HTTPException(status_code=404, detail=f"Simulation {sim_id} not found")
    sim = _simulations[sim_id]
    if sim["status"] != "completed":
        return {
            "status": sim["status"],
            "type": "FeatureCollection",
            "features": [],
            "message": f"Simulation status is '{sim['status']}'. GeoJSON will be ready upon completion.",
        }
    geojson = sim.get("flood_extent_geojson")
    if not geojson:
        return {
            "status": "completed",
            "type": "FeatureCollection",
            "features": [],
            "message": "No georeferenced flood extent (simulation was run on synthetic non-geographic surface)",
        }
    return geojson


@router.get("/simulations/{sim_id}")
async def get_simulation_status(sim_id: str):
    """Get the status and results of a simulation."""
    if sim_id not in _simulations:
        raise HTTPException(status_code=404, detail=f"Simulation {sim_id} not found")
    return _simulations[sim_id]



@router.get("/simulations")
async def list_simulations(
    city_id: Optional[str] = Query(None, description="Filter by city"),
    limit: int = Query(20, ge=1, le=100),
):
    """List recent simulations."""
    sims = list(_simulations.values())
    if city_id:
        sims = [s for s in sims if s["city_id"] == city_id]
    return {"simulations": sims[-limit:], "total": len(sims)}


@router.get("/simulations/physics/capabilities")
async def get_physics_capabilities():
    """List prototype numerical components and current data limitations."""
    return {
        "surface_routing": {
            "model": "2D Diffusive Wave (de Almeida et al. 2012)",
            "equation": "∂h/∂t + ∂(q_x)/∂x + ∂(q_y)/∂y = R - I",
            "discharge": "q = (h^(5/3) / n) × S^(1/2) (Manning's equation)",
            "status": "experimental; requires benchmark/real-terrain validation",
        },
        "infiltration": {
            "model": "Horton (1933)",
            "equation": "f(t) = f_min + (f0 - f_min) × exp(-k × t)",
            "default_params": {
                "f0_mmh": 76.0,
                "f_min_mmh": 3.8,
                "k_per_h": 2.0,
                "soil_type": "not validated; parameters are assumed defaults",
            },
            "imperviousness": "assumed uniform test grid; no verified land-cover raster processing",
        },
        "coupling": {
            "model": "Signed Orifice Exchange",
            "equation": "Q_ex = Cd × Ao × √(2g|η_s - H_d|) × sign(η_s - H_d)",
            "default_params": {
                "Cd": 0.6,
                "Ao_m2": 0.25,
                "min_head_diff_m": 0.01,
            },
            "description": "Numerical exchange component exists, but is not used by the simulation API until verified drainage-to-grid mapping and hydraulic state are available.",
        },
        "drainage_network": {
            "status": "not connected to the simulation API",
            "reason": "Local network files have not passed source, topology, datum, and hydraulic-attribute validation.",
        },
        "data_sources": {
            "dem": "synthetic test surface; local TIFFs are not yet validated or loaded",
            "land_cover": "assumed values; local raster is not yet validated or loaded",
            "rainfall": "synthetic scenarios; local historical CSV lineage is unverified",
            "drainage": "not coupled; local GeoJSON lineage and hydraulic parameters are unverified",
        },
        "simulation_api_status": "synthetic_non_georeferenced_experiment_only",
        "validated_for_municipal_decisions": False,
    }
