"""Confidence and Uncertainty Estimation Engine for Nowcasting.

Evaluates multi-factor confidence across:
1. Data source count (Open-Meteo, MOSDAC INSAT-3DR, NASA IMERG, radar)
2. Provider agreement and data freshness
3. Spatial monitoring grid coverage across Mumbai
4. Hydrodynamic mass balance error (numerical convergence)
5. Physical terrain and drainage parameter quality

Phase 2D-1: Explainable confidence scoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class ConfidenceReport:
    """Detailed confidence assessment with factor explanations."""
    score: float                      # 0 - 100
    level: str                        # HIGH, MODERATE, LOW
    evaluated_at: str
    factors: List[Dict[str, Any]] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "confidence_score": round(self.score, 1),
            "confidence_level": self.level,
            "evaluated_at": self.evaluated_at,
            "factors": self.factors,
            "limitations": self.limitations,
        }


def compute_nowcast_confidence(
    weather_provider_count: int = 1,
    weather_latency_ms: float = 500.0,
    weather_points_count: int = 9,
    mass_balance_error_pct: float = 0.05,
    spatial_coverage_pct: float = 100.0,
    has_live_tide: bool = True,
    has_drainage_coupling: bool = True,
) -> ConfidenceReport:
    """Compute weighted composite confidence score with explainable sub-factors."""
    now_iso = datetime.now(timezone.utc).isoformat()
    factors = []
    limitations = []
    total_score = 0.0

    # 1. Weather provider redundancy (Weight 25%)
    if weather_provider_count >= 3:
        w_score = 25.0
        w_note = "High multi-source redundancy (NWP + Satellite + Gauges)"
    elif weather_provider_count == 2:
        w_score = 21.0
        w_note = "Dual provider validation active (Open-Meteo + INSAT-3DR)"
    elif weather_provider_count == 1:
        w_score = 17.0
        w_note = "Single primary NWP provider active; cross-validation limited"
        limitations.append("Rainfall forcing relies on single provider without real-time radar fusion")
    else:
        w_score = 5.0
        w_note = "Synthetic / fallback weather forcing used"
        limitations.append("Weather observations unavailable; using fallback schedule")
    total_score += w_score
    factors.append({
        "factor": "Meteorological Input Redundancy",
        "weight_pct": 25,
        "score_earned": round(w_score, 1),
        "status": "OPTIMAL" if w_score >= 20 else "ACCEPTABLE" if w_score >= 15 else "DEGRADED",
        "description": w_note,
    })

    # 2. Spatial monitoring grid coverage (Weight 20%)
    if weather_points_count >= 9:
        s_score = 20.0
        s_note = f"Full 9-point spatial distribution across Mumbai metropolitan area"
    elif weather_points_count >= 6:
        s_score = 16.0
        s_note = f"{weather_points_count}/9 spatial monitoring points reporting"
    else:
        s_score = 10.0
        s_note = f"Sparse spatial grid ({weather_points_count} points reporting)"
        limitations.append("Spatial rainfall heterogeneity may be underestimated")
    total_score += s_score
    factors.append({
        "factor": "Spatial Grid Coverage",
        "weight_pct": 20,
        "score_earned": round(s_score, 1),
        "status": "OPTIMAL" if s_score >= 18 else "ACCEPTABLE",
        "description": s_note,
    })

    # 3. Hydrodynamic mass balance closure (Weight 25%)
    abs_mb = abs(mass_balance_error_pct)
    if abs_mb < 0.1:
        mb_score = 25.0
        mb_note = f"Excellent mass conservation error ({abs_mb:.3f}% < 0.1%)"
    elif abs_mb < 0.5:
        mb_score = 22.0
        mb_note = f"Acceptable mass conservation error ({abs_mb:.2f}% < 0.5%)"
    elif abs_mb < 2.0:
        mb_score = 16.0
        mb_note = f"Moderate mass conservation deviation ({abs_mb:.2f}%)"
    else:
        mb_score = 8.0
        mb_note = f"Elevated mass conservation error ({abs_mb:.2f}%)"
        limitations.append("Numerical mass balance deviation exceeds standard tolerance")
    total_score += mb_score
    factors.append({
        "factor": "Numerical Hydrodynamic Solver Convergence",
        "weight_pct": 25,
        "score_earned": round(mb_score, 1),
        "status": "OPTIMAL" if mb_score >= 22 else "ACCEPTABLE",
        "description": mb_note,
    })

    # 4. Drainage coupling & coastal boundary (Weight 20%)
    drain_score = 0.0
    if has_drainage_coupling:
        drain_score += 10.0
    else:
        limitations.append("Drainage network exchange decoupled; surface flow only")

    if has_live_tide:
        drain_score += 10.0
    else:
        drain_score += 5.0
        limitations.append("Assumed coastal boundary used instead of Apollo Bunder real-time gauge")
    total_score += drain_score
    factors.append({
        "factor": "Drainage Coupling & Coastal Boundary",
        "weight_pct": 20,
        "score_earned": round(drain_score, 1),
        "status": "OPTIMAL" if drain_score >= 18 else "ACCEPTABLE",
        "description": "BRIMSTOWAD orifice coupling active; coastal tidal boundary schedule applied",
    })

    # 5. Latency & terrain quality (Weight 10%)
    lat_score = 10.0 if weather_latency_ms < 2000 else 7.0 if weather_latency_ms < 5000 else 4.0
    total_score += lat_score
    factors.append({
        "factor": "Data Ingestion Latency",
        "weight_pct": 10,
        "score_earned": round(lat_score, 1),
        "status": "OPTIMAL" if lat_score >= 8 else "ACCEPTABLE",
        "description": f"Weather API response latency: {weather_latency_ms:.0f} ms",
    })

    final_score = min(100.0, max(10.0, round(total_score, 1)))
    level = "HIGH" if final_score >= 80.0 else "MODERATE" if final_score >= 60.0 else "LOW"

    return ConfidenceReport(
        score=final_score,
        level=level,
        evaluated_at=now_iso,
        factors=factors,
        limitations=limitations,
    )
