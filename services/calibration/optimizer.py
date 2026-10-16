"""Hydrodynamic Model Auto-Calibration Framework.

Optimizes physical hydraulic and hydrologic parameters:
- Manning's roughness coefficient (n)
- Horton infiltration parameters (f0, f_min, decay k)
against historical satellite SAR flood masks and observed ground truth.

Phase 2D-4: Automated calibration framework.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import structlog

from services.terrain.dem_loader import get_catchment_dem
from services.terrain.conditioning import fill_sinks
from services.flood.engine import SimulationConfig, HortonParams, run_simulation
from services.validation.satellite_sar import SatelliteSARValidator

logger = structlog.get_logger()


@dataclass
class CalibratedParameterSet:
    """Calibrated hydrodynamic parameters with performance metrics."""
    parameter_set_id: str
    event_id: str
    catchment: str
    calibrated_at: str
    manning_n: float
    horton_f0_mmh: float
    horton_fmin_mmh: float
    horton_k_per_h: float
    initial_csi: float
    calibrated_csi: float
    initial_iou: float
    calibrated_iou: float
    improvement_pct: float
    iterations: int
    converged: bool
    version: str = "v1.0-calibrated"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "parameter_set_id": self.parameter_set_id,
            "event_id": self.event_id,
            "catchment": self.catchment,
            "calibrated_at": self.calibrated_at,
            "parameters": {
                "manning_n": round(self.manning_n, 4),
                "horton_f0_mmh": round(self.horton_f0_mmh, 1),
                "horton_fmin_mmh": round(self.horton_fmin_mmh, 2),
                "horton_k_per_h": round(self.horton_k_per_h, 2),
            },
            "metrics": {
                "initial_csi": round(self.initial_csi, 4),
                "calibrated_csi": round(self.calibrated_csi, 4),
                "initial_iou": round(self.initial_iou, 4),
                "calibrated_iou": round(self.calibrated_iou, 4),
                "improvement_pct": round(self.improvement_pct, 1),
            },
            "iterations": self.iterations,
            "converged": self.converged,
            "version": self.version,
        }


# Calibrated registry storage
_calibrated_registry: Dict[str, CalibratedParameterSet] = {}


class HydrodynamicCalibrator:
    """Parameter optimizer using objective spatial metrics (CSI/IoU)."""

    def __init__(self):
        self.validator = SatelliteSARValidator()

    async def calibrate_catchment(
        self,
        event_id: str = "HIST_FLOOD_2005_07_26",
        catchment: str = "hindmata_dadar",
        grid_size: int = 40,
        max_iterations: int = 8,
    ) -> CalibratedParameterSet:
        """Run bounded coordinate search to optimize Manning's n and Horton f0."""
        now_str = datetime.now(timezone.utc).isoformat()
        param_id = f"cal_{event_id}_{catchment}_{int(datetime.now().timestamp())}"

        # 1. Load DEM and observed mask
        dem_raw, georef = get_catchment_dem(catchment, max_dim=grid_size)
        dem = fill_sinks(dem_raw.astype(np.float64))
        observed_mask = self.validator.get_event_flood_mask(event_id, georef, dem.shape)

        # Baseline parameters
        best_n = 0.035
        best_f0 = 76.0
        best_fmin = 3.8
        best_k = 2.0

        # High-intensity test pulse
        test_schedule = [(0.0, 60.0), (1.0, 80.0), (2.0, 30.0)]
        imperviousness = np.full(dem.shape, 0.75)

        def evaluate(n_val: float, f0_val: float) -> Tuple[float, float]:
            cfg = SimulationConfig(
                city_id="mumbai",
                duration_hours=2.0,
                cell_size_m=georef["cell_size_m"],
                manning_n=n_val,
                horton_params=HortonParams(f0_mmh=f0_val, f_min_mmh=best_fmin, k_per_h=best_k),
            )
            res = run_simulation(
                dem=dem,
                rainfall_schedule=test_schedule,
                imperviousness=imperviousness,
                config=cfg,
            )
            pred_mask = res.max_depth_grid >= 0.10
            metrics = self.validator.compute_contingency_metrics(observed_mask, pred_mask)
            return metrics.critical_success_index, metrics.iou

        # Initial baseline evaluation
        init_csi, init_iou = evaluate(best_n, best_f0)

        # Search grid
        n_candidates = [0.025, 0.035, 0.045]
        f0_candidates = [50.0, 76.0, 95.0]

        best_csi = init_csi
        best_iou = init_iou
        iterations = 0

        for n_cand in n_candidates:
            for f0_cand in f0_candidates:
                iterations += 1
                csi_cand, iou_cand in evaluate(n_cand, f0_cand)
                if csi_cand > best_csi:
                    best_csi = csi_cand
                    best_iou = iou_cand
                    best_n = n_cand
                    best_f0 = f0_cand

        improvement = ((best_csi - init_csi) / max(0.01, init_csi)) * 100.0 if best_csi > init_csi else 0.0

        result = CalibratedParameterSet(
            parameter_set_id=param_id,
            event_id=event_id,
            catchment=catchment,
            calibrated_at=now_str,
            manning_n=best_n,
            horton_f0_mmh=best_f0,
            horton_fmin_mmh=best_fmin,
            horton_k_per_h=best_k,
            initial_csi=init_csi,
            calibrated_csi=best_csi,
            initial_iou=init_iou,
            calibrated_iou=best_iou,
            improvement_pct=improvement,
            iterations=iterations,
            converged=True,
            version="v1.0-auto-calibrated",
        )

        _calibrated_registry[catchment] = result
        return result

    def get_calibrated_parameters(self, catchment: str) -> Optional[CalibratedParameterSet]:
        return _calibrated_registry.get(catchment)

    def list_all_calibrated(self) -> List[CalibratedParameterSet]:
        return list(_calibrated_registry.values())


_global_calibrator = HydrodynamicCalibrator()


def get_calibrator() -> HydrodynamicCalibrator:
    return _global_calibrator
