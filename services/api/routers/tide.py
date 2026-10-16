"""Tide and Coastal Hydrodynamics API Router.

Exposes endpoints for Mumbai coastal tide schedules, current tidal status,
astronomical scenarios, and tidal locking risks for drainage outfalls.
Backed by TideService and Apollo Bunder (Survey of India / MbPT) observations.

Phase 2E-1: Coastal coupling API.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.coastal.tide_service import (
    TideService,
    TideScenario,
    TideBoundarySchedule,
    MUMBAI_DATUM_OFFSET_M,
    MUMBAI_MHWS_M_CD,
    MUMBAI_MHWN_M_CD,
    MUMBAI_EXTREME_M_CD,
    MUMBAI_MLWS_M_CD,
    MUMBAI_TIDAL_PERIOD_HOURS,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/tide", tags=["Tide & Coastal"])

# Singleton service instance
_tide_service = TideService()


class CurrentTideResponse(BaseModel):
    timestamp: str
    datum_offset_m: float = MUMBAI_DATUM_OFFSET_M
    tide_height_m_cd: float
    tide_height_m_msl: float
    tidal_phase: str  # FLOOD (RISING), EBB (FALLING), HIGH_SLACK, LOW_SLACK
    tidal_locking_risk: str  # NONE, LOW, MODERATE, HIGH, CRITICAL
    next_high_tide: Optional[Dict[str, Any]] = None
    next_low_tide: Optional[Dict[str, Any]] = None
    station: str = "Apollo Bunder (Survey of India / MbPT)"
    provenance: str


class TideScenarioInfo(BaseModel):
    id: str
    name: str
    description: str
    peak_tide_m_cd: float
    peak_tide_m_msl: float
    datum: str = "MSL"
    tidal_locking_hazard: str


class TideForecastResponse(BaseModel):
    scenario: str
    duration_hours: float
    datum: str
    peak_tide_m_cd: float
    peak_tide_m_msl: float
    mean_tide_m_msl: float
    min_tide_m_msl: float
    quality_status: str
    provenance: str
    schedule: List[List[float]]  # [[t_hours, height_m_msl], ...]


@router.get("/current", response_model=CurrentTideResponse)
async def get_current_tide():
    """Get the current estimated or observed tide level at Mumbai (Apollo Bunder)."""
    now = datetime.now(timezone.utc)
    
    # Try getting real observed records for today first
    records = []
    try:
        records = await _tide_service.get_observed_records()
    except Exception as e:
        logger.warning("Could not query DB tide_observations", error=str(e))

    if records:
        latest = records[-1]
        tide_cd = latest["tide_height_m"]
        provenance = f"Live PostGIS tide_observations (Station: {latest.get('station_name', 'Apollo Bunder')})"
    else:
        # Calculate current height using Apollo Bunder semidiurnal harmonic model
        # M2 tidal cycle: period 12.42h, MHWS amplitude
        hour_of_day = now.hour + now.minute / 60.0 + now.second / 3600.0
        omega = 2.0 * 3.14159265 / MUMBAI_TIDAL_PERIOD_HOURS
        mean_cd = (MUMBAI_MHWS_M_CD + MUMBAI_MLWS_M_CD) / 2.0  # 2.605m CD
        amp_cd = (MUMBAI_MHWS_M_CD - MUMBAI_MLWS_M_CD) / 2.0   # 1.845m
        # Peak at ~12:00 and ~00:25 IST
        tide_cd = round(mean_cd + amp_cd * float(np_cos_approx(omega * hour_of_day)), 2)
        provenance = "Apollo Bunder M2 Harmonic Tidal Benchmark (Survey of India datum)"

    tide_msl = round(tide_cd - MUMBAI_DATUM_OFFSET_M, 2)

    # Locking risk assessment based on BMC BRIMSTOWAD benchmarks
    if tide_cd >= MUMBAI_EXTREME_M_CD:
        locking = "CRITICAL"
    elif tide_cd >= MUMBAI_MHWS_M_CD:
        locking = "HIGH"
    elif tide_cd >= MUMBAI_MHWN_M_CD:
        locking = "MODERATE"
    elif tide_cd >= 3.0:
        locking = "LOW"
    else:
        locking = "NONE"

    # Phase calculation
    # Derivative sign approx
    hour_val = now.hour + now.minute / 60.0
    phase_val = (hour_val % MUMBAI_TIDAL_PERIOD_HOURS) / MUMBAI_TIDAL_PERIOD_HOURS
    if 0.2 <= phase_val <= 0.3:
        phase = "HIGH_SLACK"
    elif 0.7 <= phase_val <= 0.8:
        phase = "LOW_SLACK"
    elif phase_val < 0.25 or phase_val > 0.75:
        phase = "FLOOD (RISING)"
    else:
        phase = "EBB (FALLING)"

    return CurrentTideResponse(
        timestamp=now.isoformat(),
        tide_height_m_cd=tide_cd,
        tide_height_m_msl=tide_msl,
        tidal_phase=phase,
        tidal_locking_risk=locking,
        next_high_tide={"height_m_cd": MUMBAI_MHWS_M_CD, "height_m_msl": round(MUMBAI_MHWS_M_CD - MUMBAI_DATUM_OFFSET_M, 2)},
        next_low_tide={"height_m_cd": MUMBAI_MLWS_M_CD, "height_m_msl": round(MUMBAI_MLWS_M_CD - MUMBAI_DATUM_OFFSET_M, 2)},
        provenance=provenance,
    )


@router.get("/scenarios", response_model=List[TideScenarioInfo])
async def list_tide_scenarios():
    """List all available tidal forcing scenarios for hydrodynamic simulation."""
    return [
        TideScenarioInfo(
            id=TideScenario.RAINFALL_ONLY.value,
            name="Rainfall Only (Free Outflow)",
            description="Ocean boundary operates with unhindered gravity discharge (Z_tide = -2.0m MSL).",
            peak_tide_m_cd=0.0,
            peak_tide_m_msl=-2.0,
            tidal_locking_hazard="NONE",
        ),
        TideScenarioInfo(
            id=TideScenario.TIDE_ONLY.value,
            name="Tide Inundation Only",
            description="Pure tidal flooding with zero precipitation; drives seawater intrusion into low-lying creeks.",
            peak_tide_m_cd=MUMBAI_MHWS_M_CD,
            peak_tide_m_msl=round(MUMBAI_MHWS_M_CD - MUMBAI_DATUM_OFFSET_M, 2),
            tidal_locking_hazard="HIGH",
        ),
        TideScenarioInfo(
            id=TideScenario.RAINFALL_NORMAL_TIDE.value,
            name="Rainfall + Normal Neap Tide",
            description="Coupled precipitation with standard neap high tide (MHWN = 3.48m CD -> +0.97m MSL).",
            peak_tide_m_cd=MUMBAI_MHWN_M_CD,
            peak_tide_m_msl=round(MUMBAI_MHWN_M_CD - MUMBAI_DATUM_OFFSET_M, 2),
            tidal_locking_hazard="MODERATE",
        ),
        TideScenarioInfo(
            id=TideScenario.RAINFALL_HIGH_TIDE.value,
            name="Rainfall + Spring High Tide",
            description="Monsoon rainfall coupled with astronomical spring high tide (MHWS = 4.45m CD -> +1.94m MSL). Outfalls locked.",
            peak_tide_m_cd=MUMBAI_MHWS_M_CD,
            peak_tide_m_msl=round(MUMBAI_MHWS_M_CD - MUMBAI_DATUM_OFFSET_M, 2),
            tidal_locking_hazard="HIGH",
        ),
        TideScenarioInfo(
            id=TideScenario.RAINFALL_EXTREME_TIDE.value,
            name="Rainfall + Storm Surge / Extreme Tide",
            description="Extreme cyclonic or astronomical tide (5.00m CD -> +2.49m MSL) causing severe tidal backflow into storm drains.",
            peak_tide_m_cd=MUMBAI_EXTREME_M_CD,
            peak_tide_m_msl=round(MUMBAI_EXTREME_M_CD - MUMBAI_DATUM_OFFSET_M, 2),
            tidal_locking_hazard="CRITICAL",
        ),
        TideScenarioInfo(
            id=TideScenario.OBSERVED_TIDE.value,
            name="Observed Apollo Bunder Gauge",
            description="Real gauge records from Apollo Bunder tide_observations table with automatic harmonic fallback.",
            peak_tide_m_cd=MUMBAI_MHWS_M_CD,
            peak_tide_m_msl=round(MUMBAI_MHWS_M_CD - MUMBAI_DATUM_OFFSET_M, 2),
            tidal_locking_hazard="VARIABLE",
        ),
    ]


@router.get("/forecast", response_model=TideForecastResponse)
async def get_tide_forecast(
    scenario: str = Query(
        default=TideScenario.RAINFALL_HIGH_TIDE.value,
        description="Tidal scenario to compute boundary schedule for",
    ),
    duration_hours: float = Query(
        default=6.0,
        ge=1.0,
        le=72.0,
        description="Forecast schedule duration in hours",
    ),
):
    """Generate continuous boundary condition schedule for hydrodynamic flood models."""
    try:
        scen_enum = TideScenario(scenario)
    except ValueError:
        scen_enum = TideScenario.RAINFALL_HIGH_TIDE

    sched = await _tide_service.build_tide_schedule(scen_enum, duration_hours)

    return TideForecastResponse(
        scenario=sched.scenario.value,
        duration_hours=duration_hours,
        datum=sched.datum,
        peak_tide_m_cd=sched.peak_tide_m_cd,
        peak_tide_m_msl=sched.peak_tide_m_msl,
        mean_tide_m_msl=sched.mean_tide_m_msl,
        min_tide_m_msl=sched.min_tide_m_msl,
        quality_status=sched.quality_status,
        provenance=sched.provenance,
        schedule=[[t, h] for t, h in sched.schedule],
    )


def np_cos_approx(val: float) -> float:
    import math
    return math.cos(val)
