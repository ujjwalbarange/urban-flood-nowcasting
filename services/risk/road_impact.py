"""Road impact and risk assessment.

Assesses the impact of flooding on road infrastructure and computes
ward-level risk indices by combining:
1. Flood depth / extent
2. Road passability
3. Population exposure
4. Infrastructure vulnerability
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
import structlog

from services.routing.dijkstra import PassabilityThresholds, Passability, VehicleProfile, THRESHOLDS

logger = structlog.get_logger()


class RiskLevel(str, Enum):
    """Ward-level risk classification."""

    LOW = "low"           # No significant flooding
    MODERATE = "moderate" # Some roads affected, manageable
    HIGH = "high"         # Major roads impassable, shelter needed
    CRITICAL = "critical" # Severe flooding, immediate evacuation needed


@dataclass
class RoadImpactSummary:
    """Summary of flood impact on the road network."""

    total_segments: int = 0
    clear_segments: int = 0
    caution_segments: int = 0
    difficult_segments: int = 0
    impassable_segments: int = 0

    total_length_km: float = 0.0
    clear_length_km: float = 0.0
    impassable_length_km: float = 0.0

    @property
    def impassable_fraction(self) -> float:
        if self.total_segments == 0:
            return 0.0
        return self.impassable_segments / self.total_segments


@dataclass
class WardRiskAssessment:
    """Risk assessment for a single ward."""

    ward_id: str
    ward_name: str
    risk_level: RiskLevel
    max_depth_m: float
    mean_depth_m: float
    flooded_area_pct: float
    road_impact: RoadImpactSummary
    population_exposed: int = 0
    shelters_available: int = 0
    risk_score: float = 0.0  # Composite 0-100
    recommendations: list[str] = field(default_factory=list)


def assess_road_impact(
    road_segments: list[dict],
    depth_at_segment: dict[str, float],
    vehicle: VehicleProfile = VehicleProfile.CAR,
) -> RoadImpactSummary:
    """Assess flood impact on road segments.

    Args:
        road_segments: List of road segment dicts with segment_id, length_m
        depth_at_segment: Dict of segment_id → flood depth (m)
        vehicle: Vehicle profile for passability assessment

    Returns:
        RoadImpactSummary
    """
    thresholds = THRESHOLDS[vehicle]
    summary = RoadImpactSummary(total_segments=len(road_segments))

    for segment in road_segments:
        seg_id = segment["segment_id"]
        length_km = segment.get("length_m", 0) / 1000.0
        depth = depth_at_segment.get(seg_id, 0.0)
        summary.total_length_km += length_km

        passability = thresholds.classify(depth)
        if passability == Passability.CLEAR:
            summary.clear_segments += 1
            summary.clear_length_km += length_km
        elif passability == Passability.CAUTION:
            summary.caution_segments += 1
        elif passability == Passability.DIFFICULT:
            summary.difficult_segments += 1
        elif passability == Passability.IMPASSABLE:
            summary.impassable_segments += 1
            summary.impassable_length_km += length_km

    return summary


def compute_ward_risk(
    ward_id: str,
    ward_name: str,
    flood_depths: np.ndarray,
    ward_cell_mask: np.ndarray,
    cell_size_m: float,
    road_impact: RoadImpactSummary,
    population: int = 0,
    shelters: int = 0,
) -> WardRiskAssessment:
    """Compute risk assessment for a ward.

    Args:
        ward_id: Ward identifier
        ward_name: Ward display name
        flood_depths: 2D flood depth grid (m)
        ward_cell_mask: Boolean mask of cells belonging to this ward
        cell_size_m: Grid cell size
        road_impact: Pre-computed road impact
        population: Ward population
        shelters: Number of available shelters

    Returns:
        WardRiskAssessment
    """
    ward_depths = flood_depths[ward_cell_mask]

    if ward_depths.size == 0:
        return WardRiskAssessment(
            ward_id=ward_id,
            ward_name=ward_name,
            risk_level=RiskLevel.LOW,
            max_depth_m=0.0,
            mean_depth_m=0.0,
            flooded_area_pct=0.0,
            road_impact=road_impact,
        )

    max_depth = float(np.max(ward_depths))
    mean_depth = float(np.mean(ward_depths))
    flooded_cells = int(np.sum(ward_depths > 0.05))
    total_cells = ward_depths.size
    flooded_area_pct = (flooded_cells / max(total_cells, 1)) * 100.0

    # Composite risk score (0-100)
    depth_score = min(max_depth / 0.5, 1.0) * 30      # 0-30 points
    area_score = min(flooded_area_pct / 50, 1.0) * 25  # 0-25 points
    road_score = road_impact.impassable_fraction * 25    # 0-25 points
    pop_score = min(population / 100000, 1.0) * 20       # 0-20 points

    risk_score = depth_score + area_score + road_score + pop_score

    # Classify risk level
    if risk_score >= 70:
        risk_level = RiskLevel.CRITICAL
    elif risk_score >= 45:
        risk_level = RiskLevel.HIGH
    elif risk_score >= 20:
        risk_level = RiskLevel.MODERATE
    else:
        risk_level = RiskLevel.LOW

    # Generate recommendations
    recommendations = []
    if risk_level == RiskLevel.CRITICAL:
        recommendations.append("IMMEDIATE EVACUATION recommended for low-lying areas")
        recommendations.append("Avoid all road travel unless emergency")
    elif risk_level == RiskLevel.HIGH:
        recommendations.append("Stay indoors, avoid flooded roads")
        recommendations.append("Prepare for possible evacuation")
        if shelters > 0:
            recommendations.append(f"{shelters} shelter(s) available in this ward")
    elif risk_level == RiskLevel.MODERATE:
        recommendations.append("Exercise caution near waterways and low points")
        recommendations.append("Avoid driving through standing water")

    return WardRiskAssessment(
        ward_id=ward_id,
        ward_name=ward_name,
        risk_level=risk_level,
        max_depth_m=round(max_depth, 3),
        mean_depth_m=round(mean_depth, 3),
        flooded_area_pct=round(flooded_area_pct, 1),
        road_impact=road_impact,
        population_exposed=population,
        shelters_available=shelters,
        risk_score=round(risk_score, 1),
        recommendations=recommendations,
    )
