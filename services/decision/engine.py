"""Decision Support Engine for MUFNS.

Generates actionable recommendations for municipal decision-makers
based on real-time flood conditions, ward risk assessments, and
resource availability.

Phase 2F: Decision engine with tiered response protocols.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import structlog

logger = structlog.get_logger()


class ResponseLevel:
    """Municipal emergency response levels (aligned with NDMA guidelines)."""
    NORMAL = "NORMAL"
    ADVISORY = "ADVISORY"        # L1: Awareness and preparation
    ALERT = "ALERT"              # L2: Active monitoring, resource staging
    WARNING = "WARNING"          # L3: Active response, evacuations possible
    EMERGENCY = "EMERGENCY"      # L4: Full emergency response
    CATASTROPHIC = "CATASTROPHIC"  # L5: Multi-agency, state/national escalation


@dataclass
class DecisionRecommendation:
    """A single actionable recommendation."""
    priority: int                    # 1=highest
    category: str                    # evacuation, shelter, rescue, infrastructure, public_comms
    action: str
    target_audience: str             # command_center, field_workers, citizens
    urgency: str = "medium"          # immediate, high, medium, low
    resource_required: str = ""
    estimated_response_time_min: int = 0
    ward_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "priority": self.priority,
            "category": self.category,
            "action": self.action,
            "target_audience": self.target_audience,
            "urgency": self.urgency,
            "resource_required": self.resource_required,
            "estimated_response_time_min": self.estimated_response_time_min,
            "ward_ids": self.ward_ids,
        }


@dataclass
class DecisionPackage:
    """Complete decision support package for command center."""
    response_level: str = ResponseLevel.NORMAL
    computed_at: Optional[datetime] = None
    summary: str = ""
    max_depth_m: float = 0.0
    affected_wards: int = 0
    total_population_exposed: int = 0
    recommendations: list[DecisionRecommendation] = field(default_factory=list)
    resource_allocation: dict = field(default_factory=dict)
    escalation_triggers: list[str] = field(default_factory=list)
    confidence_level: str = "MODERATE"

    def to_dict(self) -> dict:
        return {
            "response_level": self.response_level,
            "computed_at": self.computed_at.isoformat() if self.computed_at else None,
            "summary": self.summary,
            "max_depth_m": round(self.max_depth_m, 3),
            "affected_wards": self.affected_wards,
            "total_population_exposed": self.total_population_exposed,
            "recommendation_count": len(self.recommendations),
            "recommendations": [r.to_dict() for r in self.recommendations],
            "resource_allocation": self.resource_allocation,
            "escalation_triggers": self.escalation_triggers,
            "confidence_level": self.confidence_level,
        }


def determine_response_level(
    max_depth_m: float,
    critical_wards: int = 0,
    high_risk_wards: int = 0,
    rainfall_mmh: float = 0.0,
) -> str:
    """Determine municipal response level based on conditions.

    Aligned with IMD color codes and NDMA disaster management guidelines:
    - GREEN (Normal): No significant flooding
    - YELLOW (Advisory): Localized shallow flooding
    - ORANGE (Alert/Warning): Moderate widespread flooding
    - RED (Emergency): Severe flooding, critical infrastructure at risk
    """
    if max_depth_m >= 2.0 or critical_wards >= 3 or rainfall_mmh >= 100:
        return ResponseLevel.EMERGENCY
    elif max_depth_m >= 1.0 or critical_wards >= 1 or high_risk_wards >= 5 or rainfall_mmh >= 65:
        return ResponseLevel.WARNING
    elif max_depth_m >= 0.3 or high_risk_wards >= 2 or rainfall_mmh >= 35:
        return ResponseLevel.ALERT
    elif max_depth_m >= 0.1 or high_risk_wards >= 1 or rainfall_mmh >= 15:
        return ResponseLevel.ADVISORY
    else:
        return ResponseLevel.NORMAL


def generate_decision_package(
    ward_risks: list,  # list of WardRisk objects
    max_depth_m: float = 0.0,
    rainfall_mmh: float = 0.0,
    confidence_level: str = "MODERATE",
) -> DecisionPackage:
    """Generate a complete decision support package.

    Takes ward risk assessments and current conditions to produce
    actionable recommendations for the command center.
    """
    now = datetime.now(timezone.utc)

    # Count ward risk levels
    critical_wards = [w for w in ward_risks if w.risk_level == "CRITICAL"]
    high_wards = [w for w in ward_risks if w.risk_level == "HIGH"]
    moderate_wards = [w for w in ward_risks if w.risk_level == "MODERATE"]
    affected_wards = len(critical_wards) + len(high_wards) + len(moderate_wards)

    # Determine response level
    response_level = determine_response_level(
        max_depth_m=max_depth_m,
        critical_wards=len(critical_wards),
        high_risk_wards=len(high_wards),
        rainfall_mmh=rainfall_mmh,
    )

    total_pop = sum(getattr(w, "population_exposed", 0) for w in ward_risks)

    pkg = DecisionPackage(
        response_level=response_level,
        computed_at=now,
        max_depth_m=max_depth_m,
        affected_wards=affected_wards,
        total_population_exposed=total_pop,
        confidence_level=confidence_level,
    )

    # Generate recommendations based on response level
    priority = 1

    if response_level == ResponseLevel.EMERGENCY:
        pkg.summary = (
            f"EMERGENCY: Severe flooding detected. {len(critical_wards)} wards at CRITICAL risk. "
            f"Maximum depth: {max_depth_m:.1f}m. Immediate multi-agency response required."
        )
        pkg.recommendations.extend([
            DecisionRecommendation(
                priority=priority,
                category="evacuation",
                action="Initiate mandatory evacuation of low-lying areas in critical wards",
                target_audience="command_center",
                urgency="immediate",
                resource_required="NDRF teams, police, boats",
                estimated_response_time_min=15,
                ward_ids=[w.ward_id for w in critical_wards],
            ),
            DecisionRecommendation(
                priority=priority + 1,
                category="shelter",
                action="Open all emergency shelters and relief camps in affected areas",
                target_audience="command_center",
                urgency="immediate",
                resource_required="BMC shelter management team",
                estimated_response_time_min=30,
            ),
            DecisionRecommendation(
                priority=priority + 2,
                category="infrastructure",
                action="Activate all pumping stations at maximum capacity",
                target_audience="field_workers",
                urgency="immediate",
                resource_required="Storm water dept operators",
                estimated_response_time_min=10,
            ),
            DecisionRecommendation(
                priority=priority + 3,
                category="public_comms",
                action="Issue emergency alert via CAP XML to all registered citizens",
                target_audience="command_center",
                urgency="immediate",
                resource_required="Public communication team",
                estimated_response_time_min=5,
            ),
            DecisionRecommendation(
                priority=priority + 4,
                category="rescue",
                action="Deploy rescue boats and NDRF teams to flooded wards",
                target_audience="field_workers",
                urgency="immediate",
                resource_required="NDRF, fire brigade, boats",
                estimated_response_time_min=30,
                ward_ids=[w.ward_id for w in critical_wards],
            ),
        ])
        pkg.escalation_triggers = [
            "Depth exceeds 3m in any ward",
            "Loss of communication with field teams",
            "Power grid failure in 3+ wards",
            "Hospital inundation reported",
        ]

    elif response_level == ResponseLevel.WARNING:
        pkg.summary = (
            f"WARNING: Moderate flooding in progress. {len(critical_wards)} critical, "
            f"{len(high_wards)} high-risk wards. Max depth: {max_depth_m:.1f}m."
        )
        pkg.recommendations.extend([
            DecisionRecommendation(
                priority=priority,
                category="evacuation",
                action="Issue voluntary evacuation advisory for flood-prone areas",
                target_audience="command_center",
                urgency="high",
                resource_required="Local police, ward officers",
                estimated_response_time_min=30,
                ward_ids=[w.ward_id for w in critical_wards + high_wards],
            ),
            DecisionRecommendation(
                priority=priority + 1,
                category="infrastructure",
                action="Activate pumping stations in affected wards",
                target_audience="field_workers",
                urgency="high",
                resource_required="Pump operators",
                estimated_response_time_min=15,
            ),
            DecisionRecommendation(
                priority=priority + 2,
                category="public_comms",
                action="Send flood warning notifications to affected wards",
                target_audience="command_center",
                urgency="high",
                estimated_response_time_min=10,
            ),
        ])
        pkg.escalation_triggers = [
            f"Depth exceeds 2m (currently {max_depth_m:.1f}m)",
            "3+ wards reach CRITICAL level",
            "Rainfall intensity exceeds 100 mm/hr",
        ]

    elif response_level == ResponseLevel.ALERT:
        pkg.summary = (
            f"ALERT: Rising water levels. {len(high_wards)} high-risk wards. "
            f"Max depth: {max_depth_m:.1f}m. Active monitoring and staging recommended."
        )
        pkg.recommendations.extend([
            DecisionRecommendation(
                priority=priority,
                category="infrastructure",
                action="Pre-position pumping equipment at known hotspots",
                target_audience="field_workers",
                urgency="medium",
                estimated_response_time_min=45,
            ),
            DecisionRecommendation(
                priority=priority + 1,
                category="public_comms",
                action="Issue weather advisory and flood preparedness reminders",
                target_audience="command_center",
                urgency="medium",
                estimated_response_time_min=15,
            ),
        ])
        pkg.escalation_triggers = [
            f"Depth exceeds 1.0m (currently {max_depth_m:.1f}m)",
            "Rainfall rate exceeds 65 mm/hr",
            "Any ward reaches CRITICAL risk",
        ]

    elif response_level == ResponseLevel.ADVISORY:
        pkg.summary = (
            f"ADVISORY: Light flooding possible. {affected_wards} wards under watch. "
            f"Max predicted depth: {max_depth_m:.1f}m."
        )
        pkg.recommendations.append(
            DecisionRecommendation(
                priority=1,
                category="public_comms",
                action="Post rainfall advisory on citizen dashboard",
                target_audience="command_center",
                urgency="low",
                estimated_response_time_min=10,
            ),
        )
        pkg.escalation_triggers = [
            f"Depth exceeds 0.3m (currently {max_depth_m:.1f}m)",
            "Rainfall rate exceeds 35 mm/hr",
        ]

    else:
        pkg.summary = "NORMAL: No significant flooding detected. All systems nominal."
        pkg.escalation_triggers = [
            "Rainfall exceeds 15 mm/hr",
            "High tide exceeds 4.0m CD",
        ]

    # Resource allocation summary
    pkg.resource_allocation = {
        "pumping_stations": "full_capacity" if response_level in (ResponseLevel.EMERGENCY, ResponseLevel.WARNING) else "standby",
        "rescue_teams": "deployed" if response_level == ResponseLevel.EMERGENCY else "staged" if response_level == ResponseLevel.WARNING else "base",
        "shelters": "open" if response_level in (ResponseLevel.EMERGENCY, ResponseLevel.WARNING) else "standby",
        "ndrf": "activated" if response_level == ResponseLevel.EMERGENCY else "notified" if response_level == ResponseLevel.WARNING else "not_required",
    }

    logger.info(
        "Decision package generated",
        response_level=response_level,
        recommendations=len(pkg.recommendations),
        affected_wards=affected_wards,
    )

    return pkg
