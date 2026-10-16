"""Alert Threshold Configuration and Severity Classifiers.

Defines thresholds aligned with National Disaster Management Authority (NDMA),
India Meteorological Department (IMD) color codes, and Municipal Corporation
of Greater Mumbai (MCGM) disaster management operating procedures.

Phase 2F-2: Configurable alert thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any


class AlertSeverity(str, Enum):
    """Standardized alert severity aligned with IMD color-coding."""
    INFO = "INFO"          # Green - No warning
    WATCH = "WATCH"        # Yellow - Be updated
    WARNING = "WARNING"    # Orange - Be prepared
    EMERGENCY = "EMERGENCY"# Red - Take action


class FloodDepthThreshold(float, Enum):
    """Water depth thresholds (meters) for urban inundation."""
    ADVISORY = 0.10        # 10 cm - Minor street ponding
    WATCH = 0.15           # 15 cm - Curb overtopping, pedestrian disruption
    WARNING = 0.30         # 30 cm - Vehicles stalled, low-floor homes threatened
    EMERGENCY = 0.50       # 50 cm - Major roads cut off, power equipment risk
    CATASTROPHIC = 1.00    # 100 cm - Evacuation mandatory, danger to life


@dataclass
class AlertThresholdConfig:
    """Configurable system thresholds for alert generation and escalation."""
    # Water depth thresholds (m)
    depth_watch_m: float = 0.15
    depth_warning_m: float = 0.30
    depth_emergency_m: float = 0.50
    depth_catastrophic_m: float = 1.00

    # Rate of depth rise for flash flooding (m per 30 minutes)
    flash_flood_rate_m_per_30min: float = 0.15

    # Rainfall rate thresholds (mm/h)
    rain_heavy_mmh: float = 30.0       # IMD Heavy Rain
    rain_very_heavy_mmh: float = 65.0  # IMD Very Heavy Rain
    rain_extreme_mmh: float = 115.0    # IMD Extremely Heavy Rain

    # Exposure escalation thresholds
    population_emergency_count: int = 15_000
    critical_infra_emergency_count: int = 2

    # Tidal compounding threshold (m Chart Datum)
    high_tide_lock_threshold_cd: float = 4.45  # MHWS benchmark

    def evaluate_severity(
        self,
        max_depth_m: float,
        rainfall_rate_mmh: float = 0.0,
        exposed_population: int = 0,
        critical_infra_count: int = 0,
        tide_height_cd: float = 0.0,
    ) -> AlertSeverity:
        """Evaluate composite alert severity based on physical and exposure metrics."""
        # 1. Base evaluation from water depth
        if max_depth_m >= self.depth_emergency_m:
            severity = AlertSeverity.EMERGENCY
        elif max_depth_m >= self.depth_warning_m:
            severity = AlertSeverity.WARNING
        elif max_depth_m >= self.depth_watch_m:
            severity = AlertSeverity.WATCH
        else:
            severity = AlertSeverity.INFO

        # 2. Exposure escalations
        if exposed_population >= self.population_emergency_count or critical_infra_count >= self.critical_infra_emergency_count:
            if severity == AlertSeverity.WARNING:
                severity = AlertSeverity.EMERGENCY

        # 3. Heavy rain escalation if approaching threshold
        if rainfall_rate_mmh >= self.rain_extreme_mmh:
            if severity in (AlertSeverity.WATCH, AlertSeverity.WARNING):
                severity = AlertSeverity.EMERGENCY
        elif rainfall_rate_mmh >= self.rain_very_heavy_mmh:
            if severity == AlertSeverity.WATCH:
                severity = AlertSeverity.WARNING

        # 4. Tidal compound hazard escalation
        if tide_height_cd >= self.high_tide_lock_threshold_cd:
            if severity == AlertSeverity.WATCH:
                severity = AlertSeverity.WARNING
            elif severity == AlertSeverity.WARNING and max_depth_m >= 0.40:
                severity = AlertSeverity.EMERGENCY

        return severity


DEFAULT_THRESHOLDS = AlertThresholdConfig()
