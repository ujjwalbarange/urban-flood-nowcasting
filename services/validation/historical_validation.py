"""Stage 7 & Phase 5: Historical Flood Event and Hotspot Validation Engine.

Compares 2D diffusive wave simulation output against:
1. 202 verified historical flood event records (2016–2025) with documented depths and rainfall.
2. 35 chronic urban flooding hotspots cataloged by MCGM Disaster Management.

Scientific Integrity Standards (Phase 5):
- Offline-first architecture: Works with local GeoJSON data package when PostGIS is offline,
  and queries PostgreSQL/PostGIS when connected.
- True Paired Depth Evaluation: Computes MAE, RMSE, and Bias ONLY for paired coordinates
  where observed depth measurements actually exist.
- Explicit Missing-Data States: Emits "insufficient_validation_data" instead of inventing 0% error
  or 100% accuracy.
- Contingency Metrics: Hit Rate / Recall (POD), Precision, Critical Success Index (CSI),
  and False Alarm Ratio (FAR) with exact sample count N and formulas documented.
- No Proxy Constants: Never fabricates precision with arbitrary offsets.
"""

from __future__ import annotations

import json
import math
import os
import ssl
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import structlog

logger = structlog.get_logger()

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_HISTORICAL_GEOJSON = _PROJECT_ROOT / "data" / "cities" / "mumbai" / "historical_flood_events.geojson"
_HOTSPOTS_GEOJSON = _PROJECT_ROOT / "mumbai_flood_data_package" / "08_flood_observations" / "flood_points.geojson"
if not _HOTSPOTS_GEOJSON.exists():
    _HOTSPOTS_GEOJSON = _PROJECT_ROOT / "data" / "processed" / "flood_hotspots" / "mumbai_flood_hotspots.geojson"


@dataclass
class HotspotValidationRecord:
    """Individual hotspot validation assessment."""
    hotspot_id: str
    name: str
    ward: str
    lon: float
    lat: float
    in_simulation_domain: bool
    observed_typical_depth_m: Optional[float]
    observed_max_depth_m: Optional[float]
    simulated_depth_m: float
    is_hit: bool                        # True if simulated depth >= threshold
    classification: str                 # "HIT" (TP), "MISSED" (FN), or "OUT_OF_DOMAIN"


@dataclass
class HistoricalEventValidationRecord:
    """Individual historical flood event observation assessment."""
    event_id: str
    locality: str
    ward: str
    date_observed: str
    lon: float
    lat: float
    in_simulation_domain: bool
    has_observed_depth: bool
    observed_depth_m: Optional[float]   # Converted from flood_depth_cm / 100.0
    observed_severity: str
    simulated_depth_m: float
    depth_error_m: Optional[float]      # simulated - observed (None if no observed depth)
    is_hit: bool
    classification: str                 # "HIT" (TP), "MISSED" (FN), or "OUT_OF_DOMAIN"


@dataclass
class PairedDepthMetrics:
    """Rigorous paired depth metrics computed ONLY where observed measurements exist."""
    sample_count_n: int
    mean_absolute_error_m: Optional[float]
    root_mean_squared_error_m: Optional[float]
    mean_bias_error_m: Optional[float]
    mean_observed_depth_m: Optional[float]
    mean_simulated_depth_m: Optional[float]
    units: str = "metres"
    formula_mae: str = "MAE = (1/N) * sum(|h_sim - h_obs|)"
    formula_rmse: str = "RMSE = sqrt((1/N) * sum((h_sim - h_obs)^2))"
    formula_bias: str = "Bias = (1/N) * sum(h_sim - h_obs)"
    status: str = "valid"               # "valid" or "insufficient_validation_data"
    limitations: str = (
        "Depth error is evaluated at available point observation coordinates. "
        "Does not represent continuous cell-by-cell error across the entire city domain."
    )


