"""Synthetic rainfall provider — design storms for testing and scenario analysis.

Provides deterministic rainfall patterns for:
1. Unit testing (reproducible inputs)
2. Scenario analysis (what-if studies)
3. Model calibration (known forcing)

Design storm types:
- Uniform: constant rate over duration
- Triangular: linearly increasing then decreasing
- SCS Type II: USDA SCS 24-hour distribution
- Chicago: Chicago storm method (alternating block)
- Historical template: replay a recorded event pattern
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

import numpy as np

from packages.contracts.provenance import DataQuality, DataSource
from packages.contracts.rainfall import RainfallObservation, RainfallSpatialType
from services.rainfall.base import RainfallProvider


class StormType(str, Enum):
    UNIFORM = "uniform"
    TRIANGULAR = "triangular"
    SCS_TYPE_II = "scs_type_ii"
    PULSE = "pulse"


class SyntheticProvider(RainfallProvider):
    """Synthetic rainfall generator for testing and scenarios."""

    def __init__(
        self,
        storm_type: StormType = StormType.UNIFORM,
        total_depth_mm: float = 100.0,
        duration_hours: float = 6.0,
        peak_intensity_mmh: Optional[float] = None,
        time_step_minutes: int = 15,
    ):
        self.storm_type = storm_type
        self.total_depth_mm = total_depth_mm
        self.duration_hours = duration_hours
        self.peak_intensity_mmh = peak_intensity_mmh
        self.time_step_minutes = time_step_minutes

    @property
    def provider_name(self) -> str:
        return f"Synthetic ({self.storm_type.value})"

    def _generate_hyetograph(self) -> list[float]:
        """Generate rainfall intensity time series (mm/h) for the design storm."""
        n_steps = int(self.duration_hours * 60 / self.time_step_minutes)
        dt_h = self.time_step_minutes / 60.0

        if self.storm_type == StormType.UNIFORM:
            rate = self.total_depth_mm / self.duration_hours
            return [rate] * n_steps

        elif self.storm_type == StormType.TRIANGULAR:
            # Peak at center, linearly increasing then decreasing
            peak = 2 * self.total_depth_mm / self.duration_hours
            if self.peak_intensity_mmh:
                peak = self.peak_intensity_mmh
            half = n_steps // 2
            rising = np.linspace(0, peak, half + 1)[1:]
            falling = np.linspace(peak, 0, n_steps - half + 1)[:-1]
            rates = list(rising) + list(falling)
            # Normalize to total depth
            actual_depth = sum(rates) * dt_h
            if actual_depth > 0:
                factor = self.total_depth_mm / actual_depth
                rates = [r * factor for r in rates]
            return rates[:n_steps]

        elif self.storm_type == StormType.PULSE:
            # Short intense burst in the middle
            rates = [0.0] * n_steps
            mid = n_steps // 2
            burst_steps = max(1, n_steps // 6)
            burst_rate = self.total_depth_mm / (burst_steps * dt_h)
            for i in range(mid - burst_steps // 2, mid + burst_steps // 2 + 1):
                if 0 <= i < n_steps:
                    rates[i] = burst_rate
            return rates

        elif self.storm_type == StormType.SCS_TYPE_II:
            # Simplified SCS Type II 24-hour distribution
            # Peak at ~12 hours (50% of duration)
            t_frac = np.linspace(0, 1, n_steps + 1)
            # SCS Type II cumulative approximation
            cumulative = np.where(
                t_frac <= 0.5,
                0.5 * (t_frac / 0.5) ** 3.5,
                1.0 - 0.5 * ((1.0 - t_frac) / 0.5) ** 3.5,
            )
            incremental = np.diff(cumulative) * self.total_depth_mm
            rates = (incremental / dt_h).tolist()
            return rates

        return [0.0] * n_steps

    async def fetch_current(
        self,
        latitude: float,
        longitude: float,
    ) -> list[RainfallObservation]:
        """Return synthetic current observation."""
        rates = self._generate_hyetograph()
        # Return the first step as "current"
        rate = rates[0] if rates else 0.0
        return [
            RainfallObservation(
                source=DataSource.SYNTHETIC,
                observed_at=datetime.now(timezone.utc),
                rate_mmh=rate,
                spatial_type=RainfallSpatialType.POINT,
                latitude=latitude,
                longitude=longitude,
                quality=DataQuality.ESTIMATED,
            )
        ]

    async def fetch_historical(
        self,
        latitude: float,
        longitude: float,
        start_date: datetime,
        end_date: datetime,
    ) -> list[RainfallObservation]:
        """Generate full synthetic storm as historical data."""
        rates = self._generate_hyetograph()
        dt = timedelta(minutes=self.time_step_minutes)

        observations = []
        current_time = start_date
        for rate in rates:
            observations.append(
                RainfallObservation(
                    source=DataSource.SYNTHETIC,
                    observed_at=current_time,
                    rate_mmh=rate,
                    spatial_type=RainfallSpatialType.POINT,
                    latitude=latitude,
                    longitude=longitude,
                    quality=DataQuality.ESTIMATED,
                )
            )
            current_time += dt

        return observations
