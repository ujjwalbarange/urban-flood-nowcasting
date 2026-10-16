"""Stage 4: Rainfall Validation Engine.

Compares satellite rainfall estimates against ground gauge observations.
Calculates standard verification metrics per event window:
- Bias (multiplicative)
- MAE (Mean Absolute Error)
- RMSE (Root Mean Square Error)
- Correlation (Pearson's r)
- Peak rainfall difference
- Peak timing error
- Cumulative rainfall difference

Does NOT hide poor performance. The purpose is to know which rainfall
forcing is actually useful for flood simulation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, List, Optional

import numpy as np
import structlog

logger = structlog.get_logger()


@dataclass
class RainfallValidationResult:
    """Validation metrics for a satellite product vs ground truth."""

    product: str                        # e.g., "HEM", "IMC", "GPM", "GPM_HEM_blend"
    event_name: str                     # e.g., "July 8 2024 Mumbai Cloudburst"
    start_time: str
    end_time: str

    # Paired observations
    gauge_records: int = 0
    satellite_records: int = 0
    matched_pairs: int = 0

    # Standard metrics
    bias: Optional[float] = None             # multiplicative: mean(sat) / mean(gauge)
    mae_mmh: Optional[float] = None          # Mean Absolute Error (mm/hr)
    rmse_mmh: Optional[float] = None         # Root Mean Square Error (mm/hr)
    correlation: Optional[float] = None      # Pearson's r

    # Peak analysis
    gauge_peak_mmh: float = 0.0
    satellite_peak_mmh: float = 0.0
    peak_difference_mmh: float = 0.0         # sat_peak - gauge_peak
    peak_timing_error_min: Optional[float] = None  # minutes between peaks

    # Accumulation
    gauge_cumulative_mm: float = 0.0
    satellite_cumulative_mm: float = 0.0
    cumulative_difference_mm: float = 0.0
    cumulative_difference_pct: float = 0.0

    # Quality assessment
    quality_grade: str = "unknown"  # A/B/C/D/F based on metrics
    limitations: List[str] = field(default_factory=list)


def compute_validation_metrics(
    gauge_ts: List[dict],
    satellite_ts: List[dict],
    product: str,
    event_name: str,
    start_time: str,
    end_time: str,
    temporal_tolerance_min: int = 30,
) -> RainfallValidationResult:
    """Compute validation metrics between gauge and satellite timeseries.

    Args:
        gauge_ts: List of {"time": datetime, "rate_mmh": float, "station": str}
        satellite_ts: List of {"time": datetime/str, "rate_mmh": float}
        product: Name of the satellite product being validated
        event_name: Human-readable event name
        temporal_tolerance_min: Max minutes difference for timestamp pairing
    """
    result = RainfallValidationResult(
        product=product,
        event_name=event_name,
        start_time=start_time,
        end_time=end_time,
        gauge_records=len(gauge_ts),
        satellite_records=len(satellite_ts),
    )

    if not gauge_ts or not satellite_ts:
        result.limitations.append("Insufficient data for validation")
        result.quality_grade = "F"
        return result

    # Parse timestamps
    tolerance = timedelta(minutes=temporal_tolerance_min)

    def parse_time(t):
        if isinstance(t, datetime):
            return t
        try:
            return datetime.fromisoformat(str(t))
        except (ValueError, TypeError):
            return None

    # Build paired observations
    gauge_rates = []
    sat_rates = []
    gauge_times_paired = []
    sat_times_paired = []

    for g in gauge_ts:
        g_time = parse_time(g.get("time"))
        g_rate = float(g.get("rate_mmh", 0.0))
        if g_time is None:
            continue

        # Find closest satellite observation
        best_match = None
        best_delta = tolerance
        for s in satellite_ts:
            s_time = parse_time(s.get("time"))
            if s_time is None:
                continue
            delta = abs(g_time - s_time)
            if delta <= best_delta:
                best_delta = delta
                best_match = s

        if best_match is not None:
            s_rate = float(best_match.get("rate_mmh", 0.0))
            gauge_rates.append(g_rate)
            sat_rates.append(s_rate)
            gauge_times_paired.append(g_time)
            s_time_matched = parse_time(best_match.get("time"))
            sat_times_paired.append(s_time_matched)

    result.matched_pairs = len(gauge_rates)

    if result.matched_pairs < 2:
        result.limitations.append(f"Only {result.matched_pairs} matched pairs (need >= 2)")
        result.quality_grade = "F"
        return result

    gauge_arr = np.array(gauge_rates, dtype=np.float64)
    sat_arr = np.array(sat_rates, dtype=np.float64)

    # Bias (multiplicative)
    gauge_mean = np.mean(gauge_arr)
    sat_mean = np.mean(sat_arr)
    if gauge_mean > 0.01:
        result.bias = round(float(sat_mean / gauge_mean), 4)
    else:
        result.bias = None
        result.limitations.append("Gauge mean near zero, bias undefined")

    # MAE
    result.mae_mmh = round(float(np.mean(np.abs(sat_arr - gauge_arr))), 4)

    # RMSE
    result.rmse_mmh = round(float(np.sqrt(np.mean((sat_arr - gauge_arr) ** 2))), 4)

    # Correlation
    if np.std(gauge_arr) > 0.001 and np.std(sat_arr) > 0.001:
        corr = np.corrcoef(gauge_arr, sat_arr)[0, 1]
        result.correlation = round(float(corr), 4) if not np.isnan(corr) else None
    else:
        result.correlation = None
        result.limitations.append("Insufficient variance for correlation")

    # Peak analysis
    result.gauge_peak_mmh = round(float(np.max(gauge_arr)), 2)
    result.satellite_peak_mmh = round(float(np.max(sat_arr)), 2)
    result.peak_difference_mmh = round(result.satellite_peak_mmh - result.gauge_peak_mmh, 2)

    # Peak timing error
    gauge_peak_idx = int(np.argmax(gauge_arr))
    sat_peak_idx = int(np.argmax(sat_arr))
    if gauge_peak_idx < len(gauge_times_paired) and sat_peak_idx < len(sat_times_paired):
        g_peak_time = gauge_times_paired[gauge_peak_idx]
        s_peak_time = sat_times_paired[sat_peak_idx]
        if g_peak_time and s_peak_time:
            timing_delta = (s_peak_time - g_peak_time).total_seconds() / 60.0
            result.peak_timing_error_min = round(timing_delta, 1)

    # Cumulative rainfall
    # Assume 30-min intervals for satellite, variable for gauge
    result.satellite_cumulative_mm = round(float(np.sum(sat_arr * 0.5)), 2)  # mm/hr * 0.5hr
    result.gauge_cumulative_mm = round(float(np.sum(gauge_arr * 0.5)), 2)
    result.cumulative_difference_mm = round(
        result.satellite_cumulative_mm - result.gauge_cumulative_mm, 2
    )
    if result.gauge_cumulative_mm > 0.1:
        result.cumulative_difference_pct = round(
            result.cumulative_difference_mm / result.gauge_cumulative_mm * 100, 1
        )

    # Quality grade
    result.quality_grade = _assign_grade(result)

    logger.info(
        "Rainfall validation computed",
        product=product,
        event=event_name,
        pairs=result.matched_pairs,
        bias=result.bias,
        mae=result.mae_mmh,
        rmse=result.rmse_mmh,
        corr=result.correlation,
        grade=result.quality_grade,
    )

    return result


def _assign_grade(r: RainfallValidationResult) -> str:
    """Assign a quality grade based on validation metrics.

    A: Excellent — bias 0.8-1.2, correlation > 0.8, RMSE < 5
    B: Good — bias 0.6-1.5, correlation > 0.6, RMSE < 10
    C: Fair — bias 0.4-2.0, correlation > 0.4, RMSE < 20
    D: Poor — worse than C but some data
    F: Fail — insufficient data or extremely poor
    """
    if r.matched_pairs < 3:
        return "F"

    bias_ok = r.bias is not None and 0.8 <= r.bias <= 1.2
    bias_fair = r.bias is not None and 0.4 <= r.bias <= 2.0
    corr_high = r.correlation is not None and r.correlation > 0.8
    corr_med = r.correlation is not None and r.correlation > 0.6
    corr_low = r.correlation is not None and r.correlation > 0.4
    rmse_low = r.rmse_mmh is not None and r.rmse_mmh < 5.0
    rmse_med = r.rmse_mmh is not None and r.rmse_mmh < 10.0
    rmse_high = r.rmse_mmh is not None and r.rmse_mmh < 20.0

    if bias_ok and corr_high and rmse_low:
        return "A"
    elif (r.bias is not None and 0.6 <= r.bias <= 1.5) and corr_med and rmse_med:
        return "B"
    elif bias_fair and corr_low and rmse_high:
        return "C"
    elif r.matched_pairs >= 3:
        return "D"
    else:
        return "F"


def generate_validation_report(results: List[RainfallValidationResult]) -> dict:
    """Generate a summary report comparing multiple products for the same event."""
    report = {
        "event": results[0].event_name if results else "unknown",
        "products_compared": len(results),
        "comparisons": [],
        "best_product": None,
        "recommendation": "",
    }

    best_corr = -1.0
    best_product = None

    for r in results:
        entry = {
            "product": r.product,
            "matched_pairs": r.matched_pairs,
            "bias": r.bias,
            "mae_mmh": r.mae_mmh,
            "rmse_mmh": r.rmse_mmh,
            "correlation": r.correlation,
            "peak_difference_mmh": r.peak_difference_mmh,
            "peak_timing_error_min": r.peak_timing_error_min,
            "cumulative_difference_pct": r.cumulative_difference_pct,
            "quality_grade": r.quality_grade,
            "limitations": r.limitations,
        }
        report["comparisons"].append(entry)

        if r.correlation is not None and r.correlation > best_corr:
            best_corr = r.correlation
            best_product = r.product

    report["best_product"] = best_product
    if best_product:
        report["recommendation"] = (
            f"For this event, {best_product} shows the highest correlation with ground observations. "
            f"However, all satellite estimates should be used with documented uncertainty."
        )

    return report
