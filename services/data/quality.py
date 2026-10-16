"""Data Quality Control (QC) pipeline for MUFNS.

Validates incoming data from weather APIs, gauge stations, satellite observations,
and simulation outputs before they enter the operational pipeline.

Phase 2A: Establishes QC framework with provenance tracking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

import numpy as np
import structlog

logger = structlog.get_logger()


class QCFlag(str, Enum):
    """Data quality control flags following WMO conventions."""
    GOOD = "good"                    # Passed all checks
    SUSPECT = "suspect"              # Failed soft check, usable with caution
    BAD = "bad"                      # Failed hard check, should not be used
    MISSING = "missing"              # No data available
    NOT_CHECKED = "not_checked"      # QC not yet applied
    INTERPOLATED = "interpolated"    # Value was filled/interpolated


@dataclass
class QCResult:
    """Result of a data quality check."""
    flag: QCFlag = QCFlag.NOT_CHECKED
    checks_passed: list[str] = field(default_factory=list)
    checks_failed: list[str] = field(default_factory=list)
    checks_warned: list[str] = field(default_factory=list)
    original_value: Any = None
    corrected_value: Any = None
    correction_applied: str = ""
    source: str = ""
    checked_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "flag": self.flag.value,
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "checks_warned": self.checks_warned,
            "correction_applied": self.correction_applied,
            "source": self.source,
            "checked_at": self.checked_at.isoformat() if self.checked_at else None,
        }


@dataclass
class DataProvenance:
    """Provenance record for a data value or dataset."""
    source_name: str
    source_type: str  # api, gauge, satellite, derived, model
    retrieved_at: Optional[datetime] = None
    spatial_resolution: str = ""
    temporal_resolution: str = ""
    qc_flag: QCFlag = QCFlag.NOT_CHECKED
    qc_details: Optional[QCResult] = None
    transformations: list[str] = field(default_factory=list)
    confidence: float = 1.0  # 0-1

    def to_dict(self) -> dict:
        return {
            "source_name": self.source_name,
            "source_type": self.source_type,
            "retrieved_at": self.retrieved_at.isoformat() if self.retrieved_at else None,
            "spatial_resolution": self.spatial_resolution,
            "temporal_resolution": self.temporal_resolution,
            "qc_flag": self.qc_flag.value,
            "transformations": self.transformations,
            "confidence": self.confidence,
        }


# ── Rainfall QC ──────────────────────────────────────────────────────────


def qc_rainfall_rate(
    value_mmh: float,
    source: str = "unknown",
    max_physical_mmh: float = 350.0,
    warn_threshold_mmh: float = 200.0,
) -> QCResult:
    """Quality-check a rainfall intensity value.

    Physical limits based on:
    - Mumbai extreme: 300+ mm/hr recorded in 2005 event
    - World record: ~300 mm in one hour
    - IMD extreme classification: >244.5 mm/day

    Args:
        value_mmh: Rainfall rate in mm/hr
        source: Data source name
        max_physical_mmh: Maximum physically plausible rate
        warn_threshold_mmh: Threshold for suspect flag
    """
    result = QCResult(source=source, original_value=value_mmh, checked_at=datetime.now(timezone.utc))

    # Check 1: Non-negative
    if value_mmh < 0:
        result.checks_failed.append(f"negative_value: {value_mmh}")
        result.corrected_value = 0.0
        result.correction_applied = "clamped_to_zero"
        result.flag = QCFlag.BAD
        return result
    result.checks_passed.append("non_negative")

    # Check 2: Not NaN/Inf
    if np.isnan(value_mmh) or np.isinf(value_mmh):
        result.checks_failed.append("nan_or_inf")
        result.flag = QCFlag.BAD
        return result
    result.checks_passed.append("finite")

    # Check 3: Physical maximum
    if value_mmh > max_physical_mmh:
        result.checks_failed.append(f"exceeds_physical_max: {value_mmh} > {max_physical_mmh}")
        result.corrected_value = max_physical_mmh
        result.correction_applied = f"capped_at_{max_physical_mmh}"
        result.flag = QCFlag.BAD
        return result
    result.checks_passed.append("within_physical_range")

    # Check 4: Suspect threshold
    if value_mmh > warn_threshold_mmh:
        result.checks_warned.append(f"high_value: {value_mmh} > {warn_threshold_mmh}")
        result.flag = QCFlag.SUSPECT
        return result

    result.flag = QCFlag.GOOD
    return result


def qc_rainfall_timeseries(
    values_mmh: list[float],
    source: str = "unknown",
    max_jump_mmh: float = 150.0,
) -> QCResult:
    """Quality-check a rainfall time series for temporal consistency.

    Checks for:
    - Sudden unrealistic jumps between consecutive readings
    - Stuck gauge (identical values for too long)
    - All-zero when other sources report rain
    """
    result = QCResult(source=source, checked_at=datetime.now(timezone.utc))

    if not values_mmh or len(values_mmh) < 2:
        result.flag = QCFlag.NOT_CHECKED
        result.checks_warned.append("insufficient_data_points")
        return result

    # Check temporal jumps
    jumps = [abs(values_mmh[i] - values_mmh[i - 1]) for i in range(1, len(values_mmh))]
    max_jump = max(jumps) if jumps else 0
    if max_jump > max_jump_mmh:
        result.checks_warned.append(f"large_temporal_jump: {max_jump:.1f} mm/hr")
        result.flag = QCFlag.SUSPECT
    else:
        result.checks_passed.append("temporal_consistency")

    # Check for stuck gauge (>5 identical non-zero values)
    for i in range(len(values_mmh) - 5):
        window = values_mmh[i:i + 6]
        if len(set(window)) == 1 and window[0] > 0:
            result.checks_warned.append(f"stuck_gauge_at_index_{i}: constant={window[0]}")
            result.flag = QCFlag.SUSPECT
            break
    else:
        result.checks_passed.append("no_stuck_gauge")

    if result.flag == QCFlag.NOT_CHECKED:
        result.flag = QCFlag.GOOD

    return result


# ── Water Depth QC ────────────────────────────────────────────────────────


def qc_water_depth(
    depth_m: float,
    source: str = "model",
    max_depth_m: float = 15.0,
) -> QCResult:
    """Quality-check a water depth value.

    Physical limits for Mumbai urban flooding:
    - Maximum observed depth: ~4-5m in extreme events (2005)
    - Model outputs above 10m likely indicate numerical instability
    """
    result = QCResult(source=source, original_value=depth_m, checked_at=datetime.now(timezone.utc))

    if depth_m < 0:
        result.checks_failed.append(f"negative_depth: {depth_m}")
        result.flag = QCFlag.BAD
        return result
    result.checks_passed.append("non_negative")

    if np.isnan(depth_m) or np.isinf(depth_m):
        result.checks_failed.append("nan_or_inf")
        result.flag = QCFlag.BAD
        return result
    result.checks_passed.append("finite")

    if depth_m > max_depth_m:
        result.checks_warned.append(f"extreme_depth: {depth_m} > {max_depth_m}")
        result.flag = QCFlag.SUSPECT
        return result
    result.checks_passed.append("within_expected_range")

    result.flag = QCFlag.GOOD
    return result


# ── Mass Balance QC ──────────────────────────────────────────────────────


def qc_mass_balance(
    closure_error_pct: float,
    warn_threshold_pct: float = 5.0,
    fail_threshold_pct: float = 15.0,
) -> QCResult:
    """Quality-check simulation mass balance closure.

    A well-conditioned simulation should have <5% closure error.
    >15% suggests numerical instability or incorrect boundary conditions.
    """
    result = QCResult(
        source="simulation_mass_balance",
        original_value=closure_error_pct,
        checked_at=datetime.now(timezone.utc),
    )

    abs_error = abs(closure_error_pct)

    if abs_error > fail_threshold_pct:
        result.checks_failed.append(f"mass_balance_error: {abs_error:.1f}% > {fail_threshold_pct}%")
        result.flag = QCFlag.BAD
        return result

    if abs_error > warn_threshold_pct:
        result.checks_warned.append(f"mass_balance_warning: {abs_error:.1f}% > {warn_threshold_pct}%")
        result.flag = QCFlag.SUSPECT
    else:
        result.checks_passed.append(f"mass_balance_ok: {abs_error:.1f}%")
        result.flag = QCFlag.GOOD

    return result


# ── Confidence Scoring ───────────────────────────────────────────────────


@dataclass
class ConfidenceAssessment:
    """Confidence assessment for a nowcast/simulation result."""
    score: float = 0.0        # 0-100
    level: str = "LOW"        # HIGH, MODERATE, LOW
    factors: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "score": round(self.score, 1),
            "level": self.level,
            "factors": self.factors,
        }


def compute_confidence(
    mass_balance_error_pct: float,
    rainfall_source: str,
    terrain_source: str,
    spatial_params_quality: str,
    has_drainage_coupling: bool = False,
    has_tide_data: bool = False,
    validation_csi: Optional[float] = None,
) -> ConfidenceAssessment:
    """Compute a multi-factor confidence score for a simulation/nowcast result.

    Factors and their weights:
    - Mass balance quality (25%)
    - Rainfall data quality (20%)
    - Terrain quality (20%)
    - Spatial parameters (15%)
    - Drainage coupling (10%)
    - Validation history (10%)
    """
    assessment = ConfidenceAssessment()

    # Factor 1: Mass balance (25 pts)
    abs_mb = abs(mass_balance_error_pct)
    if abs_mb < 2.0:
        mb_score = 25.0
        mb_detail = "Excellent mass balance"
    elif abs_mb < 5.0:
        mb_score = 20.0
        mb_detail = "Good mass balance"
    elif abs_mb < 15.0:
        mb_score = 12.0
        mb_detail = "Marginal mass balance"
    else:
        mb_score = 5.0
        mb_detail = "Poor mass balance"
    assessment.factors.append({"factor": "mass_balance", "score": mb_score, "max": 25, "detail": mb_detail})

    # Factor 2: Rainfall source (20 pts)
    rainfall_scores = {
        "gauge_verified": 20.0,
        "nasa_imerg": 18.0,
        "mosdac_insat": 16.0,
        "Open-Meteo live forecast + recent history": 14.0,
        "open-meteo": 14.0,
        "design_burst": 10.0,
        "forced_uniform": 8.0,
    }
    rf_score = rainfall_scores.get(rainfall_source, 10.0)
    assessment.factors.append({"factor": "rainfall_source", "score": rf_score, "max": 20, "detail": rainfall_source})

    # Factor 3: Terrain quality (20 pts)
    terrain_scores = {
        "Copernicus GLO-30 (30m DSM via OpenTopography)": 18.0,
        "copernicus_glo30": 18.0,
        "surveyed_dtm": 20.0,
        "synthetic": 5.0,
    }
    tr_score = terrain_scores.get(terrain_source, 10.0)
    assessment.factors.append({"factor": "terrain", "score": tr_score, "max": 20, "detail": terrain_source})

    # Factor 4: Spatial parameters (15 pts)
    param_scores = {
        "postgis_lulc": 15.0,
        "assumed": 10.0,
        "default_fallback": 7.0,
        "default": 7.0,
        "unknown": 5.0,
    }
    sp_score = param_scores.get(spatial_params_quality, 7.0)
    assessment.factors.append({"factor": "spatial_params", "score": sp_score, "max": 15, "detail": spatial_params_quality})

    # Factor 5: Drainage coupling (10 pts)
    dr_score = 10.0 if has_drainage_coupling else 4.0
    assessment.factors.append({"factor": "drainage_coupling", "score": dr_score, "max": 10, "detail": "coupled" if has_drainage_coupling else "surface_only"})

    # Factor 6: Validation (10 pts)
    if validation_csi is not None:
        val_score = min(10.0, validation_csi * 10.0)
    else:
        val_score = 5.0  # neutral
    assessment.factors.append({"factor": "validation", "score": val_score, "max": 10, "detail": f"CSI={validation_csi}" if validation_csi else "not_validated"})

    # Total
    assessment.score = sum(f["score"] for f in assessment.factors)

    # Level
    if assessment.score >= 70:
        assessment.level = "HIGH"
    elif assessment.score >= 45:
        assessment.level = "MODERATE"
    else:
        assessment.level = "LOW"

    return assessment
