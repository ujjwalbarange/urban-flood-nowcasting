"""Evaluation and Validation Metrics for ML Flood Surrogate.

Computes quantitative metrics comparing ML predictions against physics ground truth:
- Flood extent metrics: IoU, CSI, POD (Recall), Precision, FAR
- Water depth metrics: MAE, RMSE, Peak Depth Error, Volume Conservation Ratio

Phase 2C-4: Evaluation and metrics suite.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import numpy as np
import torch


@dataclass
class SurrogateEvaluationMetrics:
    """Quantitative performance scorecard for surrogate model."""
    csi: float                   # Critical Success Index [0, 1]
    iou: float                   # Intersection over Union [0, 1]
    pod: float                   # Probability of Detection (Recall) [0, 1]
    precision: float             # Precision [0, 1]
    far: float                   # False Alarm Ratio [0, 1]
    mae_depth_m: float           # Mean Absolute Error (meters)
    rmse_depth_m: float          # Root Mean Squared Error (meters)
    peak_depth_error_m: float    # Peak depth deviation
    volume_ratio: float          # Predicted volume / Target volume
    sample_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "critical_success_index": round(self.csi, 4),
            "iou": round(self.iou, 4),
            "pod_recall": round(self.pod, 4),
            "precision": round(self.precision, 4),
            "false_alarm_ratio": round(self.far, 4),
            "mae_depth_m": round(self.mae_depth_m, 4),
            "rmse_depth_m": round(self.rmse_depth_m, 4),
            "peak_depth_error_m": round(self.peak_depth_error_m, 4),
            "volume_conservation_ratio": round(self.volume_ratio, 4),
            "evaluation_samples": self.sample_count,
            "rating": "EXCELLENT" if self.csi >= 0.70 else "ACCEPTABLE" if self.csi >= 0.50 else "NEEDS_TRAINING",
        }


def compute_surrogate_metrics(
    pred_depth: np.ndarray,      # (H, W) or (T, H, W)
    target_depth: np.ndarray,    # (H, W) or (T, H, W)
    flood_threshold_m: float = 0.05,
) -> SurrogateEvaluationMetrics:
    """Compute spatial and depth regression metrics."""
    # Flatten
    y_pred = np.asarray(pred_depth, dtype=np.float64).ravel()
    y_true = np.asarray(target_depth, dtype=np.float64).ravel()

    # Binary extent masks
    mask_pred = y_pred >= flood_threshold_m
    mask_true = y_true >= flood_threshold_m

    tp = int(np.sum(mask_pred & mask_true))
    fp = int(np.sum(mask_pred & (~mask_true)))
    fn = int(np.sum((~mask_pred) & mask_true))
    tn = int(np.sum((~mask_pred) & (~mask_true)))

    # Spatial contingency
    csi = tp / max(1, tp + fp + fn)
    iou = tp / max(1, tp + fp + fn)
    pod = tp / max(1, tp + fn)
    prec = tp / max(1, tp + fp)
    far = fp / max(1, tp + fp)

    # Depth errors (computed across all cells where either is flooded)
    wet_union = mask_pred | mask_true
    if np.any(wet_union):
        mae = float(np.mean(np.abs(y_pred[wet_union] - y_true[wet_union])))
        rmse = float(np.sqrt(np.mean((y_pred[wet_union] - y_true[wet_union]) ** 2)))
    else:
        mae = 0.0
        rmse = 0.0

    peak_err = float(np.abs(np.max(y_pred) - np.max(y_true))) if len(y_pred) > 0 else 0.0
    vol_pred = float(np.sum(y_pred))
    vol_true = float(np.sum(y_true))
    vol_ratio = vol_pred / max(1e-4, vol_true)

    return SurrogateEvaluationMetrics(
        csi=csi,
        iou=iou,
        pod=pod,
        precision=prec,
        far=far,
        mae_depth_m=mae,
        rmse_depth_m=rmse,
        peak_depth_error_m=peak_err,
        volume_ratio=vol_ratio,
        sample_count=len(y_pred),
    )
