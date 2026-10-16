"""Stage 6: Tide and Coastal Boundary Integration Service.

Integrates observed tide data from public.tide_observations (Apollo Bunder station,
Mumbai Port Trust / Survey of India) into the 2D diffusive wave hydrodynamic solver.

Datum Conversion:
- Apollo Bunder records are measured relative to Chart Datum (CD).
- Mumbai Mean Sea Level (MSL) is 2.51 m above Chart Datum (Survey of India / MbPT benchmark).
- The Copernicus GLO-30 DEM vertical datum is EGM96 (equivalent to MSL, 0.0 m MSL).
- Conversion formula:
    Z_MSL (m) = Z_CD (m) - 2.51 m

Scenarios Supported:
1. rainfall_only          — No tide effect (free ocean boundary outflow, Z_tide = -2.0 m MSL)
2. tide_only              — Zero rainfall; flow driven purely by tidal inundation
3. rainfall_normal_tide   — Rainfall + normal neap high tide (3.50 m CD -> 0.99 m MSL)
4. rainfall_high_tide     — Rainfall + spring high tide (4.45 m CD -> 1.94 m MSL)
5. rainfall_extreme_tide  — Rainfall + extreme astronomical / storm surge tide (5.00 m CD -> 2.49 m MSL)

Physical Mechanics:
- When sea water surface elevation (WSE_sea) > WSE_land, the water surface slope is adverse,
  causing tidal locking (zero drainage outflow) and inland seawater intrusion for cells below tide level.
- When WSE_land > WSE_sea, gravity drainage proceeds toward the sea boundary.
"""

from __future__ import annotations

import os
import ssl
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import asyncpg
import numpy as np
import structlog

logger = structlog.get_logger()

# Mumbai Tidal Benchmarks (Apollo Bunder / Survey of India)
MUMBAI_DATUM_OFFSET_M = 2.51     # MSL is +2.51 m above Chart Datum (CD)
MUMBAI_MHWS_M_CD = 4.45          # Mean High Water Spring (m CD) -> +1.94 m MSL
MUMBAI_MHWN_M_CD = 3.48          # Mean High Water Neap (m CD)   -> +0.97 m MSL
MUMBAI_EXTREME_M_CD = 5.00       # Extreme / Storm Surge (m CD)  -> +2.49 m MSL
MUMBAI_MLWS_M_CD = 0.76          # Mean Low Water Spring (m CD)  -> -1.75 m MSL
MUMBAI_TIDAL_PERIOD_HOURS = 12.42  # Principal lunar semidiurnal M2 tidal period


class TideScenario(str, Enum):
    """Allowed tidal forcing scenarios."""
    RAINFALL_ONLY = "rainfall_only"
    TIDE_ONLY = "tide_only"
    RAINFALL_NORMAL_TIDE = "rainfall_normal_tide"
    RAINFALL_HIGH_TIDE = "rainfall_high_tide"
    RAINFALL_EXTREME_TIDE = "rainfall_extreme_tide"
    OBSERVED_TIDE = "observed_tide"


@dataclass
class TideBoundarySchedule:
    """Tide height schedule for the simulation domain."""
    scenario: TideScenario
    datum: str = "MSL"                          # Converted to DEM datum (MSL)
    peak_tide_m_cd: float = 0.0                 # Peak in Chart Datum (m)
    peak_tide_m_msl: float = 0.0                # Peak in DEM MSL (m)
    mean_tide_m_msl: float = 0.0                # Mean in DEM MSL (m)
    min_tide_m_msl: float = 0.0                 # Min in DEM MSL (m)
    schedule: List[Tuple[float, float]] = field(default_factory=list)  # [(t_hours, tide_m_msl), ...]
    provenance: str = ""
    quality_status: str = "observed"            # observed or assumed


