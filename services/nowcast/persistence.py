"""Rainfall nowcasting engine — persistence, optical flow, NWP blending.

Provides short-term (0-6h) rainfall forecasts by:
1. Persistence: assume current rate continues
2. Lagrangian persistence: advect current field using motion vectors
3. NWP blending: blend persistence with NWP model output

For the initial version, we implement persistence + exponential decay.
Optical flow (pysteps) and NWP blending come in Phase 8+.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np
import structlog

from packages.contracts.rainfall import NowcastMethod, RainfallNowcast

logger = structlog.get_logger()


class PersistenceNowcaster:
    """Persistence-based rainfall nowcaster.

    Assumes current rainfall rate continues, with optional exponential decay.
    This is the simplest nowcaster but provides a useful baseline.

    Skill horizon: ~30 minutes (urban timescale).
    Beyond that, atmospheric dynamics dominate.
    """

    def __init__(
        self,
        decay_rate: float = 0.1,  # Exponential decay constant (1/h)
        time_step_minutes: int = 15,
    ):
        self.decay_rate = decay_rate
        self.time_step_minutes = time_step_minutes

    def nowcast(
        self,
        current_rate_mmh: float,
        hours_ahead: float = 3.0,
        latitude: float = 0.0,
        longitude: float = 0.0,
    ) -> list[RainfallNowcast]:
        """Generate persistence nowcast with exponential decay.

        Args:
            current_rate_mmh: Current observed rainfall rate (mm/h)
            hours_ahead: Forecast horizon in hours
            latitude, longitude: Location (for metadata)

        Returns:
            List of RainfallNowcast objects at each time step
        """
        n_steps = int(hours_ahead * 60 / self.time_step_minutes)
        dt = timedelta(minutes=self.time_step_minutes)
        now = datetime.now(timezone.utc)

        forecasts = []
        for i in range(n_steps):
            t_hours = (i + 1) * self.time_step_minutes / 60.0
            valid_time = now + dt * (i + 1)

            # Exponential decay of current rate
            predicted_rate = current_rate_mmh * np.exp(-self.decay_rate * t_hours)

            # Confidence decreases with lead time
            confidence = max(0.1, 1.0 - (t_hours / hours_ahead) * 0.8)

            forecasts.append(
                RainfallNowcast(
                    method=NowcastMethod.PERSISTENCE,
                    initialization_time=now,
                    valid_time=valid_time,
                    lead_minutes=int((i + 1) * self.time_step_minutes),
                    mean_rate_mmh=max(0.0, round(float(predicted_rate), 2)),
                    confidence=round(float(confidence), 3),
                    metadata={"latitude": latitude, "longitude": longitude},
                )
            )

        logger.info(
            "Persistence nowcast generated",
            current_rate=current_rate_mmh,
            steps=n_steps,
            hours_ahead=hours_ahead,
        )
        return forecasts


class GridNowcaster:
    """Grid-based rainfall nowcaster for 2D spatial fields.

    Takes a current rainfall grid and produces forecast grids at
    future time steps using persistence + decay.

    This is the version that feeds into the 2D surface flow model.
    """

    def __init__(
        self,
        decay_rate: float = 0.1,
        time_step_minutes: int = 15,
    ):
        self.decay_rate = decay_rate
        self.time_step_minutes = time_step_minutes

    def nowcast_grid(
        self,
        current_grid_mmh: np.ndarray,
        hours_ahead: float = 3.0,
    ) -> list[tuple[float, np.ndarray]]:
        """Generate nowcast grid sequence.

        Args:
            current_grid_mmh: 2D rainfall rate grid (mm/h)
            hours_ahead: Forecast horizon

        Returns:
            List of (lead_hours, rainfall_grid) tuples
        """
        n_steps = int(hours_ahead * 60 / self.time_step_minutes)
        forecasts = []

        for i in range(n_steps):
            t_hours = (i + 1) * self.time_step_minutes / 60.0
            decay_factor = np.exp(-self.decay_rate * t_hours)
            forecast_grid = current_grid_mmh * decay_factor
            forecasts.append((t_hours, forecast_grid.copy()))

        return forecasts
