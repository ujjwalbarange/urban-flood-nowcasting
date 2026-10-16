"""Training Data Generation for ML Flood Surrogate.

Executes parametrized 2D diffusive wave hydrodynamic simulations across diverse
rainfall intensities (10 - 180 mm/h), storm durations (1 - 4h), and catchments,
generating paired spatio-temporal datasets for training ConvGRU surrogates.

Phase 2C-1: Training data generation.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import structlog
import torch

from services.terrain.dem_loader import get_catchment_dem
from services.terrain.conditioning import fill_sinks
from services.flood.engine import SimulationConfig, HortonParams, run_simulation

logger = structlog.get_logger()


@dataclass
class SimulationSample:
    """A paired input-output sample for surrogate model training."""
    sample_id: str
    catchment: str
    rainfall_rate_mmh: float
    duration_hours: float
    # Tensors: (T, H, W) or (C, H, W)
    dem_tensor: torch.Tensor             # (1, H, W) normalized elevation
    rainfall_tensor: torch.Tensor        # (T_in, 1, H, W) spatio-temporal rainfall input
    target_depth_tensor: torch.Tensor    # (T_out, 1, H, W) water depth ground truth
    target_mask_tensor: torch.Tensor     # (T_out, 1, H, W) binary wet/dry mask
    max_depth_m: float
    flooded_area_km2: float


class FloodDataGenerator:
    """Generates synthetic physics-grounded simulation runs for ML training."""

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = Path(output_dir or "data/processed/ml_training")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_single_sample(
        self,
        catchment: str = "hindmata_dadar",
        rainfall_intensity_mmh: float = 50.0,
        duration_hours: float = 2.0,
        grid_size: int = 32,
    ) -> SimulationSample:
        """Run a physics simulation and produce paired PyTorch tensors."""
        sample_id = f"sample_{catchment}_{int(rainfall_intensity_mmh)}mmh_{int(duration_hours)}h_{int(datetime.now().timestamp() * 1000) % 100000}"

        # 1. Load DEM
        dem_raw, georef = get_catchment_dem(catchment, max_dim=grid_size)
        dem = fill_sinks(dem_raw.astype(np.float64))
        H, W = dem.shape

        # 2. Build synthetic storm pulse (ramping up and down)
        t_steps = int(duration_hours * 4)  # 15-min intervals
        schedule = []
        for i in range(t_steps + 1):
            t_h = i * 0.25
            # Triangular/Gaussian storm hyetograph
            rate = float(rainfall_intensity_mmh * np.exp(-((t_h - duration_hours / 2.0) ** 2) / 0.8))
            schedule.append((t_h, max(2.0, rate)))

        # 3. Run physics simulation
        cfg = SimulationConfig(
            city_id="mumbai",
            duration_hours=duration_hours,
            cell_size_m=georef["cell_size_m"],
            manning_n=0.035,
            horton_params=HortonParams(f0_mmh=76.0, f_min_mmh=3.8, k_per_h=2.0),
        )
        imperviousness = np.full(dem.shape, 0.75)

        sim_result = run_simulation(
            dem=dem,
            rainfall_schedule=schedule,
            imperviousness=imperviousness,
            config=cfg,
        )

        # 4. Construct tensors
        # DEM normalized [0, 1]
        dem_norm = (dem - np.min(dem)) / max(1e-4, np.max(dem) - np.min(dem))
        dem_tensor = torch.tensor(dem_norm, dtype=torch.float32).unsqueeze(0)  # (1, H, W)

        # Rainfall sequence (T, 1, H, W)
        rain_vals = [s[1] for s in schedule]
        T = len(rain_vals)
        rainfall_seq = np.zeros((T, 1, H, W), dtype=np.float32)
        for t_idx, rate in enumerate(rain_vals):
            rainfall_seq[t_idx, 0, :, :] = rate / 100.0  # Normalized (100 mm/h = 1.0)
        rainfall_tensor = torch.tensor(rainfall_seq, dtype=torch.float32)

        # Target depth grids
        if sim_result.snapshots:
            depth_stack = np.array([snap.depth_grid for snap in sim_result.snapshots], dtype=np.float32)
        else:
            depth_stack = np.expand_dims(sim_result.max_depth_grid.astype(np.float32), axis=0)

        depth_tensor = torch.tensor(depth_stack, dtype=torch.float32).unsqueeze(1)  # (T_out, 1, H, W)
        mask_tensor = (depth_tensor >= 0.05).float()

        cell_area_km2 = (georef["cell_size_m"] ** 2) / 1e6
        flooded_cells = int(np.sum(sim_result.max_depth_grid >= 0.05))

        return SimulationSample(
            sample_id=sample_id,
            catchment=catchment,
            rainfall_rate_mmh=rainfall_intensity_mmh,
            duration_hours=duration_hours,
            dem_tensor=dem_tensor,
            rainfall_tensor=rainfall_tensor,
            target_depth_tensor=depth_tensor,
            target_mask_tensor=mask_tensor,
            max_depth_m=float(sim_result.max_depth_m),
            flooded_area_km2=flooded_cells * cell_area_km2,
        )

    def generate_dataset_batch(
        self,
        catchment: str = "hindmata_dadar",
        num_samples: int = 10,
        grid_size: int = 32,
    ) -> List[SimulationSample]:
        """Generate a diverse batch of samples across rainfall intensities."""
        samples = []
        intensities = np.linspace(15.0, 160.0, num_samples)

        for rate in intensities:
            sample = self.generate_single_sample(
                catchment=catchment,
                rainfall_intensity_mmh=float(rate),
                duration_hours=2.0,
                grid_size=grid_size,
            )
            samples.append(sample)

        logger.info(
            "Generated simulation dataset batch",
            catchment=catchment,
            samples=len(samples),
            min_rain=round(float(intensities[0]), 1),
            max_rain=round(float(intensities[-1]), 1),
        )
        return samples
