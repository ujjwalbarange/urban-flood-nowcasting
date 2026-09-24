"""Alerts API router — query and generate flood alerts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from services.alerts.cap import (
    IMDSeverity,
    classify_severity_combined,
    generate_cap_xml,
)

logger = structlog.get_logger()
router = APIRouter()

# Alert store (in-memory for dev; use DB in production)
_alerts: list[dict] = []


@router.post("/alerts/generate")
async def generate_alert(
    city_name: str = Query("Mumbai"),
    max_depth_m: float = Query(0.25, ge=0.0),
    rainfall_mm_day: float = Query(100.0, ge=0.0),
    flooded_area_pct: float = Query(10.0, ge=0.0, le=100.0),
    affected_wards: Optional[str] = Query(None, description="Comma-separated ward names"),
):
    """Generate a CAP v1.2 flood alert based on current conditions."""
    severity = classify_severity_combined(max_depth_m, rainfall_mm_day, flooded_area_pct)

    ward_list = affected_wards.split(",") if affected_wards else []

    xml = generate_cap_xml(
        city_name=city_name,
        severity=severity,
        max_depth_m=max_depth_m,
        affected_wards=ward_list,
    )

    alert_record = {
        "severity": severity.value,
        "city": city_name,
        "max_depth_m": max_depth_m,
        "rainfall_mm_day": rainfall_mm_day,
        "affected_wards": ward_list,
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }
    _alerts.append(alert_record)

    return {
        "severity": severity.value,
        "cap_xml": xml,
        "alert": alert_record,
    }


@router.get("/alerts/cap/{city_id}")
async def get_cap_xml(city_id: str):
    """Get the latest CAP v1.2 XML alert for a city."""
    city_alerts = [a for a in _alerts if a["city"].lower() == city_id.lower()]
    if not city_alerts:
        xml = generate_cap_xml(
            city_name=city_id.title(),
            severity=IMDSeverity.GREEN,
            max_depth_m=0.0,
        )
        return Response(content=xml, media_type="application/xml")

    latest = city_alerts[-1]
    severity = IMDSeverity(latest["severity"])
    xml = generate_cap_xml(
        city_name=latest["city"],
        severity=severity,
        max_depth_m=latest["max_depth_m"],
        affected_wards=latest.get("affected_wards", []),
    )
    return Response(content=xml, media_type="application/xml")


@router.get("/alerts/active")
async def get_active_alerts(
    city: Optional[str] = Query(None, description="Filter by city name"),
):
    """Get all active alerts."""
    alerts = _alerts
    if city:
        alerts = [a for a in alerts if a["city"].lower() == city.lower()]
    return {"alerts": alerts, "total": len(alerts)}
