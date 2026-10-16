"""Alerts API router — query and generate flood alerts with PostGIS persistence.

Phase 2A: Alerts now persist to the `alerts` table via SQLAlchemy ORM.
In-memory fallback is retained for when the database is unavailable (standalone mode).
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from services.alerts.cap import (
    IMDSeverity,
    classify_severity_combined,
    generate_cap_xml,
)
from services.database.connection import get_db
from services.database.models import Alert

logger = structlog.get_logger()
router = APIRouter()

# In-memory fallback when DB is unavailable
_alerts_fallback: list[dict] = []


def _build_dedup_key(city: str, severity: str, wards: list[str]) -> str:
    """Build a deduplication key to prevent duplicate alerts for the same event."""
    ward_str = ",".join(sorted(w.strip().lower() for w in wards)) if wards else "all"
    return f"{city.lower()}:{severity}:{ward_str}"


@router.post("/alerts/generate")
async def generate_alert(
    db: Optional[AsyncSession] = Depends(get_db),
    city_name: str = Query("Mumbai"),
    max_depth_m: float = Query(0.25, ge=0.0),
    rainfall_mm_day: float = Query(100.0, ge=0.0),
    flooded_area_pct: float = Query(10.0, ge=0.0, le=100.0),
    affected_wards: Optional[str] = Query(None, description="Comma-separated ward names"),
):
    """Generate a CAP v1.2 flood alert based on current conditions.

    Alert is persisted to PostGIS with lifecycle tracking and deduplication.
    """
    severity = classify_severity_combined(max_depth_m, rainfall_mm_day, flooded_area_pct)
    ward_list = affected_wards.split(",") if affected_wards else []

    xml = generate_cap_xml(
        city_name=city_name,
        severity=severity,
        max_depth_m=max_depth_m,
        affected_wards=ward_list,
    )

    now = datetime.now(timezone.utc)
    dedup_key = _build_dedup_key(city_name, severity.value, ward_list)

    if db is not None:
        try:
            # Check for duplicate active alert
            existing = await db.execute(
                select(Alert).where(
                    Alert.deduplication_key == dedup_key,
                    Alert.status == "active",
                )
            )
            existing_alert = existing.scalars().first()

            if existing_alert:
                logger.info("Duplicate alert prevented", dedup_key=dedup_key)
                return {
                    "severity": severity.value,
                    "cap_xml": xml,
                    "alert_id": str(existing_alert.alert_id),
                    "deduplicated": True,
                    "message": "Active alert already exists for this event",
                }

            # Create new alert
            alert = Alert(
                city_id=city_name.lower(),
                severity=severity.value,
                cap_xml=xml,
                issued_at=now,
                expires_at=now + timedelta(hours=6),
                affected_wards=ward_list,
                status="active",
                valid_from=now,
                valid_until=now + timedelta(hours=6),
                source="manual",
                deduplication_key=dedup_key,
                escalation_level=0,
                metadata_={
                    "max_depth_m": max_depth_m,
                    "rainfall_mm_day": rainfall_mm_day,
                    "flooded_area_pct": flooded_area_pct,
                },
            )
            db.add(alert)
            await db.flush()

            logger.info("Alert persisted to PostGIS", alert_id=str(alert.alert_id), severity=severity.value)

            return {
                "severity": severity.value,
                "cap_xml": xml,
                "alert_id": str(alert.alert_id),
                "alert": {
                    "alert_id": str(alert.alert_id),
                    "severity": severity.value,
                    "city": city_name,
                    "max_depth_m": max_depth_m,
                    "rainfall_mm_day": rainfall_mm_day,
                    "affected_wards": ward_list,
                    "status": "active",
                    "issued_at": now.isoformat(),
                    "expires_at": alert.expires_at.isoformat(),
                },
                "persisted": True,
            }
        except Exception as e:
            logger.error("Failed to persist alert, falling back to memory", error=str(e))

    # Fallback: in-memory storage
    alert_record = {
        "alert_id": str(uuid4()),
        "severity": severity.value,
        "city": city_name,
        "max_depth_m": max_depth_m,
        "rainfall_mm_day": rainfall_mm_day,
        "affected_wards": ward_list,
        "status": "active",
        "issued_at": now.isoformat(),
    }
    _alerts_fallback.append(alert_record)

    return {
        "severity": severity.value,
        "cap_xml": xml,
        "alert": alert_record,
        "persisted": False,
    }


@router.get("/alerts/cap/{city_id}")
async def get_cap_xml(
    city_id: str,
    db: Optional[AsyncSession] = Depends(get_db),
):
    """Get the latest CAP v1.2 XML alert for a city."""
    if db is not None:
        try:
            result = await db.execute(
                select(Alert)
                .where(Alert.city_id == city_id.lower())
                .order_by(Alert.issued_at.desc())
                .limit(1)
            )
            latest = result.scalars().first()
            if latest and latest.cap_xml:
                return Response(content=latest.cap_xml, media_type="application/xml")
        except Exception as e:
            logger.debug("DB query failed for CAP XML, generating default", error=str(e))

    # Fallback: check in-memory or generate default
    city_alerts = [a for a in _alerts_fallback if a["city"].lower() == city_id.lower()]
    if city_alerts:
        latest = city_alerts[-1]
        severity = IMDSeverity(latest["severity"])
        xml = generate_cap_xml(
            city_name=latest["city"],
            severity=severity,
            max_depth_m=latest["max_depth_m"],
            affected_wards=latest.get("affected_wards", []),
        )
    else:
        xml = generate_cap_xml(
            city_name=city_id.title(),
            severity=IMDSeverity.GREEN,
            max_depth_m=0.0,
        )
    return Response(content=xml, media_type="application/xml")


@router.get("/alerts/active")
async def get_active_alerts(
    db: Optional[AsyncSession] = Depends(get_db),
    city: Optional[str] = Query(None, description="Filter by city name"),
):
    """Get all active alerts (persisted in PostGIS)."""
    if db is not None:
        try:
            query = select(Alert).where(Alert.status == "active")
            if city:
                query = query.where(Alert.city_id == city.lower())
            query = query.order_by(Alert.issued_at.desc())

            result = await db.execute(query)
            alerts = result.scalars().all()

            alert_dicts = []
            for a in alerts:
                alert_dicts.append({
                    "alert_id": str(a.alert_id),
                    "severity": a.severity,
                    "city": a.city_id,
                    "issued_at": a.issued_at.isoformat() if a.issued_at else None,
                    "expires_at": a.expires_at.isoformat() if a.expires_at else None,
                    "affected_wards": a.affected_wards or [],
                    "status": a.status,
                    "source": a.source,
                    "escalation_level": a.escalation_level,
                    "confidence_score": a.confidence_score,
                    "recommended_action": a.recommended_action,
                    "affected_population": a.affected_population,
                })

            return {"alerts": alert_dicts, "total": len(alert_dicts), "source": "postgis"}
        except Exception as e:
            logger.debug("DB query failed, falling back to memory", error=str(e))

    # Fallback
    alerts = _alerts_fallback
    if city:
        alerts = [a for a in alerts if a["city"].lower() == city.lower()]
    return {"alerts": alerts, "total": len(alerts), "source": "memory"}


@router.patch("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    acknowledged_by: str = Query(..., description="Name or ID of person acknowledging"),
    db: Optional[AsyncSession] = Depends(get_db),
):
    """Acknowledge an active alert."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        result = await db.execute(select(Alert).where(Alert.alert_id == alert_id))
        alert = result.scalars().first()
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")

        alert.status = "acknowledged"
        alert.acknowledged_at = datetime.now(timezone.utc)
        alert.acknowledged_by = acknowledged_by
        await db.flush()

        return {"alert_id": alert_id, "status": "acknowledged", "acknowledged_by": acknowledged_by}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    resolution_notes: str = Query("", description="Resolution notes"),
    db: Optional[AsyncSession] = Depends(get_db),
):
    """Resolve (close) an alert."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        result = await db.execute(select(Alert).where(Alert.alert_id == alert_id))
        alert = result.scalars().first()
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")

        alert.status = "resolved"
        alert.resolved_at = datetime.now(timezone.utc)
        alert.resolution_notes = resolution_notes
        await db.flush()

        return {"alert_id": alert_id, "status": "resolved"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