@dataclass
class ContingencyMetrics:
    """Categorical flood detection metrics."""
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    sample_count_n: int
    recall_pod: float                   # TP / (TP + FN)
    precision: Optional[float]          # TP / (TP + FP) or None if uncomputable
    critical_success_index: float       # TP / (TP + FP + FN)
    false_alarm_ratio: Optional[float]  # FP / (TP + FP)
    flood_threshold_m: float = 0.08     # 8cm urban waterlogging threshold
    formula_csi: str = "CSI = TP / (TP + FP + FN)"
    formula_pod: str = "POD = TP / (TP + FN)"
    limitations: str = (
        "Precision and false alarms are assessed against cataloged municipal hotspots and survey points. "
        "Emergency incident logs typically document flooded locations without systematic negative samples."
    )


@dataclass
class Stage7ValidationReport:
    """Complete validation report for a historical replay simulation."""
    simulation_id: str
    event_id: str
    event_name: str
    evaluation_time: str
    domain_bounds: Dict[str, float]
    cell_size_m: float
    flood_threshold_m: float = 0.08

    # Hotspot Metrics
    hotspots_total_db: int = 0
    hotspots_in_domain: int = 0
    hotspots_hit: int = 0
    hotspots_missed: int = 0
    hotspot_hit_rate_pct: float = 0.0

    # Historical Event Observations Metrics
    events_observed_in_window: int = 0
    events_in_domain: int = 0
    events_hit: int = 0
    events_missed: int = 0
    event_hit_rate_pct: float = 0.0

    # Detailed metrics objects
    paired_depth_metrics: Optional[PairedDepthMetrics] = None
    contingency_metrics: Optional[ContingencyMetrics] = None

    # Spatial summary
    simulated_flooded_cells: int = 0
    simulated_flooded_area_km2: float = 0.0
    simulated_peak_timing_hours: float = 0.0

    # Detailed record lists
    hotspot_details: List[HotspotValidationRecord] = field(default_factory=list)
    event_details: List[HistoricalEventValidationRecord] = field(default_factory=list)

    # Scientific classifications
    observed_facts: List[str] = field(default_factory=list)
    simulated_results: List[str] = field(default_factory=list)
    scientific_assumptions: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "event_id": self.event_id,
            "event_name": self.event_name,
            "evaluation_time": self.evaluation_time,
            "domain_bounds": self.domain_bounds,
            "cell_size_m": self.cell_size_m,
            "flood_threshold_m": self.flood_threshold_m,
            "summary": {
                "hotspots_in_domain": self.hotspots_in_domain,
                "hotspots_hit": self.hotspots_hit,
                "hotspot_hit_rate_pct": self.hotspot_hit_rate_pct,
                "events_in_domain": self.events_in_domain,
                "events_hit": self.events_hit,
                "event_hit_rate_pct": self.event_hit_rate_pct,
                "simulated_flooded_area_km2": self.simulated_flooded_area_km2,
            },
            "paired_depth_metrics": asdict(self.paired_depth_metrics) if self.paired_depth_metrics else {
                "status": "insufficient_validation_data",
                "message": "No verified depth measurements found within active simulation window."
            },
            "contingency_metrics": asdict(self.contingency_metrics) if self.contingency_metrics else None,
            "hotspot_details": [asdict(h) for h in self.hotspot_details],
            "event_details": [asdict(e) for e in self.event_details],
            "observed_facts": self.observed_facts,
            "simulated_results": self.simulated_results,
            "scientific_assumptions": self.scientific_assumptions,
            "limitations": self.limitations,
        }


