"""Decision Support API router.

Provides endpoints for the municipal command center to get
real-time decision packages, response recommendations, and
resource allocation guidance.

Phase 2F: Integrates ward risk + decision engine + confidence scoring.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Query

from services.decision.engine import (
    DecisionPackage,
    generate_decision_package,
    determine_response_level,
    ResponseLevel,
)
from services.risk.ward_risk import compute_all_ward_risks, compute_ward_risk

logger = structlog.get_logger()
router = APIRouter(prefix="/decision", tags=["Decision Support"])


@router.get("/package")
async def get_decision_package():
    """Get the current decision support package for the command center.

    Computes ward risks, determines response level, and generates
    actionable recommendations with resource allocation guidance.
    """
    # 1. Compute ward risks
    ward_risks = await compute_all_ward_risks()

    # 2. Get current max depth from latest nowcast
    max_depth = 0.0
    rainfall_mmh = 0.0
    confidence = "MODERATE"
    try:
        from services.nowcast.pipeline import get_latest_nowcast, get_latest_weather
        nowcast = get_latest_nowcast()
        if nowcast and nowcast.status == "completed":
            max_depth = nowcast.max_depth_m
            confidence = getattr(nowcast, "confidence_level", "MODERATE") or "MODERATE"

        weather = get_latest_weather()
        if weather:
            rainfall_mmh = weather.mean_rainfall_mmh
    except Exception:
        pass

    # 3. Generate decision package
    pkg = generate_decision_package(
        ward_risks=ward_risks,
        max_depth_m=max_depth,
        rainfall_mmh=rainfall_mmh,
        confidence_level=confidence,
    )

    return pkg.to_dict()


@router.get("/response-level")
async def get_response_level(
    max_depth_m: float = Query(0.0, ge=0.0, description="Current max flood depth in meters"),
    critical_wards: int = Query(0, ge=0, description="Number of wards at CRITICAL risk"),
    high_risk_wards: int = Query(0, ge=0, description="Number of wards at HIGH risk"),
    rainfall_mmh: float = Query(0.0, ge=0.0, description="Current rainfall intensity"),
):
    """Determine the municipal response level for given conditions.

    Returns the recommended response level based on IMD/NDMA guidelines.
    """
    level = determine_response_level(
        max_depth_m=max_depth_m,
        critical_wards=critical_wards,
        high_risk_wards=high_risk_wards,
        rainfall_mmh=rainfall_mmh,
    )

    # Map to IMD color code
    color_map = {
        ResponseLevel.NORMAL: "GREEN",
        ResponseLevel.ADVISORY: "YELLOW",
        ResponseLevel.ALERT: "ORANGE",
        ResponseLevel.WARNING: "RED",
        ResponseLevel.EMERGENCY: "RED",
        ResponseLevel.CATASTROPHIC: "RED",
    }

    return {
        "response_level": level,
        "imd_color": color_map.get(level, "GREEN"),
        "inputs": {
            "max_depth_m": max_depth_m,
            "critical_wards": critical_wards,
            "high_risk_wards": high_risk_wards,
            "rainfall_mmh": rainfall_mmh,
        },
    }


@router.get("/ward/{ward_id}/risk")
async def get_ward_specific_risk(ward_id: str):
    """Get detailed risk assessment for a specific ward."""
    all_risks = await compute_all_ward_risks()
    for risk in all_risks:
        if risk.ward_id.lower() == ward_id.lower() or risk.ward_name.lower() == ward_id.lower():
            return risk.to_dict()
    return {"error": f"Ward '{ward_id}' not found", "available_wards": [r.ward_id for r in all_risks]}
