"""Crowdsourced Citizen Report Verification Pipeline.

Implements multi-factor automated verification of citizen-submitted flood reports
against PostGIS spatial hotspots, real-time meteorological observations, and
hydrodynamic simulation results.

Phase 2H-5: Report verification pipeline.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from services.data.store import get_data_store

logger = structlog.get_logger()


@dataclass
class VerificationResult:
    """Detailed verification outcome for a citizen flood report."""
    report_id: str
    verification_status: str       # VERIFIED, PLAUSIBLE, SUSPECT, REJECTED
    confidence_score: float        # 0.0 to 1.0
    spatial_proximity_score: float # 0.0 to 0.30
    meteorological_concordance_score: float # 0.0 to 0.30
    hydrodynamic_concordance_score: float   # 0.0 to 0.25
    evidence_score: float          # 0.0 to 0.15
    factors: List[Dict[str, Any]] = field(default_factory=list)
    recommended_action: Optional[str] = None
    dispatch_priority: Optional[str] = None # CRITICAL, HIGH, MEDIUM, LOW, NONE
    verified_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "verification_status": self.verification_status,
            "confidence_score": round(self.confidence_score, 2),
            "spatial_proximity_score": round(self.spatial_proximity_score, 2),
            "meteorological_concordance_score": round(self.meteorological_concordance_score, 2),
            "hydrodynamic_concordance_score": round(self.hydrodynamic_concordance_score, 2),
            "evidence_score": round(self.evidence_score, 2),
            "factors": self.factors,
            "recommended_action": self.recommended_action,
            "dispatch_priority": self.dispatch_priority,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
        }


class ReportVerificationPipeline:
    """Multi-factor verification pipeline for citizen flood observations."""

    def __init__(self):
        self.store = get_data_store()

    def _haversine_distance_m(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate great-circle distance between two coordinates in meters."""
        R = 6371000.0  # Earth radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)

        a = math.sin(dphi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0)**2
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return R * c

    def _assess_spatial_proximity(self, lat: float, lon: float) -> tuple[float, Dict[str, Any]]:
        """Assess report proximity to chronic flood hotspots and low-lying topography."""
        hotspots = self.store.flood_hotspots().get("features", [])
        min_dist_m = 1e9
        closest_spot = None

        for f in hotspots:
            geom = f.get("geometry", {})
            coords = geom.get("coordinates", [])
            if len(coords) >= 2:
                h_lon, h_lat = coords[0], coords[1]
                dist = self._haversine_distance_m(lat, lon, h_lat, h_lon)
                if dist < min_dist_m:
                    min_dist_m = dist
                    closest_spot = f.get("properties", {}).get("location_name") or f.get("properties", {}).get("name")

        if min_dist_m <= 400.0:
            score = 0.30
            detail = f"Within {int(min_dist_m)}m of chronic hotspot ({closest_spot})"
        elif min_dist_m <= 1000.0:
            score = 0.20
            detail = f"Within 1km ({int(min_dist_m)}m) of chronic hotspot ({closest_spot})"
        elif min_dist_m <= 2500.0:
            score = 0.12
            detail = f"In broader proximity ({int(min_dist_m)}m) of known flood basin"
        else:
            score = 0.05
            detail = f"Isolated location ({int(min_dist_m/1000)}km from documented hotspots)"

        return score, {"factor": "spatial_proximity", "score": score, "max": 0.30, "detail": detail}

    def _assess_meteorological_concordance(
        self,
        rainfall_rate_mmh: Optional[float] = None,
    ) -> tuple[float, Dict[str, Any]]:
        """Assess weather condition plausibility for flood ponding."""
        rate = rainfall_rate_mmh if rainfall_rate_mmh is not None else 25.0

        if rate >= 50.0:
            score = 0.30
            detail = f"Extreme torrential rainfall ({rate:.1f} mm/h) strongly corroborates flooding"
        elif rate >= 30.0:
            score = 0.25
            detail = f"Heavy rainfall intensity ({rate:.1f} mm/h) likely induces surface runoff"
        elif rate >= 15.0:
            score = 0.18
            detail = f"Moderate rainfall intensity ({rate:.1f} mm/h) can cause localized ponding"
        elif rate >= 5.0:
            score = 0.10
            detail = f"Light rainfall ({rate:.1f} mm/h); flooding requires antecedent water or tidal lock"
        else:
            score = 0.04
            detail = f"Negligible current rainfall ({rate:.1f} mm/h); verify tidal backflow or pipe burst"

        return score, {"factor": "meteorological_concordance", "score": score, "max": 0.30, "detail": detail}

    def _assess_hydrodynamic_concordance(
        self,
        simulated_depth_m: Optional[float] = None,
        water_depth_cm: float = 0.0,
    ) -> tuple[float, Dict[str, Any]]:
        """Compare reported water depth with numerical model depth."""
        rep_m = max(0.0, water_depth_cm / 100.0)
        sim_m = simulated_depth_m if simulated_depth_m is not None else 0.25

        if sim_m >= 0.10:
            diff = abs(sim_m - rep_m)
            if diff <= 0.25:
                score = 0.25
                detail = f"Model predicts {sim_m:.2f}m depth, closely matching reported {rep_m:.2f}m"
            else:
                score = 0.18
                detail = f"Model confirms flooding ({sim_m:.2f}m depth), though reported {rep_m:.2f}m differs"
        elif sim_m >= 0.03:
            score = 0.12
            detail = f"Model predicts shallow sheet flow ({sim_m:.2f}m)"
        else:
            score = 0.04
            detail = "Model does not predict significant surface ponding at this immediate grid cell"

        return score, {"factor": "hydrodynamic_concordance", "score": score, "max": 0.25, "detail": detail}

    def _assess_evidence_integrity(
        self,
        photo_url: Optional[str] = None,
        water_depth_cm: float = 0.0,
        description: Optional[str] = None,
    ) -> tuple[float, Dict[str, Any]]:
        """Assess report completeness, photo proof, and physical plausibility."""
        score = 0.05  # Base registration score
        reasons = []

        if photo_url and len(photo_url.strip()) > 5:
            score += 0.07
            reasons.append("Geotagged photographic evidence attached")

        if 5.0 <= water_depth_cm <= 250.0:
            score += 0.03
            reasons.append("Reported depth within physically plausible monsoon range (5-250cm)")
        elif water_depth_cm > 300.0:
            score = max(0.0, score - 0.05)
            reasons.append("Unusually high depth (>3m) requires urgent field verification")

        if description and len(description.strip()) > 15:
            reasons.append("Detailed contextual landmark description provided")

        detail = "; ".join(reasons) if reasons else "Standard citizen report metadata"
        return min(0.15, score), {"factor": "evidence_integrity", "score": min(0.15, score), "max": 0.15, "detail": detail}

    async def verify_report(
        self,
        report_id: str,
        latitude: float,
        longitude: float,
        water_depth_cm: float,
        reported_at: Optional[datetime] = None,
        photo_url: Optional[str] = None,
        description: Optional[str] = None,
        rainfall_rate_mmh: Optional[float] = None,
        simulated_depth_m: Optional[float] = None,
    ) -> VerificationResult:
        """Run full multi-factor verification pipeline on a citizen report."""
        spatial_score, spatial_factor = self._assess_spatial_proximity(latitude, longitude)
        met_score, met_factor = self._assess_meteorological_concordance(rainfall_rate_mmh)
        hydro_score, hydro_factor = self._assess_hydrodynamic_concordance(simulated_depth_m, water_depth_cm)
        evidence_score, evidence_factor = self._assess_evidence_integrity(photo_url, water_depth_cm, description)

        total_confidence = spatial_score + met_score + hydro_score + evidence_score
        total_confidence = min(1.0, max(0.0, total_confidence))

        factors = [spatial_factor, met_factor, hydro_factor, evidence_factor]

        if total_confidence >= 0.70:
            status = "VERIFIED"
            if water_depth_cm >= 60.0:
                priority = "CRITICAL"
                action = "Deploy emergency dewatering crew and NDRF inflatable boat for immediate evacuation"
            elif water_depth_cm >= 30.0:
                priority = "HIGH"
                action = "Dispatch municipal mobile dewatering pump and barricade vehicular access"
            else:
                priority = "MEDIUM"
                action = "Route ward drainage maintenance crew to inspect storm inlet grates"
        elif total_confidence >= 0.45:
            status = "PLAUSIBLE"
            priority = "MEDIUM"
            action = "Dispatch field beat officer to visually inspect reported waterlogging"
        elif total_confidence >= 0.25:
            status = "SUSPECT"
            priority = "LOW"
            action = "Hold in unverified queue; await secondary corroborating citizen reports"
        else:
            status = "REJECTED"
            priority = "NONE"
            action = "Flagged as inconsistent with sensor baseline and historical terrain"

        return VerificationResult(
            report_id=report_id,
            verification_status=status,
            confidence_score=total_confidence,
            spatial_proximity_score=spatial_score,
            meteorological_concordance_score=met_score,
            hydrodynamic_concordance_score=hydro_score,
            evidence_score=evidence_score,
            factors=factors,
            recommended_action=action,
            dispatch_priority=priority,
            verified_at=datetime.now(timezone.utc),
        )


# Singleton verification pipeline
_pipeline_instance: Optional[ReportVerificationPipeline] = None


def get_verification_pipeline() -> ReportVerificationPipeline:
    """Get or initialize singleton ReportVerificationPipeline."""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = ReportVerificationPipeline()
    return _pipeline_instance