class TideService:
    """Provides coastal tide schedules from PostGIS tide_observations and scenarios."""

    def __init__(self, db_url: Optional[str] = None):
        raw_url = db_url or os.environ.get("DATABASE_URL", "")
        self.clean_url = raw_url.replace("postgresql+asyncpg://", "postgresql://").split("?")[0]
        self.ssl_ctx = ssl.create_default_context()
        self.ssl_ctx.check_hostname = False
        self.ssl_ctx.verify_mode = ssl.CERT_NONE

    async def _get_conn(self) -> asyncpg.Connection:
        return await asyncpg.connect(self.clean_url, ssl=self.ssl_ctx)

    async def get_observed_records(
        self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Fetch historical records from public.tide_observations."""
        conn = await self._get_conn()
        try:
            if start_time and end_time:
                rows = await conn.fetch("""
                    SELECT timestamp, tide_height_m, datum, station_name, data_source
                    FROM public.tide_observations
                    WHERE timestamp >= $1 AND timestamp <= $2
                    ORDER BY timestamp ASC;
                """, start_time, end_time)
            else:
                rows = await conn.fetch("""
                    SELECT timestamp, tide_height_m, datum, station_name, data_source
                    FROM public.tide_observations
                    ORDER BY timestamp ASC;
                """)
            return [dict(r) for r in rows]
        finally:
            await conn.close()

    async def build_tide_schedule(
        self,
        scenario: TideScenario | str,
        duration_hours: float,
        start_time: Optional[datetime] = None,
    ) -> TideBoundarySchedule:
        """Construct a continuous tide boundary schedule for simulation duration."""
        if isinstance(scenario, str):
            try:
                scenario = TideScenario(scenario)
            except ValueError:
                scenario = TideScenario.RAINFALL_HIGH_TIDE

        # Scenario 1: Rainfall Only (free outflow, tide below land drain)
        if scenario == TideScenario.RAINFALL_ONLY:
            return TideBoundarySchedule(
                scenario=scenario,
                datum="MSL",
                peak_tide_m_cd=0.0,
                peak_tide_m_msl=-2.0,
                mean_tide_m_msl=-2.0,
                min_tide_m_msl=-2.0,
                schedule=[(0.0, -2.0), (duration_hours, -2.0)],
                provenance="Free ocean drainage boundary (no tidal obstruction)",
                quality_status="assumed_boundary_condition",
            )

        # Scenarios 2 - 5: Tide-driven scenarios
        # Determine peak and low tide levels based on scenario
        if scenario == TideScenario.RAINFALL_NORMAL_TIDE:
            peak_cd = MUMBAI_MHWN_M_CD
            low_cd = MUMBAI_MLWS_M_CD + 0.8
            desc = "Normal Neap Tide (MHWN 3.48m CD -> +0.97m MSL)"
            quality = "assumed_standard_neap_tide"

        elif scenario == TideScenario.RAINFALL_HIGH_TIDE:
            peak_cd = MUMBAI_MHWS_M_CD
            low_cd = MUMBAI_MLWS_M_CD
            desc = "Spring High Tide (MHWS 4.45m CD -> +1.94m MSL, calibrated from Apollo Bunder)"
            quality = "calibrated_from_apollo_bunder_tide_observations"

        elif scenario == TideScenario.RAINFALL_EXTREME_TIDE:
            peak_cd = MUMBAI_EXTREME_M_CD
            low_cd = MUMBAI_MLWS_M_CD
            desc = "Extreme Astronomical / Storm Surge Tide (5.00m CD -> +2.49m MSL)"
            quality = "assumed_extreme_surge_scenario"

        elif scenario == TideScenario.TIDE_ONLY:
            peak_cd = MUMBAI_MHWS_M_CD
            low_cd = MUMBAI_MLWS_M_CD
            desc = "Tide-Only Simulation (No Rainfall; Spring Tide 4.45m CD -> +1.94m MSL)"
            quality = "calibrated_from_apollo_bunder_tide_observations"

        else:  # OBSERVED_TIDE
            records = await self.get_observed_records(start_time, start_time + timedelta(hours=duration_hours) if start_time else None)
            if records and len(records) >= 3:
                schedule = []
                t0 = records[0]["timestamp"]
                for r in records:
                    t_hours = (r["timestamp"] - t0).total_seconds() / 3600.0
                    h_msl = r["tide_height_m"] - MUMBAI_DATUM_OFFSET_M
                    schedule.append((t_hours, h_msl))
                max_cd = max(r["tide_height_m"] for r in records)
                min_cd = min(r["tide_height_m"] for r in records)
                mean_cd = float(np.mean([r["tide_height_m"] for r in records]))
                return TideBoundarySchedule(
                    scenario=scenario,
                    datum="MSL",
                    peak_tide_m_cd=round(max_cd, 2),
                    peak_tide_m_msl=round(max_cd - MUMBAI_DATUM_OFFSET_M, 2),
                    mean_tide_m_msl=round(mean_cd - MUMBAI_DATUM_OFFSET_M, 2),
                    min_tide_m_msl=round(min_cd - MUMBAI_DATUM_OFFSET_M, 2),
                    schedule=schedule,
                    provenance="Apollo Bunder tide_observations table (Survey of India / MbPT)",
                    quality_status="observed",
                )
            else:
                # Fallback to High Tide harmonic
                peak_cd = MUMBAI_MHWS_M_CD
                low_cd = MUMBAI_MLWS_M_CD
                desc = "Observed records unavailable for requested window; using Apollo Bunder Spring Tide harmonic"
                quality = "assumed_harmonic_from_observed_tide"

        # Build semidiurnal harmonic schedule
        peak_msl = peak_cd - MUMBAI_DATUM_OFFSET_M
        low_msl = low_cd - MUMBAI_DATUM_OFFSET_M
        mean_msl = (peak_msl + low_msl) / 2.0
        amplitude = (peak_msl - low_msl) / 2.0

        # Discretize at 15-minute intervals (0.25 hr)
        n_pts = int(np.ceil(duration_hours / 0.25)) + 1
        schedule = []
        omega = 2.0 * np.pi / MUMBAI_TIDAL_PERIOD_HOURS

        for i in range(n_pts):
            t_h = i * 0.25
            if t_h > duration_hours:
                t_h = duration_hours
            # Peak tide occurs at ~t=3.0h (during initial monsoon surge)
            h_msl = mean_msl + amplitude * np.cos(omega * (t_h - 3.0))
            schedule.append((round(t_h, 3), round(float(h_msl), 4)))

        return TideBoundarySchedule(
            scenario=scenario,
            datum="MSL",
            peak_tide_m_cd=round(peak_cd, 2),
            peak_tide_m_msl=round(peak_msl, 2),
            mean_tide_m_msl=round(mean_msl, 2),
            min_tide_m_msl=round(low_msl, 2),
            schedule=schedule,
            provenance=f"Apollo Bunder benchmark model: {desc}",
            quality_status=quality,
        )


def identify_coastal_boundary_mask(
    dem: np.ndarray,
    georef: Dict[str, Any],
    max_coastal_elev_m: float = 3.0,
) -> np.ndarray:
    """Identify coastal/sea cells in DEM grid that interact with sea tides.

    In Mumbai:
    - West boundary faces the Arabian Sea.
    - South boundary faces South Mumbai harbor / Apollo Bunder.
    - Low-elevation cells near the boundary (DEM < max_coastal_elev_m) act as tidal receptors.

    Returns:
        Boolean 2D array: True where cells connect directly to the sea tide boundary.
    """
    rows, cols = dem.shape
    coastal_mask = np.zeros((rows, cols), dtype=bool)

    # Western boundary (Arabian Sea) - cols 0, 1
    coastal_mask[:, 0] = dem[:, 0] <= max_coastal_elev_m
    if cols > 1:
        coastal_mask[:, 1] = (dem[:, 1] <= max_coastal_elev_m) & coastal_mask[:, 0]

    # Southern boundary (Harbor/Bay) - rows -1, -2
    coastal_mask[-1, :] = coastal_mask[-1, :] | (dem[-1, :] <= max_coastal_elev_m)
    if rows > 1:
        coastal_mask[-2, :] = coastal_mask[-2, :] | ((dem[-2, :] <= max_coastal_elev_m) & coastal_mask[-1, :])

    return coastal_mask
