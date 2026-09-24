"""Satellite SAR & Observational Flood Extent Validation Engine.

Implements the satellite validation loop (Level 1 historical evidence):
1. Loads observed / Sentinel-1 SAR change-detection flood extent masks.
2. Rasterizes them onto the Copernicus DEM simulation mesh.
3. Compares the 2D diffusive wave predicted flood extent against the satellite mask.
4. Computes hydro-spatial validation metrics:
   - IoU (Intersection over Union / Jaccard Index)
   - CSI (Critical Success Index / Threat Score)
   - POD (Probability of Detection / Recall)
   - Precision (Positive Predictive Value)
   - FAR (False Alarm Ratio)
   - Bias Score
5. Emits georeferenced spatial confusion polygons (TP, FP, FN) for visualization on OpenStreetMap.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
import numpy as np
from shapely.geometry import Point, shape
import structlog

logger = structlog.get_logger()

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OBSERVED_POLYGONS_FILE = (
    _PROJECT_ROOT
    / "mumbai_flood_data_package"
    / "08_flood_observations"
    / "flood_polygons.geojson"
)


@dataclass
class ValidationMetrics:
    """Standard hydro-spatial validation metrics."""

    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    total_cells: int
    iou: float
    critical_success_index: float
    recall_pod: float
    precision: float
    false_alarm_ratio: float
    accuracy: float
    bias: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "true_negatives": self.true_negatives,
            "total_evaluated_cells": self.total_cells,
            "iou_jaccard": round(self.iou, 4),
            "critical_success_index_csi": round(self.critical_success_index, 4),
            "recall_pod": round(self.recall_pod, 4),
            "precision": round(self.precision, 4),
            "false_alarm_ratio_far": round(self.false_alarm_ratio, 4),
            "overall_accuracy": round(self.accuracy, 4),
            "bias_score": round(self.bias, 4),
        }


class SatelliteSARValidator:
    """Validates 2D hydraulic flood models against satellite SAR change masks."""

    def __init__(self, polygons_file: Optional[Path] = None):
        self._polygons_file = polygons_file or OBSERVED_POLYGONS_FILE
        self._observed_features: list[dict] = []
        self._load_features()

    def _load_features(self) -> None:
        if not self._polygons_file.exists():
            logger.warning("Observed flood polygons file not found", path=str(self._polygons_file))
            return
        try:
            with open(self._polygons_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._observed_features = data.get("features", [])
            logger.info("Loaded observed flood features", count=len(self._observed_features))
        except Exception as e:
            logger.error("Failed to load observed flood polygons", error=str(e))

    def get_available_events(self) -> list[dict[str, Any]]:
        """List historical events with satellite or documented validation extents."""
        events = []
        for f in self._observed_features:
            p = f.get("properties", {})
            events.append({
                "event_id": p.get("event_id"),
                "event_name": p.get("event_name"),
                "area_name": p.get("inundation_area_name"),
                "date": p.get("date"),
                "peak_depth_range": p.get("peak_depth_range_m"),
                "source": p.get("source"),
            })
        return events

    def rasterize_observed_extent(
        self,
        event_id: str,
        georef: dict,
    ) -> np.ndarray:
        """Rasterize observed/satellite flood polygons onto the simulation grid.

        Returns:
            binary 2D boolean array (True = flooded according to satellite/observation)
        """
        rows = georef["rows"]
        cols = georef["cols"]
        mask = np.zeros((rows, cols), dtype=bool)

        d_lon = (georef["max_lon"] - georef["min_lon"]) / cols
        d_lat = (georef["max_lat"] - georef["min_lat"]) / rows

        # Find matching feature(s)
        matching_geoms = []
        for f in self._observed_features:
            props = f.get("properties", {})
            if event_id.lower() in props.get("event_id", "").lower() or event_id.lower() in props.get("event_name", "").lower():
                try:
                    geom = shape(f["geometry"])
                    matching_geoms.append(geom)
                except Exception:
                    continue

        if not matching_geoms:
            # Fallback: check all features that intersect georef bounding box
            from shapely.geometry import box
            bbox_poly = box(georef["min_lon"], georef["min_lat"], georef["max_lon"], georef["max_lat"])
            for f in self._observed_features:
                try:
                    geom = shape(f["geometry"])
                    if geom.intersects(bbox_poly):
                        matching_geoms.append(geom)
                except Exception:
                    continue

        if not matching_geoms:
            logger.warning("No matching observed flood geometry for event", event_id=event_id)
            return mask

        # Rasterize cell centers
        for r in range(rows):
            cell_lat = georef["max_lat"] - (r + 0.5) * d_lat
            for c in range(cols):
                cell_lon = georef["min_lon"] + (c + 0.5) * d_lon
                pt = Point(cell_lon, cell_lat)
                for geom in matching_geoms:
                    if geom.contains(pt) or geom.distance(pt) < (d_lon * 0.5):
                        mask[r, c] = True
                        break

        logger.info(
            "Rasterized observed flood extent",
            event_id=event_id,
            flooded_cells=int(np.sum(mask)),
            total_cells=mask.size,
        )
        return mask

    def evaluate_model_extent(
        self,
        simulated_depth_grid: np.ndarray,
        observed_mask: np.ndarray,
        min_depth_threshold_m: float = 0.08,
    ) -> ValidationMetrics:
        """Compute spatial validation metrics between simulated depth and observed mask."""
        sim_mask = (simulated_depth_grid >= min_depth_threshold_m)

        tp = int(np.sum(sim_mask & observed_mask))
        fp = int(np.sum(sim_mask & ~observed_mask))
        fn = int(np.sum(~sim_mask & observed_mask))
        tn = int(np.sum(~sim_mask & ~observed_mask))
        total = int(sim_mask.size)

        denom_union = tp + fp + fn
        iou = tp / denom_union if denom_union > 0 else 0.0
        csi = iou

        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        far = fp / (tp + fp) if (tp + fp) > 0 else 0.0
        accuracy = (tp + tn) / total if total > 0 else 0.0
        bias = (tp + fp) / (tp + fn) if (tp + fn) > 0 else 1.0

        return ValidationMetrics(
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
            true_negatives=tn,
            total_cells=total,
            iou=iou,
            critical_success_index=csi,
            recall_pod=recall,
            precision=precision,
            false_alarm_ratio=far,
            accuracy=accuracy,
            bias=bias,
        )

    def generate_spatial_confusion_geojson(
        self,
        simulated_depth_grid: np.ndarray,
        observed_mask: np.ndarray,
        georef: dict,
        min_depth_threshold_m: float = 0.08,
        max_features: int = 1500,
    ) -> dict[str, Any]:
        """Generate GeoJSON with classified cells: True Positive, False Positive, False Negative."""
        sim_mask = (simulated_depth_grid >= min_depth_threshold_m)
        rows, cols = simulated_depth_grid.shape

        d_lon = (georef["max_lon"] - georef["min_lon"]) / cols
        d_lat = (georef["max_lat"] - georef["min_lat"]) / rows

        features = []

        # Find cells of interest (TP, FP, FN)
        eval_cells = np.argwhere(sim_mask | observed_mask)
        if len(eval_cells) > max_features:
            step = int(np.ceil(len(eval_cells) / max_features))
            eval_cells = eval_cells[::step]

        for r, c in eval_cells:
            is_sim = sim_mask[r, c]
            is_obs = observed_mask[r, c]
            depth = float(simulated_depth_grid[r, c])

            if is_sim and is_obs:
                classification = "TP"
                desc = "True Positive (Model & Satellite Agreed: Flooded)"
                color = "#059669" # Green
            elif is_sim and not is_obs:
                classification = "FP"
                desc = "False Positive (Model Overprediction: Sim Flooded, Obs Dry)"
                color = "#ea580c" # Orange
            elif not is_sim and is_obs:
                classification = "FN"
                desc = "False Negative (Model Underprediction: Missed Flood)"
                color = "#dc2626" # Red
            else:
                continue

            lat_top = round(georef["max_lat"] - r * d_lat, 6)
            lat_bot = round(lat_top - d_lat, 6)
            lon_left = round(georef["min_lon"] + c * d_lon, 6)
            lon_right = round(lon_left + d_lon, 6)

            poly_coords = [[
                [lon_left, lat_top],
                [lon_right, lat_top],
                [lon_right, lat_bot],
                [lon_left, lat_bot],
                [lon_left, lat_top],
            ]]

            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": poly_coords,
                },
                "properties": {
                    "classification": classification,
                    "description": desc,
                    "simulated_depth_m": round(depth, 3),
                    "color": color,
                    "center_lat": round((lat_top + lat_bot) / 2.0, 6),
                    "center_lon": round((lon_left + lon_right) / 2.0, 6),
                },
            })

        return {
            "type": "FeatureCollection",
            "features": features,
            "feature_count": len(features),
            "georef": georef,
        }