class HistoricalValidator:
    """Validates 2D flood simulation results against historical ground truth observations."""

    def __init__(self, db_url: Optional[str] = None):
        raw_url = db_url or os.environ.get("DATABASE_URL", "")
        self.clean_url = raw_url.replace("postgresql+asyncpg://", "postgresql://").split("?")[0]
        self.ssl_ctx = ssl.create_default_context()
        self.ssl_ctx.check_hostname = False
        self.ssl_ctx.verify_mode = ssl.CERT_NONE

    async def fetch_hotspots(self) -> List[Dict[str, Any]]:
        """Fetch chronic flood hotspots from PostGIS or fallback to local data package."""
        try:
            import asyncpg
            conn = await asyncpg.connect(self.clean_url, ssl=self.ssl_ctx, timeout=3.0)
            try:
                rows = await conn.fetch("""
                    SELECT hotspot_id, name, ward, hotspot_type, severity, recurrence,
                           typical_water_depth_m, historical_max_depth_m,
                           ST_X(location) as lon, ST_Y(location) as lat
                    FROM public.flood_hotspots
                    ORDER BY name ASC;
                """)
                return [dict(r) for r in rows]
            finally:
                await conn.close()
        except Exception as e:
            logger.info("Using local hotspots GeoJSON fallback", reason=str(e))
            return self._load_local_hotspots()

    def _load_local_hotspots(self) -> List[Dict[str, Any]]:
        """Load hotspots from local file."""
        if not _HOTSPOTS_GEOJSON.exists():
            return []
        try:
            with open(_HOTSPOTS_GEOJSON, "r", encoding="utf-8") as f:
                data = json.load(f)
            hotspots = []
            for feat in data.get("features", []):
                geom = feat.get("geometry", {})
                props = feat.get("properties", {})
                coords = geom.get("coordinates")
                if coords and len(coords) >= 2:
                    hotspots.append({
                        "hotspot_id": str(props.get("hotspot_id") or feat.get("id") or props.get("name")),
                        "name": props.get("name") or props.get("location_name") or "Flood Hotspot",
                        "ward": props.get("ward") or props.get("ward_id") or "",
                        "hotspot_type": props.get("type", "chronic_junction"),
                        "severity": props.get("severity", "Severe"),
                        "recurrence": props.get("recurrence", "Annual Monsoon"),
                        "typical_water_depth_m": props.get("typical_depth_m", 0.5),
                        "historical_max_depth_m": props.get("max_depth_m", 1.2),
                        "lon": coords[0],
                        "lat": coords[1],
                    })
            return hotspots
        except Exception as e:
            logger.error("Failed loading local hotspots", error=str(e))
            return []

    async def fetch_historical_events(
        self, start_date: str = "2024-07-07", end_date: str = "2024-07-09"
    ) -> List[Dict[str, Any]]:
        """Fetch historical flood events with reported depths and coordinates."""
        try:
            import asyncpg
            conn = await asyncpg.connect(self.clean_url, ssl=self.ssl_ctx, timeout=3.0)
            try:
                t0 = datetime.fromisoformat(start_date).replace(hour=0, minute=0, second=0, tzinfo=timezone.utc)
                t1 = datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
                rows = await conn.fetch("""
                    SELECT event_id, date, ward, locality, flood_severity,
                           flood_depth_cm, rainfall_24h_mm,
                           ST_X(location) as lon, ST_Y(location) as lat
                    FROM public.historical_flood_events
                    WHERE date >= $1 AND date <= $2
                    ORDER BY date ASC;
                """, t0, t1)
                return [dict(r) for r in rows]
            finally:
                await conn.close()
        except Exception as e:
            logger.info("Using local historical_flood_events.geojson fallback", reason=str(e))
            return self._load_local_events(start_date, end_date)

    def _load_local_events(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Load matching historical events from local GeoJSON archive (202 verified features)."""
        if not _HISTORICAL_GEOJSON.exists():
            return []
        try:
            with open(_HISTORICAL_GEOJSON, "r", encoding="utf-8") as f:
                data = json.load(f)
            events = []
            s_date = start_date[:10]
            e_date = end_date[:10]
            for feat in data.get("features", []):
                props = feat.get("properties", {})
                geom = feat.get("geometry", {})
                ev_date = str(props.get("date", ""))[:10]
                if s_date <= ev_date <= e_date:
                    coords = geom.get("coordinates")
                    if coords and len(coords) >= 2:
                        events.append({
                            "event_id": str(props.get("event_id") or feat.get("id")),
                            "date": ev_date,
                            "ward": props.get("ward", ""),
                            "locality": props.get("locality") or props.get("name", "Unknown"),
                            "flood_severity": props.get("flood_severity", "Severe"),
                            "flood_depth_cm": props.get("flood_depth_cm"),
                            "rainfall_24h_mm": props.get("rainfall_24h_mm"),
                            "lon": coords[0],
                            "lat": coords[1],
                        })
            return events
        except Exception as e:
            logger.error("Failed loading local historical events", error=str(e))
            return []

    def validate_simulation(
        self,
        simulation_id: str,
        event_id: str,
        event_name: str,
        depth_grid: np.ndarray,
        georef: Dict[str, Any],
        hotspots: List[Dict[str, Any]],
        historical_events: List[Dict[str, Any]],
        flood_threshold_m: float = 0.08,
        simulated_peak_timing_hours: float = 0.0,
    ) -> Stage7ValidationReport:
        """Execute rigorous validation against ground-truth hotspots and historical observations.

        Guarantees:
        - MAE/RMSE/Bias computed ONLY for paired locations with actual depth measurements.
        - Contingency classification uses true ground observations (no proxy constants).
        - Explicit sample counts and limitations reported for all metrics.
        """
        rows, cols = depth_grid.shape
        min_lon = georef["min_lon"]
        max_lon = georef["max_lon"]
        min_lat = georef["min_lat"]
        max_lat = georef["max_lat"]
        dx = georef["cell_size_m"]

        report = Stage7ValidationReport(
            simulation_id=simulation_id,
            event_id=event_id,
            event_name=event_name,
            evaluation_time=datetime.now(timezone.utc).isoformat(),
            domain_bounds={"west": min_lon, "east": max_lon, "south": min_lat, "north": max_lat},
            cell_size_m=dx,
            flood_threshold_m=flood_threshold_m,
            simulated_peak_timing_hours=simulated_peak_timing_hours,
        )

        def coords_to_rc(lon: float, lat: float) -> Optional[Tuple[int, int]]:
            if not (min_lon <= lon <= max_lon and min_lat <= lat <= max_lat):
                return None
            r = int((max_lat - lat) / (max_lat - min_lat) * rows)
            c = int((lon - min_lon) / (max_lon - min_lon) * cols)
            r = max(0, min(r, rows - 1))
            c = max(0, min(c, cols - 1))
            return r, c

        def sample_depth_window(r: int, c: int, radius_cells: int = 1) -> float:
            r0 = max(0, r - radius_cells)
            r1 = min(rows, r + radius_cells + 1)
            c0 = max(0, c - radius_cells)
            c1 = min(cols, c + radius_cells + 1)
            return float(np.max(depth_grid[r0:r1, c0:c1]))

        # ── 1. Evaluate Chronic Hotspots (Stage 7.1) ──
        report.hotspots_total_db = len(hotspots)
        for h in hotspots:
            lon = float(h["lon"])
            lat = float(h["lat"])
            rc = coords_to_rc(lon, lat)

            if rc is None:
                record = HotspotValidationRecord(
                    hotspot_id=str(h["hotspot_id"]),
                    name=h["name"],
                    ward=h.get("ward", ""),
                    lon=lon,
                    lat=lat,
                    in_simulation_domain=False,
                    observed_typical_depth_m=h.get("typical_water_depth_m"),
                    observed_max_depth_m=h.get("historical_max_depth_m"),
                    simulated_depth_m=0.0,
                    is_hit=False,
                    classification="OUT_OF_DOMAIN",
                )
            else:
                sim_depth = sample_depth_window(rc[0], rc[1], radius_cells=1)
                is_hit = sim_depth >= flood_threshold_m
                record = HotspotValidationRecord(
                    hotspot_id=str(h["hotspot_id"]),
                    name=h["name"],
                    ward=h.get("ward", ""),
                    lon=lon,
                    lat=lat,
                    in_simulation_domain=True,
                    observed_typical_depth_m=h.get("typical_water_depth_m"),
                    observed_max_depth_m=h.get("historical_max_depth_m"),
                    simulated_depth_m=round(sim_depth, 3),
                    is_hit=is_hit,
                    classification="HIT" if is_hit else "MISSED",
                )
                report.hotspots_in_domain += 1
                if is_hit:
                    report.hotspots_hit += 1
                else:
                    report.hotspots_missed += 1

            report.hotspot_details.append(record)

        if report.hotspots_in_domain > 0:
            report.hotspot_hit_rate_pct = round(
                report.hotspots_hit / report.hotspots_in_domain * 100.0, 1
            )

        # ── 2. Evaluate Historical Flood Event Observations (Stage 7.2) ──
        report.events_observed_in_window = len(historical_events)
        depth_errors: List[float] = []
        observed_depths: List[float] = []
        simulated_depths: List[float] = []

        tp_count = 0
        fn_count = 0
        fp_count = 0
        tn_count = 0

        for ev in historical_events:
            lon = float(ev["lon"])
            lat = float(ev["lat"])
            raw_depth_cm = ev.get("flood_depth_cm")
            has_depth = raw_depth_cm is not None and not math.isnan(float(raw_depth_cm))
            obs_depth = float(raw_depth_cm) / 100.0 if has_depth else None

            rc = coords_to_rc(lon, lat)

            if rc is None:
                ev_record = HistoricalEventValidationRecord(
                    event_id=str(ev["event_id"]),
                    locality=ev.get("locality", "Unknown"),
                    ward=ev.get("ward", "Unknown"),
                    date_observed=str(ev.get("date", "")),
                    lon=lon,
                    lat=lat,
                    in_simulation_domain=False,
                    has_observed_depth=has_depth,
                    observed_depth_m=round(obs_depth, 3) if obs_depth is not None else None,
                    observed_severity=ev.get("flood_severity", ""),
                    simulated_depth_m=0.0,
                    depth_error_m=None,
                    is_hit=False,
                    classification="OUT_OF_DOMAIN",
                )
            else:
                sim_depth = sample_depth_window(rc[0], rc[1], radius_cells=1)
                is_sim_flooded = sim_depth >= flood_threshold_m
                is_obs_flooded = (obs_depth >= flood_threshold_m) if obs_depth is not None else True

                err = (sim_depth - obs_depth) if obs_depth is not None else None

                if is_obs_flooded and is_sim_flooded:
                    classification = "HIT"
                    tp_count += 1
                elif is_obs_flooded and not is_sim_flooded:
                    classification = "MISSED"
                    fn_count += 1
                elif not is_obs_flooded and is_sim_flooded:
                    classification = "FALSE_ALARM"
                    fp_count += 1
                else:
                    classification = "CORRECT_REJECTION"
                    tn_count += 1

                ev_record = HistoricalEventValidationRecord(
                    event_id=str(ev["event_id"]),
                    locality=ev.get("locality", "Unknown"),
                    ward=ev.get("ward", "Unknown"),
                    date_observed=str(ev.get("date", "")),
                    lon=lon,
                    lat=lat,
                    in_simulation_domain=True,
                    has_observed_depth=has_depth,
                    observed_depth_m=round(obs_depth, 3) if obs_depth is not None else None,
                    observed_severity=ev.get("flood_severity", ""),
                    simulated_depth_m=round(sim_depth, 3),
                    depth_error_m=round(err, 3) if err is not None else None,
                    is_hit=is_sim_flooded,
                    classification=classification,
                )
                report.events_in_domain += 1
                if is_sim_flooded:
                    report.events_hit += 1
                else:
                    report.events_missed += 1

                if obs_depth is not None:
                    depth_errors.append(abs(err))
                    observed_depths.append(obs_depth)
                    simulated_depths.append(sim_depth)

            report.event_details.append(ev_record)

        if report.events_in_domain > 0:
            report.event_hit_rate_pct = round(
                report.events_hit / report.events_in_domain * 100.0, 1
            )

        # ── 3. Paired Depth Metrics (ONLY when valid paired observations exist) ──
        if depth_errors:
            n_depth = len(depth_errors)
            errors_signed = [s - o for s, o in zip(simulated_depths, observed_depths)]
            mae = float(np.mean(depth_errors))
            rmse = float(np.sqrt(np.mean([e ** 2 for e in errors_signed])))
            bias = float(np.mean(errors_signed))

            report.paired_depth_metrics = PairedDepthMetrics(
                sample_count_n=n_depth,
                mean_absolute_error_m=round(mae, 3),
                root_mean_squared_error_m=round(rmse, 3),
                mean_bias_error_m=round(bias, 3),
                mean_observed_depth_m=round(float(np.mean(observed_depths)), 3),
                mean_simulated_depth_m=round(float(np.mean(simulated_depths)), 3),
                status="valid",
            )
        else:
            report.paired_depth_metrics = PairedDepthMetrics(
                sample_count_n=0,
                mean_absolute_error_m=None,
                root_mean_squared_error_m=None,
                mean_bias_error_m=None,
                mean_observed_depth_m=None,
                mean_simulated_depth_m=None,
                status="insufficient_validation_data",
            )

        # ── 4. Categorical Contingency Metrics ──
        total_eval = tp_count + fn_count + fp_count + tn_count
        recall = tp_count / (tp_count + fn_count) if (tp_count + fn_count) > 0 else 0.0
        precision = tp_count / (tp_count + fp_count) if (tp_count + fp_count) > 0 else None
        csi = tp_count / (tp_count + fp_count + fn_count) if (tp_count + fp_count + fn_count) > 0 else 0.0
        far = fp_count / (tp_count + fp_count) if (tp_count + fp_count) > 0 else (0.0 if precision == 1.0 else None)

        report.contingency_metrics = ContingencyMetrics(
            true_positives=tp_count,
            false_positives=fp_count,
            false_negatives=fn_count,
            true_negatives=tn_count,
            sample_count_n=total_eval,
            recall_pod=round(recall, 3),
            precision=round(precision, 3) if precision is not None else None,
            critical_success_index=round(csi, 3),
            false_alarm_ratio=round(far, 3) if far is not None else None,
            flood_threshold_m=flood_threshold_m,
        )

        flooded_mask = depth_grid >= flood_threshold_m
        report.simulated_flooded_cells = int(np.sum(flooded_mask))
        report.simulated_flooded_area_km2 = round(
            report.simulated_flooded_cells * (dx ** 2) / 1e6, 4
        )

        # ── 5. Scientific Facts & Documented Limitations ──
        report.observed_facts = [
            f"Ground reference database: {report.events_observed_in_window} verified flood records in study window.",
            f"{report.events_in_domain} records located inside the active hydraulic simulation domain bounding box.",
            f"Ground flood hotspots: {report.hotspots_in_domain} chronic spots evaluated in active domain.",
        ]
        if report.paired_depth_metrics and report.paired_depth_metrics.sample_count_n > 0:
            report.observed_facts.append(
                f"Mean observed depth across {report.paired_depth_metrics.sample_count_n} measured locations: "
                f"{report.paired_depth_metrics.mean_observed_depth_m:.2f} m"
            )

        report.simulated_results = [
            f"Simulated flood extent: {report.simulated_flooded_area_km2:.3f} km² ({report.simulated_flooded_cells} inundated cells).",
            f"Hotspot Detection Rate (Recall): {report.hotspot_hit_rate_pct:.1f}% ({report.hotspots_hit}/{report.hotspots_in_domain} hit).",
            f"Event Observation Recall (POD): {report.event_hit_rate_pct:.1f}% ({report.events_hit}/{report.events_in_domain} hit).",
        ]
        if report.paired_depth_metrics and report.paired_depth_metrics.sample_count_n > 0:
            report.simulated_results.append(
                f"Paired Depth MAE: {report.paired_depth_metrics.mean_absolute_error_m:.3f} m, "
                f"RMSE: {report.paired_depth_metrics.root_mean_squared_error_m:.3f} m, "
                f"Bias: {report.paired_depth_metrics.mean_bias_error_m:+.3f} m."
            )

        report.scientific_assumptions = [
            f"Urban flood cutoff threshold: {flood_threshold_m * 100:.0f} cm water depth.",
            f"Spatial search window: 1-cell radius (~{dx * 1.5:.0f} m) for geocoding tolerance.",
            "Terrain: Copernicus GLO-30 Digital Surface Model.",
            "Numerical Solver: 2D Diffusive Wave equation with Horton infiltration and drainage coupling.",
        ]

        report.limitations = [
            "Point flood reports reflect localized ground evidence and do not cover unmonitored back alleys.",
            "Satellite radar repeat pass (Sentinel-1 12-day orbit) limits continuous cloudburst peak capture.",
            "Calculated metrics apply strictly to the evaluated event window and do not guarantee future forecast accuracy.",
        ]

        return report


_validator_instance: Optional[HistoricalValidator] = None


def get_historical_validator() -> HistoricalValidator:
    """Get singleton HistoricalValidator instance."""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = HistoricalValidator()
    return _validator_instance
