"""API Router for Historical Flood Event Replay.

Provides endpoints for:
- Listing available historical events
- Running a replay simulation
- Checking replay status
- Retrieving replay results
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

import structlog

logger = structlog.get_logger()

router = APIRouter(prefix="/api/replay", tags=["Historical Replay"])


class ReplayRequest(BaseModel):
    """Request body for starting a historical replay."""
    event_key: str = "july_2024_cloudburst"
    fusion_mode: str = "hem_only"
    grid_size: int = 60
    catchment: str = "mumbai"
    tide_scenario: str = "observed"
    insat_weight: float = 0.6
    gpm_weight: float = 0.4
    notes: str = ""


@router.get("/events")
async def list_events():
    """List all available historical flood events for replay."""
    from services.nowcast.historical_replay import list_available_events
    return {"events": list_available_events()}


@router.post("/run")
async def start_replay(request: ReplayRequest):
    """Run a historical flood event replay simulation.

    This executes the complete physics pipeline using real observed data.
    """
    from services.nowcast.historical_replay import (
        HISTORICAL_EVENTS, ReplayConfig, run_historical_replay, persist_replay_result,
    )

    event = HISTORICAL_EVENTS.get(request.event_key)
    if not event:
        raise HTTPException(
            status_code=404,
            detail=f"Event '{request.event_key}' not found. "
                   f"Available: {list(HISTORICAL_EVENTS.keys())}"
        )

    config = ReplayConfig(
        event=event,
        fusion_mode=request.fusion_mode,
        grid_size=request.grid_size,
        catchment=request.catchment,
        tide_scenario=request.tide_scenario,
        insat_weight=request.insat_weight,
        gpm_weight=request.gpm_weight,
        notes=request.notes,
    )

    logger.info(
        "Starting historical replay",
        event=event.name,
        mode=request.fusion_mode,
        grid=request.grid_size,
    )

    result = await run_historical_replay(config)

    # Persist to database
    await persist_replay_result(result)

    # Convert for JSON response (exclude numpy arrays)
    response = {
        "simulation_id": result.simulation_id,
        "event_id": result.event_id,
        "event_name": result.event_name,
        "status": result.status,
        "error": result.error,
        "started_at": result.started_at,
        "completed_at": result.completed_at,
        "runtime_seconds": result.runtime_seconds,
        "fusion_mode": result.fusion_mode,
        "rainfall": {
            "source": result.rainfall_source,
            "granules": result.rainfall_granules,
            "cumulative_mm": result.rainfall_cumulative_mm,
            "peak_rate_mmh": result.rainfall_peak_mmh,
            "fusion_metadata": result.fusion_metadata,
        },
        "spatial_params": {
            "avg_imperviousness": result.avg_imperviousness,
            "avg_manning_n": result.avg_manning_n,
            "source": result.spatial_param_source,
            "coverage_pct": result.spatial_coverage_pct,
        },
        "flood_results": {
            "max_depth_m": result.max_depth_m,
            "mean_depth_m": result.mean_depth_m,
            "flooded_cells": result.flooded_cells,
            "flooded_area_km2": result.flooded_area_km2,
        },
        "drainage": {
            "nodes_coupled": result.drainage_nodes_coupled,
            "coupling_events": result.coupling_events,
        },
        "mass_balance": {
            "rainfall_volume_m3": result.total_rainfall_volume_m3,
            "infiltration_volume_m3": result.total_infiltration_volume_m3,
            "surface_storage_m3": result.total_surface_storage_m3,
            "drainage_exchange_m3": result.total_drainage_exchange_m3,
            "error_pct": result.mass_balance_error_pct,
        },
        "provenance": {
            "input_datasets": result.input_datasets,
            "model_version": result.model_version,
            "assumptions": result.assumptions,
        },
    }

    return response
