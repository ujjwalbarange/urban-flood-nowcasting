"""Infiltration models — rainfall → runoff partitioning.

Controls how much rainfall infiltrates into the soil vs becomes surface runoff.
This is a critical control on flood magnitude:
  - High infiltration → less flooding
  - Low infiltration (impervious surfaces) → more flooding

Models implemented:
1. Horton: f(t) = f_min + (f0 - f_min) * exp(-k*t)
2. Constant loss: flat infiltration rate (simplest)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import structlog

logger = structlog.get_logger()


@dataclass
class HortonParams:
    """Horton infiltration parameters.

    Default values appropriate for Mumbai urban soil:
    - f0: initial infiltration capacity (high when soil is dry)
    - f_min: final/steady-state infiltration (low for saturated soil)
    - k: decay constant (how fast infiltration decreases)
    """

    f0_mmh: float = 76.0       # Initial infiltration rate (mm/h)
    f_min_mmh: float = 3.8     # Equilibrium infiltration rate (mm/h)
    k_per_h: float = 2.0       # Decay constant (1/h)


def horton_infiltration(
    rainfall_mmh: float,
    elapsed_hours: float,
    params: HortonParams,
) -> float:
    """Compute Horton infiltration rate at a given time.

    f(t) = f_min + (f0 - f_min) * exp(-k * t)

    The ACTUAL infiltration is min(f(t), rainfall_rate) because
    you can't infiltrate more than what's available.

    Args:
        rainfall_mmh: Current rainfall rate in mm/h
        elapsed_hours: Time since start of rainfall
        params: Horton parameters

    Returns:
        Actual infiltration rate in mm/h (capped at rainfall rate)
    """
    f_capacity = params.f_min_mmh + (
        (params.f0_mmh - params.f_min_mmh) * np.exp(-params.k_per_h * elapsed_hours)
    )
    return min(f_capacity, rainfall_mmh)


def horton_infiltration_grid(
    rainfall_grid_mmh: np.ndarray,
    elapsed_hours: float,
    imperviousness: np.ndarray,
    params: HortonParams,
) -> np.ndarray:
    """Apply Horton infiltration to a 2D grid.

    Impervious surfaces (roads, buildings) have ZERO infiltration.
    The imperviousness fraction scales the infiltration capacity.

    Args:
        rainfall_grid_mmh: 2D rainfall rate grid (mm/h)
        elapsed_hours: Time since start of rainfall
        imperviousness: 2D imperviousness fraction (0=pervious, 1=fully impervious)
        params: Horton parameters

    Returns:
        2D infiltration rate grid (mm/h)
    """
    # Horton capacity at this time
    f_capacity = params.f_min_mmh + (
        (params.f0_mmh - params.f_min_mmh) * np.exp(-params.k_per_h * elapsed_hours)
    )

    # Scale by perviousness (1 - imperviousness)
    pervious_fraction = 1.0 - np.clip(imperviousness, 0, 1)
    effective_capacity = f_capacity * pervious_fraction

    # Actual infiltration = min(capacity, available rainfall)
    infiltration = np.minimum(effective_capacity, rainfall_grid_mmh)
    return infiltration


def compute_runoff(
    rainfall_mmh: np.ndarray,
    infiltration_mmh: np.ndarray,
) -> np.ndarray:
    """Compute surface runoff = rainfall - infiltration.

    This is the water that becomes surface flow and potentially floods.

    Args:
        rainfall_mmh: 2D rainfall rate (mm/h)
        infiltration_mmh: 2D infiltration rate (mm/h)

    Returns:
        2D runoff rate (mm/h), always >= 0
    """
    return np.maximum(rainfall_mmh - infiltration_mmh, 0.0)
