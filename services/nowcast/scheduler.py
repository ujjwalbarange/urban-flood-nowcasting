"""Automated Nowcast Scheduler Service.

Runs the nowcast pipeline at configurable intervals (default: every 15 minutes).
Manages lifecycle, error recovery, and operational state.

Phase 2B: Replaces manual POST /nowcast/run with automated execution.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import Optional

import structlog

logger = structlog.get_logger()


@dataclass
class SchedulerState:
    """Current state of the nowcast scheduler."""
    is_running: bool = False
    interval_seconds: int = 900  # 15 minutes
    last_run_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_error_at: Optional[datetime] = None
    last_error_message: str = ""
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    consecutive_failures: int = 0
    current_catchments: list[str] = field(default_factory=lambda: ["hindmata_dadar"])
    grid_size: int = 60
    duration_hours: float = 3.0
    started_at: Optional[datetime] = None
    paused: bool = False

    def to_dict(self) -> dict:
        return {
            "is_running": self.is_running,
            "interval_seconds": self.interval_seconds,
            "interval_human": f"{self.interval_seconds // 60}min",
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "last_success_at": self.last_success_at.isoformat() if self.last_success_at else None,
            "last_error_at": self.last_error_at.isoformat() if self.last_error_at else None,
            "last_error_message": self.last_error_message,
            "total_runs": self.total_runs,
            "successful_runs": self.successful_runs,
            "failed_runs": self.failed_runs,
            "consecutive_failures": self.consecutive_failures,
            "success_rate_pct": round(100 * self.successful_runs / max(1, self.total_runs), 1),
            "current_catchments": self.current_catchments,
            "grid_size": self.grid_size,
            "duration_hours": self.duration_hours,
            "paused": self.paused,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "uptime_hours": round((datetime.now(timezone.utc) - self.started_at).total_seconds() / 3600, 2) if self.started_at else 0,
        }


# Global singleton scheduler state
_scheduler_state = SchedulerState()
_scheduler_task: Optional[asyncio.Task] = None


def get_scheduler_state() -> SchedulerState:
    """Get the current scheduler state."""
    return _scheduler_state


async def _run_single_cycle(state: SchedulerState) -> None:
    """Execute a single nowcast cycle across all configured catchments."""
    from services.nowcast.pipeline import run_nowcast_pipeline
    from services.data.quality import qc_mass_balance, compute_confidence

    state.last_run_at = datetime.now(timezone.utc)
    state.total_runs += 1

    try:
        for catchment in state.current_catchments:
            logger.info(
                "Scheduler: starting nowcast cycle",
                catchment=catchment,
                cycle=state.total_runs,
            )

            result = await run_nowcast_pipeline(
                catchment=catchment,
                duration_hours=state.duration_hours,
                grid_size=state.grid_size,
            )

            if result.status == "completed":
                # Apply QC checks
                mb_qc = qc_mass_balance(result.mass_balance_error_pct)

                # Compute confidence
                confidence = compute_confidence(
                    mass_balance_error_pct=result.mass_balance_error_pct,
                    rainfall_source=result.forcing_source or "open-meteo",
                    terrain_source=result.dem_source or "copernicus_glo30",
                    spatial_params_quality=getattr(result, "spatial_param_quality", "default"),
                    has_drainage_coupling=getattr(result, "drainage_nodes_coupled", 0) > 0,
                )

                # Attach confidence to result
                result.confidence_score = confidence.score
                result.confidence_level = confidence.level
                result.confidence_factors = confidence.factors

                logger.info(
                    "Scheduler: nowcast cycle completed",
                    catchment=catchment,
                    max_depth_m=round(result.max_depth_m, 3),
                    flooded_cells=result.flooded_cells,
                    confidence=confidence.level,
                    confidence_score=round(confidence.score, 1),
                    mass_balance_qc=mb_qc.flag.value,
                    runtime_s=round(result.runtime_seconds, 2),
                )
            else:
                logger.warning(
                    "Scheduler: nowcast cycle returned non-completed status",
                    catchment=catchment,
                    status=result.status,
                    error=result.error,
                )
                raise RuntimeError(f"Nowcast returned status={result.status}: {result.error}")

        # Success path
        state.last_success_at = datetime.now(timezone.utc)
        state.successful_runs += 1
        state.consecutive_failures = 0

    except Exception as e:
        state.last_error_at = datetime.now(timezone.utc)
        state.last_error_message = str(e)
        state.failed_runs += 1
        state.consecutive_failures += 1

        logger.error(
            "Scheduler: nowcast cycle failed",
            error=str(e),
            consecutive_failures=state.consecutive_failures,
        )

        # Exponential backoff on consecutive failures
        if state.consecutive_failures >= 5:
            logger.warning(
                "Scheduler: 5+ consecutive failures, increasing interval",
                old_interval=state.interval_seconds,
                new_interval=min(state.interval_seconds * 2, 3600),
            )


async def _scheduler_loop(state: SchedulerState) -> None:
    """Main scheduler loop — runs indefinitely."""
    logger.info(
        "Nowcast scheduler started",
        interval_s=state.interval_seconds,
        catchments=state.current_catchments,
    )

    state.is_running = True
    state.started_at = datetime.now(timezone.utc)

    # Initial run with small delay
    await asyncio.sleep(5)

    while state.is_running:
        if not state.paused:
            await _run_single_cycle(state)

        # Wait for next cycle (with backoff on failures)
        wait_time = state.interval_seconds
        if state.consecutive_failures >= 5:
            wait_time = min(state.interval_seconds * 2, 3600)  # max 1 hour

        try:
            await asyncio.sleep(wait_time)
        except asyncio.CancelledError:
            logger.info("Scheduler loop cancelled")
            break

    state.is_running = False
    logger.info("Nowcast scheduler stopped")


async def start_scheduler(
    interval_seconds: int = 900,
    catchments: Optional[list[str]] = None,
    grid_size: int = 60,
    duration_hours: float = 3.0,
) -> SchedulerState:
    """Start the automated nowcast scheduler.

    Args:
        interval_seconds: Interval between nowcast cycles (default 900 = 15 min)
        catchments: List of catchments to nowcast (default: hindmata_dadar)
        grid_size: Grid resolution dimension
        duration_hours: Simulation duration per cycle
    """
    global _scheduler_task, _scheduler_state

    if _scheduler_state.is_running:
        logger.info("Scheduler already running")
        return _scheduler_state

    _scheduler_state = SchedulerState(
        interval_seconds=interval_seconds,
        current_catchments=catchments or ["hindmata_dadar"],
        grid_size=grid_size,
        duration_hours=duration_hours,
    )

    _scheduler_task = asyncio.create_task(_scheduler_loop(_scheduler_state))
    return _scheduler_state


async def stop_scheduler() -> SchedulerState:
    """Stop the automated nowcast scheduler."""
    global _scheduler_task, _scheduler_state

    _scheduler_state.is_running = False

    if _scheduler_task is not None:
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
        _scheduler_task = None

    logger.info("Scheduler stopped", total_runs=_scheduler_state.total_runs)
    return _scheduler_state


async def pause_scheduler() -> SchedulerState:
    """Pause the scheduler without stopping it."""
    _scheduler_state.paused = True
    logger.info("Scheduler paused")
    return _scheduler_state


async def resume_scheduler() -> SchedulerState:
    """Resume a paused scheduler."""
    _scheduler_state.paused = False
    logger.info("Scheduler resumed")
    return _scheduler_state
