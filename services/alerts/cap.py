"""CAP v1.2 alert generation — Common Alerting Protocol (ITU-T X.1303).

Generates standardized machine-readable flood alerts compliant with
OASIS CAP v1.2. These can be consumed by:
- Emergency management systems
- Public warning systems
- Media organizations
- NDMA (National Disaster Management Authority)

IMD color-coded severity classification:
- GREEN:  No significant rainfall / flooding expected
- YELLOW: Heavy rainfall possible, be alert
- ORANGE: Very heavy rainfall, be prepared, flood likely
- RED:    Extremely heavy rainfall, take action, severe flooding
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4
from xml.etree.ElementTree import Element, SubElement, tostring

import structlog

logger = structlog.get_logger()


class IMDSeverity(str, Enum):
    """IMD color-coded severity classification."""

    GREEN = "green"
    YELLOW = "yellow"
    ORANGE = "orange"
    RED = "red"


class CAPSeverity(str, Enum):
    """CAP v1.2 severity values."""

    MINOR = "Minor"
    MODERATE = "Moderate"
    SEVERE = "Severe"
    EXTREME = "Extreme"


class CAPUrgency(str, Enum):
    IMMEDIATE = "Immediate"
    EXPECTED = "Expected"
    FUTURE = "Future"
    PAST = "Past"


class CAPCertainty(str, Enum):
    OBSERVED = "Observed"
    LIKELY = "Likely"
    POSSIBLE = "Possible"
    UNLIKELY = "Unlikely"


# Flood depth thresholds for IMD severity classification
DEPTH_THRESHOLDS = {
    IMDSeverity.GREEN: (0.0, 0.05),    # < 5cm
    IMDSeverity.YELLOW: (0.05, 0.15),  # 5-15cm
    IMDSeverity.ORANGE: (0.15, 0.30),  # 15-30cm
    IMDSeverity.RED: (0.30, float("inf")),  # > 30cm
}

# IMD rainfall thresholds (mm/day)
RAINFALL_THRESHOLDS = {
    IMDSeverity.GREEN: (0, 15.5),       # No rain to light rain
    IMDSeverity.YELLOW: (15.5, 64.4),   # Moderate to heavy rain
    IMDSeverity.ORANGE: (64.4, 115.5),  # Very heavy rain
    IMDSeverity.RED: (115.5, float("inf")),  # Extremely heavy rain
}

# Mapping IMD → CAP severity
IMD_TO_CAP_SEVERITY = {
    IMDSeverity.GREEN: CAPSeverity.MINOR,
    IMDSeverity.YELLOW: CAPSeverity.MODERATE,
    IMDSeverity.ORANGE: CAPSeverity.SEVERE,
    IMDSeverity.RED: CAPSeverity.EXTREME,
}

IMD_TO_CAP_URGENCY = {
    IMDSeverity.GREEN: CAPUrgency.FUTURE,
    IMDSeverity.YELLOW: CAPUrgency.EXPECTED,
    IMDSeverity.ORANGE: CAPUrgency.EXPECTED,
    IMDSeverity.RED: CAPUrgency.IMMEDIATE,
}


def classify_severity_by_depth(max_depth_m: float) -> IMDSeverity:
    """Classify flood severity by maximum water depth.

    Args:
        max_depth_m: Maximum flood depth in metres

    Returns:
        IMD color-coded severity
    """
    for severity, (low, high) in DEPTH_THRESHOLDS.items():
        if low <= max_depth_m < high:
            return severity
    return IMDSeverity.RED


def classify_severity_by_rainfall(rainfall_mm_day: float) -> IMDSeverity:
    """Classify severity by daily rainfall amount (IMD standards)."""
    for severity, (low, high) in RAINFALL_THRESHOLDS.items():
        if low <= rainfall_mm_day < high:
            return severity
    return IMDSeverity.RED


def classify_severity_combined(
    max_depth_m: float,
    rainfall_mm_day: float,
    flooded_area_pct: float = 0.0,
) -> IMDSeverity:
    """Combined severity using both depth and rainfall.

    Takes the HIGHER severity of the two metrics.
    """
    severity_order = [IMDSeverity.GREEN, IMDSeverity.YELLOW, IMDSeverity.ORANGE, IMDSeverity.RED]

    depth_sev = classify_severity_by_depth(max_depth_m)
    rain_sev = classify_severity_by_rainfall(rainfall_mm_day)

    depth_idx = severity_order.index(depth_sev)
    rain_idx = severity_order.index(rain_sev)

    # Boost severity if large area is flooded
    area_boost = 0
    if flooded_area_pct > 20:
        area_boost = 1

    combined_idx = min(max(depth_idx, rain_idx) + area_boost, 3)
    return severity_order[combined_idx]


def generate_cap_xml(
    alert_id: Optional[str] = None,
    sender: str = "ufn-system@sih26085.in",
    city_name: str = "Mumbai",
    severity: IMDSeverity = IMDSeverity.YELLOW,
    headline: Optional[str] = None,
    description: Optional[str] = None,
    affected_wards: Optional[list[str]] = None,
    max_depth_m: float = 0.0,
    polygon_coords: Optional[list[tuple[float, float]]] = None,
    issued_at: Optional[datetime] = None,
    expires_hours: float = 6.0,
) -> str:
    """Generate CAP v1.2 compliant XML alert.

    Follows ITU-T X.1303 / OASIS CAP v1.2 specification.

    Args:
        alert_id: Unique alert identifier (auto-generated if None)
        sender: Alert issuing organization
        city_name: Affected city
        severity: IMD color-coded severity
        headline: Alert headline (auto-generated if None)
        description: Alert description (auto-generated if None)
        affected_wards: List of affected ward names
        max_depth_m: Maximum predicted flood depth
        polygon_coords: Alert area polygon as (lat, lon) pairs
        issued_at: Alert issue time (default: now)
        expires_hours: Hours until alert expires

    Returns:
        CAP v1.2 XML string
    """
    if alert_id is None:
        alert_id = f"urn:ufn:alert:{uuid4().hex[:12]}"
    if issued_at is None:
        issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(hours=expires_hours)

    cap_severity = IMD_TO_CAP_SEVERITY[severity]
    cap_urgency = IMD_TO_CAP_URGENCY[severity]

    if headline is None:
        headline = f"{severity.value.upper()} Flood Alert — {city_name}"
    if description is None:
        ward_text = f" in wards: {', '.join(affected_wards)}" if affected_wards else ""
        description = (
            f"Urban flood alert for {city_name}{ward_text}. "
            f"Maximum predicted water depth: {max_depth_m:.2f}m. "
            f"Severity: {severity.value.upper()} (IMD classification)."
        )

    # Build XML
    ns = "urn:oasis:names:tc:emergency:cap:1.2"
    alert = Element("alert", xmlns=ns)

    SubElement(alert, "identifier").text = alert_id
    SubElement(alert, "sender").text = sender
    SubElement(alert, "sent").text = issued_at.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    SubElement(alert, "status").text = "Actual"
    SubElement(alert, "msgType").text = "Alert"
    SubElement(alert, "scope").text = "Public"

    # Info block
    info = SubElement(alert, "info")
    SubElement(info, "language").text = "en-IN"
    SubElement(info, "category").text = "Met"
    SubElement(info, "event").text = "Urban Flood"
    SubElement(info, "urgency").text = cap_urgency.value
    SubElement(info, "severity").text = cap_severity.value
    SubElement(info, "certainty").text = CAPCertainty.LIKELY.value
    SubElement(info, "headline").text = headline
    SubElement(info, "description").text = description
    SubElement(info, "expires").text = expires_at.strftime("%Y-%m-%dT%H:%M:%S+00:00")

    # Area block
    area = SubElement(info, "area")
    SubElement(area, "areaDesc").text = f"{city_name} flood-affected area"

    if affected_wards:
        for ward in affected_wards:
            geocode = SubElement(area, "geocode")
            SubElement(geocode, "valueName").text = "ward"
            SubElement(geocode, "value").text = ward

    if polygon_coords:
        coords_str = " ".join(f"{lat},{lon}" for lat, lon in polygon_coords)
        SubElement(area, "polygon").text = coords_str

    # Custom parameters
    param_depth = SubElement(info, "parameter")
    SubElement(param_depth, "valueName").text = "max_flood_depth_m"
    SubElement(param_depth, "value").text = f"{max_depth_m:.3f}"

    param_imd = SubElement(info, "parameter")
    SubElement(param_imd, "valueName").text = "imd_severity"
    SubElement(param_imd, "value").text = severity.value

    xml_str = tostring(alert, encoding="unicode", xml_declaration=False)
    xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str

    logger.info(
        "CAP alert generated",
        alert_id=alert_id,
        severity=severity.value,
        city=city_name,
        max_depth_m=max_depth_m,
    )
    return xml_str
