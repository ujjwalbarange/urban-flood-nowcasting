"""Alert Engine — Full Operational Lifecycle for MUFNS.

Manages flood alert lifecycle: detection, threshold evaluation, deduplication,
CAP v1.2 XML generation, DB persistence, escalation, acknowledgement, and resolution.
Aligned with NDMA protocols and IMD color coding.

Phase 2F-1: Automated alert engine.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
import structlog
from sqlalchemy import select, update, and_, desc

from services.alerts.thresholds import (
    AlertSeverity,
    AlertThresholdConfig,
    DEFAULT_THRESHOLDS,
)
from services.alerts.cap import (
    generate_cap_xml,
    IMDSeverity,
    IMD_TO_CAP_SEVERITY,
)
from services.database.connection import async_session_factory, verify_db_connectivity
from services.database.models import Alert

logger = structlog.get_logger()

# In-memory alert store for standalone/testing operation
_in_memory_alerts: Dict[str, Dict[str, Any]] = {}


def _generate_dedup_key(city_id: str, ward_id: Optional[str], event_window: str) -> str:
    """Generate deterministic deduplication key for a 6-hour event window."""
    raw = f"{city_id}:{ward_id or 'all'}:{event_window}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class AlertEngine:
    """Core alert lifecycle management engine."""

    def __init__(self, thresholds: Optional[AlertThresholdConfig] = None):
        self.thresholds = thresholds or DEFAULT_THRESHOLDS

    async def evaluate_and_generate_alerts(
        self,
        city_id: str = "mumbai",
        max_depth_m: float = 0.0,
        rainfall_rate_mmh: float = 0.0,
        exposed_population: int = 0,
        critical_infra_count: int = 0,
        tide_height_cd: float = 0.0,
        ward_risks: Optional[List[Dict[str, Any]]] = None,
        run_id: Optional[str] = None,
        confidence_score: float = 85.0,
    ) -> List[Dict[str, Any]]:
        """Evaluate flood state and generate/escalate alerts without duplicates."""
        now = datetime.now(timezone.utc)
        # 6-hour operational window identifier for deduplication
        window_id = f"{now.strftime('%Y%m%d')}_{now.hour // 6}"

        generated_alerts: List[Dict[str, Any]] = []

        # 1. City-wide / catchment general alert
        city_severity = self.thresholds.evaluate_severity(
            max_depth_m=max_depth_m,
            rainfall_rate_mmh=rainfall_rate_mmh,
            exposed_population=exposed_population,
            critical_infra_count=critical_infra_count,
            tide_height_cd=tide_height_cd,
        )

        if city_severity in (AlertSeverity.WATCH, AlertSeverity.WARNING, AlertSeverity.EMERGENCY):
            dedup_key = _generate_dedup_key(city_id, "city_wide", window_id)
            alert_dict = await self._create_or_escalate_alert(
                city_id=city_id,
                ward_id="ALL",
                severity=city_severity,
                max_depth_m=max_depth_m,
                rainfall_rate_mmh=rainfall_rate_mmh,
                exposed_population=exposed_population,
                critical_infra_count=critical_infra_count,
                dedup_key=dedup_key,
                run_id=run_id,
                confidence_score=confidence_score,
            )
            if alert_dict:
                generated_alerts.append(alert_dict)

        # 2. Ward-specific alerts if ward risks provided
        if ward_risks:
            for wr in ward_risks:
                w_name = wr.get("ward") or wr.get("ward_name")
                w_score = float(wr.get("risk_score", wr.get("composite_risk", 0.0)))
                w_depth = float(wr.get("max_depth_m", max_depth_m * 0.8))
                w_pop = int(wr.get("population_at_risk", exposed_population // max(1, len(ward_risks))))

                w_severity = AlertSeverity.INFO
                if w_score >= 0.75 or w_depth >= self.thresholds.depth_emergency_m:
                    w_severity = AlertSeverity.EMERGENCY
                elif w_score >= 0.50 or w_depth >= self.thresholds.depth_warning_m:
                    w_severity = AlertSeverity.WARNING
                elif w_score >= 0.30 or w_depth >= self.thresholds.depth_watch_m:
                    w_severity = AlertSeverity.WATCH

                if w_severity in (AlertSeverity.WARNING, AlertSeverity.EMERGENCY):
                    w_dedup = _generate_dedup_key(city_id, w_name, window_id)
                    w_alert = await self._create_or_escalate_alert(
                        city_id=city_id,
                        ward_id=w_name,
                        severity=w_severity,
                        max_depth_m=w_depth,
                        rainfall_rate_mmh=rainfall_rate_mmh,
                        exposed_population=w_pop,
                        critical_infra_count=1 if w_severity == AlertSeverity.EMERGENCY else 0,
                        dedup_key=w_dedup,
                        run_id=run_id,
                        confidence_score=confidence_score,
                    )
                    if w_alert:
                        generated_alerts.append(w_alert)

        return generated_alerts

    async def _create_or_escalate_alert(
        self,
        city_id: str,
        ward_id: Optional[str],
        severity: AlertSeverity,
        max_depth_m: float,
        rainfall_rate_mmh: float,
        exposed_population: int,
        critical_infra_count: int,
        dedup_key: str,
        run_id: Optional[str] = None,
        confidence_score: float = 85.0,
    ) -> Optional[Dict[str, Any]]:
        """Create a new alert or escalate an existing active alert for the same key."""
        now = datetime.now(timezone.utc)
        valid_until = now + timedelta(hours=4)

        # Action recommendation mapping
        if severity == AlertSeverity.EMERGENCY:
            action = (
                "EMERGENCY PROTOCOL: Evacuate ground floors in low-lying subways. Deploy mobile de-watering pumps. "
                "Close inundation-prone underpasses (Milan, Andheri, Khar). Municipal disaster cells activated."
            )
            cap_sev = "Extreme"
            imd_sev = IMDSeverity.RED
        elif severity == AlertSeverity.WARNING:
            action = (
                "WARNING: Water accumulation exceeding curb depth. Discontinue non-essential travel along arterial roads. "
                "Traffic police diverting vehicles from chronic waterlogging junctions."
            )
            cap_sev = "Severe"
            imd_sev = IMDSeverity.ORANGE
        else:
            action = (
                "WATCH: Persistent rainfall detected. Monitor localized drainage channels and low spots."
            )
            cap_sev = "Moderate"
            imd_sev = IMDSeverity.YELLOW

        # Generate standard CAP XML
        cap_xml_str = generate_cap_xml(
            city_name=city_id.title(),
            severity=imd_sev,
            headline=f"Mumbai Urban Flood {severity.value}: Ward {ward_id or 'City-Wide'}",
            description=f"Water depth {max_depth_m:.2f}m detected with rainfall rate {rainfall_rate_mmh:.1f} mm/h.",
            affected_wards=[ward_id] if ward_id and ward_id != "ALL" else ["All Municipal Wards"],
            max_depth_m=max_depth_m,
            alert_id=dedup_key,
        )

        db_available = await verify_db_connectivity()
        if db_available and async_session_factory is not None:
            try:
                async with async_session_factory() as session:
                    # Check for existing active alert with this dedup key
                    stmt = (
                        select(Alert)
                        .where(
                            and_(
                                Alert.deduplication_key == dedup_key,
                                Alert.status.in_(["active", "acknowledged"]),
                            )
                        )
                    )
                    res = await session.execute(stmt)
                    existing = res.scalar_one_or_none()

                    if existing is not None:
                        # Existing alert found -> escalate if new severity is higher
                        existing_sev = existing.severity.upper() if existing.severity else "WATCH"
                        if severity == AlertSeverity.EMERGENCY and existing_sev != "EMERGENCY":
                            existing.severity = cap_sev.lower()
                            existing.escalation_level = (existing.escalation_level or 0) + 1
                            existing.recommended_action = action
                            existing.affected_population = exposed_population
                            existing.valid_until = valid_until
                            existing.cap_xml = cap_xml_str
                            await session.commit()
                            logger.info("Alert escalated in DB", alert_id=str(existing.alert_id), new_severity=cap_sev)
                        return {
                            "alert_id": str(existing.alert_id),
                            "severity": existing.severity,
                            "ward_id": existing.ward_id,
                            "status": existing.status,
                            "escalated": True,
                            "deduplication_key": dedup_key,
                            "issued_at": existing.issued_at.isoformat() if existing.issued_at else now.isoformat(),
                        }
                    else:
                        # Create brand new Alert record
                        new_alert = Alert(
                            city_id=city_id,
                            severity=cap_sev.lower(),
                            cap_xml=cap_xml_str,
                            issued_at=now,
                            valid_from=now,
                            valid_until=valid_until,
                            expires_at=valid_until,
                            ward_id=ward_id,
                            affected_wards=[ward_id] if ward_id else ["All"],
                            status="active",
                            source="nowcast_engine",
                            affected_population=exposed_population,
                            recommended_action=action,
                            escalation_level=0,
                            deduplication_key=dedup_key,
                            confidence_score=confidence_score,
                            run_id=UUID(run_id) if run_id else None,
                        )
                        session.add(new_alert)
                        await session.commit()
                        logger.info("New alert persisted to PostGIS", alert_id=str(new_alert.alert_id), ward=ward_id)
                        return {
                            "alert_id": str(new_alert.alert_id),
                            "severity": new_alert.severity,
                            "ward_id": ward_id,
                            "status": "active",
                            "escalated": False,
                            "deduplication_key": dedup_key,
                            "issued_at": now.isoformat(),
                            "action": action,
                        }
            except Exception as e:
                logger.warning("Failed DB alert save, falling back to in-memory", error=str(e))

        # Fallback to in-memory store
        alert_id_str = str(uuid4())
        existing = _in_memory_alerts.get(dedup_key)
        if existing and existing["status"] in ("active", "acknowledged"):
            if severity == AlertSeverity.EMERGENCY and existing["severity"] != "extreme":
                existing["severity"] = "extreme"
                existing["escalation_level"] += 1
                existing["recommended_action"] = action
                existing["valid_until"] = valid_until.isoformat()
            return existing

        record = {
            "alert_id": alert_id_str,
            "city_id": city_id,
            "severity": cap_sev.lower(),
            "ward_id": ward_id,
            "affected_wards": [ward_id] if ward_id else ["All"],
            "status": "active",
            "source": "nowcast_engine",
            "affected_population": exposed_population,
            "recommended_action": action,
            "escalation_level": 0,
            "deduplication_key": dedup_key,
            "confidence_score": confidence_score,
            "issued_at": now.isoformat(),
            "valid_until": valid_until.isoformat(),
            "cap_xml": cap_xml_str,
        }
        _in_memory_alerts[dedup_key] = record
        return record

    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge an active alert by municipal authority."""
        now = datetime.now(timezone.utc)
        db_available = await verify_db_connectivity()
        if db_available and async_session_factory is not None:
            try:
                async with async_session_factory() as session:
                    stmt = (
                        update(Alert)
                        .where(Alert.alert_id == UUID(alert_id))
                        .values(
                            status="acknowledged",
                            acknowledged_at=now,
                            acknowledged_by=acknowledged_by,
                        )
                    )
                    res = await session.execute(stmt)
                    await session.commit()
                    return res.rowcount > 0
            except Exception as e:
                logger.warning("Failed to acknowledge alert in DB", error=str(e))

        for k, a in _in_memory_alerts.items():
            if a["alert_id"] == alert_id:
                a["status"] = "acknowledged"
                a["acknowledged_at"] = now.isoformat()
                a["acknowledged_by"] = acknowledged_by
                return True
        return False

    async def resolve_alert(self, alert_id: str, resolution_notes: str) -> bool:
        """Resolve a flood alert once water recedes."""
        now = datetime.now(timezone.utc)
        db_available = await verify_db_connectivity()
        if db_available and async_session_factory is not None:
            try:
                async with async_session_factory() as session:
                    stmt = (
                        update(Alert)
                        .where(Alert.alert_id == UUID(alert_id))
                        .values(
                            status="resolved",
                            resolved_at=now,
                            resolution_notes=resolution_notes,
                        )
                    )
                    res = await session.execute(stmt)
                    await session.commit()
                    return res.rowcount > 0
            except Exception as e:
                logger.warning("Failed to resolve alert in DB", error=str(e))

        for k, a in _in_memory_alerts.items():
            if a["alert_id"] == alert_id:
                a["status"] = "resolved"
                a["resolved_at"] = now.isoformat()
                a["resolution_notes"] = resolution_notes
                return True
        return False

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Return currently active and acknowledged alerts."""
        return [
            a for a in _in_memory_alerts.values()
            if a.get("status") in ("active", "acknowledged")
        ]


_global_alert_engine = AlertEngine()


def get_alert_engine() -> AlertEngine:
    return _global_alert_engine

