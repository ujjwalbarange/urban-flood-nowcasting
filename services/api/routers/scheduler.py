"""Scheduler API router — control the automated nowcast scheduler.

Phase 2B: Provides endpoints to start/stop/pause/resume the scheduler
and view its operational state.
"""

from __future__ import annotations

from typing import Optional

import structlog
from fastapi import APIRouter, Query

from services.nowcast.scheduler import (
    get_scheduler_state,
    start_scheduler,
    stop_scheduler,
    pause_scheduler,
    resume_scheduler,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/scheduler", tags=["Scheduler"])


@router.get("/status")
async def get_status():
    """Get the current scheduler status and operational metrics."""
    state = get_scheduler_state()
    return state.to_dict()


@router.post("/start")
async def start(
    interval_minutes: int = Query(15, ge=1, le=60, description="Interval between nowcast cycles in minutes"),
    catchments: Optional[str] = Query(None, description="Comma-separated catchment keys"),
    grid_size: int = Query(60, ge=20, le=120),
    duration_hours: float = Query(3.0, ge=0.5, le=6.0),
):
    """Start the automated nowcast scheduler.

    Default: runs every 15 minutes on hindmata_dadar catchment.
    """
    catchment_list = catchments.split(",") if catchments else None

    state = await start_scheduler(
        interval_seconds=interval_minutes * 60,
        catchments=catchment_list,
        grid_size=grid_size,
        duration_hours=duration_hours,
    )
    return {
        "action": "started",
        "state": state.to_dict(),
    }


@router.post("/stop")
async def stop():
    """Stop the automated nowcast scheduler."""
    state = await stop_scheduler()
    return {
        "action": "stopped",
        "state": state.to_dict(),
    }


@router.post("/pause")
async def pause():
    """Pause the scheduler (keeps running but skips cycles)."""
    state = await pause_scheduler()
    return {
        "action": "paused",
        "state": state.to_dict(),
    }


@router.post("/resume")
async def resume():
    """Resume a paused scheduler."""
    state = await resume_scheduler()
    return {
        "action": "resumed",
        "state": state.to_dict(),
    }
