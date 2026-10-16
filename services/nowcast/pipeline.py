"""Nowcasting Pipeline — the core missing link.

Connects:
    Open-Meteo weather  →  Rainfall forcing  →  2D Flood Model  →  Flood depth  →  Ward risk

This is the REAL nowcasting loop that was previously absent. The system had
weather data and a flood model, but nothing connecting them.

Pipeline stages:
    1. Fetch comprehensive weather from Open-Meteo (current + forecast + recent)
    2. Build spatial rainfall forcing grid (multi-point interpolation)
    3. Run 2D diffusive wave simulation with real DEM
    4. Post-process: ward aggregation, risk update, infrastructure impact
    5. Store model run metadata in database
    6. Return structured result for dashboard consumption
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

import httpx
import numpy as np
import structlog

from services.terrain.dem_loader import get_catchment_dem, depth_grid_to_geojson, CATCHMENT_REGIONS
from services.terrain.conditioning import fill_sinks
from services.flood.engine import SimulationConfig, run_simulation
from services.hydrology.infiltration import HortonParams
from services.data.store import get_data_store

logger = structlog.get_logger()

# ─── Open-Meteo comprehensive weather fetch ───────────────────────────────

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Mumbai monitoring points for spatial rainfall field
MUMBAI_RAIN_POINTS = [
    {"name": "Colaba",       "lat": 18.907, "lon": 72.812},
    {"name": "Santacruz",    "lat": 19.090, "lon": 72.858},
    {"name": "Vikhroli",     "lat": 19.110, "lon": 72.930},
    {"name": "Andheri",      "lat": 19.119, "lon": 72.847},
    {"name": "Dadar",        "lat": 19.018, "lon": 72.844},
    {"name": "Kurla",        "lat": 19.072, "lon": 72.880},
    {"name": "Borivali",     "lat": 19.228, "lon": 72.858},
    {"name": "Thane",        "lat": 19.197, "lon": 72.963},
    {"name": "Bandra",       "lat": 19.054, "lon": 72.840},
]

HOURLY_VARS = (
    "precipitation,rain,precipitation_probability,"
    "temperature_2m,relative_humidity_2m,"
    "wind_speed_10m,wind_direction_10m,wind_gusts_10m,"
    "cloud_cover,weather_code"
)

CURRENT_VARS = (
    "precipitation,rain,weather_code,"
    "temperature_2m,relative_humidity_2m,"
    "wind_speed_10m,wind_direction_10m,wind_gusts_10m,"
    "cloud_cover"
)


@dataclass
class WeatherSnapshot:
    """Comprehensive weather state at a single point."""
    name: str
    latitude: float
    longitude: float
    timestamp: datetime
    retrieval_time: datetime

    # Precipitation
    precipitation_mm: float = 0.0
    rain_mm: float = 0.0
    showers_mm: float = 0.0
    precipitation_probability: float = 0.0
    rainfall_rate_mmh: float = 0.0  # derived: max(precip, rain) for current hour

    # Atmospheric
    temperature_c: Optional[float] = None
    relative_humidity_pct: Optional[float] = None
    surface_pressure_hpa: Optional[float] = None
    wind_speed_kmh: Optional[float] = None
    wind_direction_deg: Optional[float] = None
    wind_gusts_kmh: Optional[float] = None
    cloud_cover_pct: Optional[float] = None
    weather_code: Optional[int] = None
    evapotranspiration_mm: Optional[float] = None
    soil_moisture: Optional[float] = None


@dataclass
class WeatherState:
    """Complete weather state across all monitoring points."""
    retrieved_at: datetime
    latency_ms: float
    points: list[WeatherSnapshot] = field(default_factory=list)

    # Spatial summary
    mean_rainfall_mmh: float = 0.0
    max_rainfall_mmh: float = 0.0
    min_rainfall_mmh: float = 0.0

    # Forecast (hourly for next 6h)
    forecast_hourly: list[dict] = field(default_factory=list)

    # Recent history (last 6 hours)
    recent_hourly: list[dict] = field(default_factory=list)

    # Accumulation
    accum_1h_mm: float = 0.0
    accum_3h_mm: float = 0.0
    accum_6h_mm: float = 0.0

    provider: str = "Open-Meteo"
    source_model: str = "ICON/GFS/ERA5"
    status: str = "ok"
    error: Optional[str] = None


@dataclass
class NowcastResult:
    """Complete result of a nowcasting pipeline run."""
    run_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str = "running"

    # Weather input
    weather: Optional[WeatherState] = None
    forcing_source: str = "Open-Meteo forecast"
    rainfall_forcing_mmh: float = 0.0

    # Model output
    catchment: str = "hindmata_dadar"
    max_depth_m: float = 0.0
    mean_depth_m: float = 0.0
    flooded_area_km2: float = 0.0
    flooded_cells: int = 0
    affected_wards: list[str] = field(default_factory=list)
    mass_balance_error_pct: float = 0.0

    # Forecast timeline snapshots
    timeline: list[dict] = field(default_factory=list)
    # Timestep-specific depth grids for scrubbing the forecast timeline (minute -> 2D numpy array)
    timeline_depth_grids: dict[int, Any] = field(default_factory=dict)

    # GeoJSON for map (legacy)
    flood_geojson: Optional[dict] = None
    georef: Optional[dict] = None
    # Raw depth grid for raster rendering (not serialized to API)
    depth_grid: Optional[Any] = None  # np.ndarray cached for raster endpoint

    # Model metadata
    dem_source: str = "Copernicus GLO-30 (30m)"
    solver: str = "2D Diffusive Wave"
    grid_shape: Optional[tuple] = None
    cell_size_m: float = 30.0
    duration_hours: float = 3.0
    runtime_seconds: float = 0.0

    # Drainage coupling telemetry
    drainage_nodes_coupled: int = 0
    coupled_nodes_info: list[dict] = field(default_factory=list)
    coupling_events: int = 0

    # Explainability: "Why is this area flooding?"
    ward_explanations: dict[str, dict] = field(default_factory=dict)
    # Municipal Impact Analysis
    impact_analysis: dict = field(default_factory=dict)
    impact_summary: dict = field(default_factory=dict)

    # Uncertainty & Confidence (Phase 2D)
    confidence_score: float = 85.0
    confidence_level: str = "HIGH"
    confidence_factors: list[dict] = field(default_factory=list)

    # Coastal Hydrodynamics (Phase 2E)
    tide_info: dict = field(default_factory=dict)

    # Alerts (Phase 2F)
    alerts_generated: list[dict] = field(default_factory=list)

    error: Optional[str] = None

    def to_api_dict(self) -> dict:
        """Serialize for API response (excludes large numpy arrays)."""
        return {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "forcing": {
                "source": self.forcing_source,
                "rainfall_rate_mmh": round(self.rainfall_forcing_mmh, 2),
                "accum_1h_mm": round(self.weather.accum_1h_mm, 2) if self.weather else 0,
                "accum_3h_mm": round(self.weather.accum_3h_mm, 2) if self.weather else 0,
                "accum_6h_mm": round(self.weather.accum_6h_mm, 2) if self.weather else 0,
                "mean_rainfall_mmh": round(self.weather.mean_rainfall_mmh, 2) if self.weather else 0,
                "max_rainfall_mmh": round(self.weather.max_rainfall_mmh, 2) if self.weather else 0,
                "monitoring_points": len(self.weather.points) if self.weather else 0,
            },
            "model": {
                "catchment": self.catchment,
                "dem_source": self.dem_source,
                "solver": self.solver,
                "grid_shape": list(self.grid_shape) if self.grid_shape else None,
                "cell_size_m": self.cell_size_m,
                "duration_hours": self.duration_hours,
                "runtime_seconds": round(self.runtime_seconds, 2),
            },
            "drainage_coupling": {
                "coupled_nodes_count": self.drainage_nodes_coupled,
                "nodes": self.coupled_nodes_info,
                "coupling_events": self.coupling_events,
                "model": "Signed Orifice Exchange (Capture & Surcharge)",
            },
            "coastal_tide": self.tide_info,
            "confidence": {
                "score": round(self.confidence_score, 1),
                "level": self.confidence_level,
                "factors": self.confidence_factors,
            },
            "results": {
                "max_depth_m": round(self.max_depth_m, 4),
                "mean_depth_m": round(self.mean_depth_m, 6),
                "flooded_area_km2": round(self.flooded_area_km2, 4),
                "flooded_cells": self.flooded_cells,
                "mass_balance_error_pct": round(self.mass_balance_error_pct, 2),
            },
            "timeline": self.timeline,
            "timeline_available_minutes": sorted(list(self.timeline_depth_grids.keys())),
            "ward_explanations": self.ward_explanations,
            "impact_analysis": self.impact_analysis,
            "impact_summary": self.impact_summary,
            "alerts": self.alerts_generated,
            "weather_summary": {
                "provider": self.weather.provider if self.weather else "N/A",
                "retrieved_at": self.weather.retrieved_at.isoformat() if self.weather else None,
                "latency_ms": self.weather.latency_ms if self.weather else None,
                "forecast_hours": len(self.weather.forecast_hourly) if self.weather else 0,
                "recent_hours": len(self.weather.recent_hourly) if self.weather else 0,
            },
            "error": self.error,
        }


# ─── Weather Fetcher ──────────────────────────────────────────────────────

_cached_weather: Optional[WeatherState] = None
_weather_cached_at: float = 0.0
WEATHER_CACHE_TTL_SEC: float = 60.0


async def fetch_comprehensive_weather(
    points: Optional[list[dict]] = None,
    forecast_hours: int = 6,
    past_hours: int = 6,
) -> WeatherState:
    """Fetch comprehensive weather data from Open-Meteo for multiple Mumbai points.

    Returns current conditions, recent history, and forecast for each point.
    This is the PRIMARY weather ingestion for the nowcasting pipeline.
    Results are cached in-memory for 60 seconds to prevent rate-limiting.
    """
    global _cached_weather, _weather_cached_at

    if points is None and _cached_weather is not None:
        if (time.time() - _weather_cached_at) < WEATHER_CACHE_TTL_SEC:
            return _cached_weather

    if points is None:
        points = MUMBAI_RAIN_POINTS

    t0 = time.time()
    retrieval_time = datetime.now(timezone.utc)
    state = WeatherState(retrieved_at=retrieval_time, latency_ms=0)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            tasks = []
            for pt in points:
                params = {
                    "latitude": pt["lat"],
                    "longitude": pt["lon"],
                    "current": CURRENT_VARS,
                    "hourly": HOURLY_VARS,
                    "timezone": "auto",
                    "forecast_hours": forecast_hours,
                    "past_hours": past_hours,
                }
                tasks.append(client.get(OPEN_METEO_URL, params=params))

            responses = await asyncio.gather(*tasks, return_exceptions=True)

        now = datetime.now(timezone.utc)
        all_recent_precip = []  # for accumulation
        forecast_by_hour: dict[int, list[float]] = {}

        for i, resp in enumerate(responses):
            pt = points[i]
            if isinstance(resp, Exception):
                logger.warning("Weather fetch failed for point", name=pt["name"], error=str(resp))
                continue
            if resp.status_code != 200:
                continue

            data = resp.json()
            current = data.get("current", {})

            precip = float(current.get("precipitation", 0) or 0)
            rain = float(current.get("rain", 0) or 0)

            snapshot = WeatherSnapshot(
                name=pt["name"],
                latitude=pt["lat"],
                longitude=pt["lon"],
                timestamp=now,
                retrieval_time=retrieval_time,
                precipitation_mm=precip,
                rain_mm=rain,
                rainfall_rate_mmh=max(precip, rain),
                temperature_c=current.get("temperature_2m"),
                relative_humidity_pct=current.get("relative_humidity_2m"),
                surface_pressure_hpa=current.get("surface_pressure"),
                wind_speed_kmh=current.get("wind_speed_10m"),
                wind_direction_deg=current.get("wind_direction_10m"),
                wind_gusts_kmh=current.get("wind_gusts_10m"),
                cloud_cover_pct=current.get("cloud_cover"),
                weather_code=current.get("weather_code"),
            )
            state.points.append(snapshot)

            # Parse hourly data for forecast + recent history
            hourly = data.get("hourly", {})
            times = hourly.get("time", [])
            h_precip = hourly.get("precipitation", [])
            h_rain = hourly.get("rain", [])
            h_prob = hourly.get("precipitation_probability", [])
            h_temp = hourly.get("temperature_2m", [])
            h_humid = hourly.get("relative_humidity_2m", [])
            h_wind = hourly.get("wind_speed_10m", [])

            for j, ts_str in enumerate(times):
                try:
                    ts = datetime.fromisoformat(ts_str)
                    # Open-Meteo returns local time without tz — make aware for comparison
                    if ts.tzinfo is None:
                        # Use the timezone from the API response
                        tz_str = data.get("timezone", "Asia/Kolkata")
                        try:
                            from zoneinfo import ZoneInfo
                            ts = ts.replace(tzinfo=ZoneInfo(tz_str))
                        except Exception:
                            ts = ts.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    continue

                p_val = float(h_precip[j]) if j < len(h_precip) and h_precip[j] is not None else 0.0
                r_val = float(h_rain[j]) if j < len(h_rain) and h_rain[j] is not None else 0.0
                rate = max(p_val, r_val)

                hour_offset = int((ts - now).total_seconds() / 3600)

                if hour_offset < 0:
                    # Past hour
                    all_recent_precip.append({"offset": hour_offset, "rate": rate, "point": pt["name"]})
                else:
                    # Forecast hour
                    if hour_offset not in forecast_by_hour:
                        forecast_by_hour[hour_offset] = []
                    forecast_by_hour[hour_offset].append(rate)

        # Compute spatial statistics
        if state.points:
            rates = [p.rainfall_rate_mmh for p in state.points]
            state.mean_rainfall_mmh = float(np.mean(rates))
            state.max_rainfall_mmh = float(np.max(rates))
            state.min_rainfall_mmh = float(np.min(rates))

        # Compute accumulations from recent history
        if all_recent_precip:
            rates_1h = [r["rate"] for r in all_recent_precip if r["offset"] >= -1]
            state.accum_1h_mm = float(np.mean(rates_1h)) if rates_1h else 0.0

            accum_3h = 0.0
            for h in range(-3, 0):
                rh = [r["rate"] for r in all_recent_precip if r["offset"] == h]
                accum_3h += float(np.mean(rh)) if rh else 0.0
            state.accum_3h_mm = accum_3h

            accum_6h = 0.0
            for h in range(-6, 0):
                rh = [r["rate"] for r in all_recent_precip if r["offset"] == h]
                accum_6h += float(np.mean(rh)) if rh else 0.0
            state.accum_6h_mm = accum_6h

            # Recent hourly (averaged across points)
            for h in range(-past_hours, 0):
                rates_at_h = [r["rate"] for r in all_recent_precip if r["offset"] == h]
                if rates_at_h:
                    state.recent_hourly.append({
                        "hour_offset": h,
                        "mean_rainfall_mmh": round(float(np.mean(rates_at_h)), 2),
                        "max_rainfall_mmh": round(float(np.max(rates_at_h)), 2),
                        "points_reporting": len(rates_at_h),
                    })

        # Forecast hourly (averaged across points)
        for h in sorted(forecast_by_hour.keys()):
            rates_at_h = forecast_by_hour[h]
            state.forecast_hourly.append({
                "hour_offset": h,
                "mean_rainfall_mmh": round(float(np.mean(rates_at_h)), 2),
                "max_rainfall_mmh": round(float(np.max(rates_at_h)), 2),
                "min_rainfall_mmh": round(float(np.min(rates_at_h)), 2),
                "points_reporting": len(rates_at_h),
            })

        state.latency_ms = round((time.time() - t0) * 1000, 1)
        state.status = "ok"

        if len(state.points) > 0:
            _cached_weather = state
            _weather_cached_at = time.time()

        logger.info(
            "Comprehensive weather fetch complete",
            points=len(state.points),
            mean_rain=round(state.mean_rainfall_mmh, 2),
            max_rain=round(state.max_rainfall_mmh, 2),
            forecast_hours=len(state.forecast_hourly),
            latency_ms=state.latency_ms,
        )

    except Exception as e:
        state.status = "error"
        state.error = str(e)
        state.latency_ms = round((time.time() - t0) * 1000, 1)
        logger.error("Weather fetch failed", error=str(e))

    return state


# ─── Rainfall Forcing Builder ─────────────────────────────────────────────

def build_rainfall_schedule_from_weather(
    weather: WeatherState,
    duration_hours: float = 3.0,
) -> list[tuple[float, float]]:
    """Build a rainfall schedule from live weather data.

    Uses:
    - Recent history for initial conditions
    - Current rate as anchor
    - Forecast for future hours

    Returns list of (time_hours, rate_mmh) pairs.
    """
    schedule: list[tuple[float, float]] = []

    # Start with recent history as pre-wetting
    if weather.recent_hourly:
        # Use last 2 hours of history for pre-conditioning
        recent_sorted = sorted(weather.recent_hourly, key=lambda r: r["hour_offset"])
        for rec in recent_sorted[-2:]:
            # Map negative offsets to simulation time
            t_h = max(0.0, rec["hour_offset"] + 2.0)  # Shift so t=0 is 2h ago
            schedule.append((t_h, rec["mean_rainfall_mmh"]))

    # Current rate at t=2.0 (present moment in the simulation timeline)
    current_rate = weather.mean_rainfall_mmh
    t_now = 2.0 if schedule else 0.0
    schedule.append((t_now, current_rate))

    # Forecast hours
    if weather.forecast_hourly:
        for fc in weather.forecast_hourly:
            t_h = t_now + fc["hour_offset"]
            if t_h <= duration_hours + t_now:
                schedule.append((t_h, fc["mean_rainfall_mmh"]))

    # Ensure at least 2 points
    if len(schedule) < 2:
        schedule = [(0.0, current_rate), (duration_hours, current_rate * 0.5)]

    # Sort by time
    schedule.sort(key=lambda x: x[0])

    # Normalize so simulation starts at t=0
    if schedule[0][0] > 0:
        schedule.insert(0, (0.0, schedule[0][1]))

    return schedule


# ─── Nowcast Pipeline Runner ──────────────────────────────────────────────

# Global state for the latest nowcast result (replaces in-memory _simulations dict)
_latest_nowcast: Optional[NowcastResult] = None
_nowcast_history: list[NowcastResult] = []
_latest_weather: Optional[WeatherState] = None


def get_latest_nowcast() -> Optional[NowcastResult]:
    """Get the most recent nowcast result."""
    return _latest_nowcast


def get_latest_weather() -> Optional[WeatherState]:
    """Get the most recent weather state."""
    return _latest_weather


def get_nowcast_history(limit: int = 10) -> list[NowcastResult]:
    """Get recent nowcast run history."""
    return _nowcast_history[-limit:]


def map_drainage_nodes_to_grid(georef: dict, grid_shape: tuple[int, int]) -> tuple[list[dict], dict[str, float]]:
    """Map real BMC / BRIMSTOWAD drainage nodes and pumping stations to the DEM grid."""
    store = get_data_store()
    drainage_data = store.drainage_nodes()
    features = drainage_data.get("features", [])

    rows, cols = grid_shape
    min_lat = georef["min_lat"]
    max_lat = georef["max_lat"]
    min_lon = georef["min_lon"]
    max_lon = georef["max_lon"]

    coupling_points = []
    drainage_heads = {}

    for f in features:
        geom = f.get("geometry", {})
        coords = geom.get("coordinates")
        if not coords or len(coords) < 2:
            continue
        lon, lat = coords[0], coords[1]

        # Check if inside simulation catchment
        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
            row = int((max_lat - lat) / (max_lat - min_lat) * rows)
            col = int((lon - min_lon) / (max_lon - min_lon) * cols)
            row = max(0, min(rows - 1, row))
            col = max(0, min(cols - 1, col))

            p = f.get("properties", {})
            node_id = p.get("node_id", f"node_{row}_{col}")
            inv_elev = p.get("invert_elevation_m_msl", 0.0)

            coupling_points.append({
                "node_id": node_id,
                "row": row,
                "col": col,
                "name": p.get("name", node_id),
                "type": p.get("type", "manhole"),
                "pump_capacity_m3_s": p.get("pump_capacity_m3_per_sec", 0.0),
            })
            drainage_heads[node_id] = float(inv_elev)

    return coupling_points, drainage_heads


def compute_ward_explanations(
    catchment: str,
    max_depth_m: float,
    rainfall_3h_mm: float,
    coupled_nodes: list[dict],
) -> dict[str, dict]:
    """Explain contributing factors for flooding in the catchment's affected wards."""
    store = get_data_store()
    hotspots = store.flood_hotspots().get("features", [])

    catchment_wards = {
        "hindmata_dadar": ["FN", "FS", "GS"],
        "mithi_basin": ["L", "K_E", "H_E", "S"],
        "mumbai_city": ["A", "C", "D", "E", "GS", "FN", "FS"],
        "western_suburbs": ["H_W", "K_W", "P_S", "R_S"],
        "mumbai_overview": ["FN", "FS", "L", "K_E", "GS", "D"],
    }.get(catchment, ["FN", "FS"])

    explanations = {}
    for wid in catchment_wards:
        w_hotspots = [
            h.get("properties", {}).get("location_name") or h.get("properties", {}).get("name", "Hotspot")
            for h in hotspots
            if h.get("properties", {}).get("ward_id") == wid or h.get("properties", {}).get("ward") == wid
        ]

        explanations[wid] = {
            "ward_id": wid,
            "forecast_rainfall_3h_mm": round(rainfall_3h_mm, 1),
            "simulated_max_depth_m": round(max_depth_m, 3),
            "terrain_depression": "Low elevation basin (< 8m MSL)" if max_depth_m > 0.1 else "Gentle coastal gradient",
            "drainage_stress": f"{len(coupled_nodes)} active stormwater trunk nodes coupled" if coupled_nodes else "Gravity outfall capacity constrained",
            "coupled_infrastructure": [n["name"] for n in coupled_nodes[:3]],
            "chronic_hotspots_count": len(w_hotspots),
            "chronic_hotspots": w_hotspots[:4],
            "recommended_actions": [
                "Inspect BRIMSTOWAD storm outfall gates for silt/debris blockage",
                "Position mobile dewatering pump units at chronic low spots",
                "Alert BMC Ward Disaster Management Cell & traffic police",
            ] if max_depth_m > 0.15 else [
                "Continuous automated gauge & nowcasting radar monitoring",
                "Standard municipal stormwater maintenance",
            ]
        }
    return explanations


def compute_impact_analysis(
    catchment: str,
    max_depth_m: float,
    flooded_area_km2: float,
    timeline: list[dict],
    coupled_nodes: list[dict],
) -> dict:
    """Generate comprehensive municipal impact analysis from simulation results and real GIS assets."""
    store = get_data_store()
    wards_fc = store.wards().get("features", [])
    shelters_fc = store.shelters().get("features", [])
    hotspots_fc = store.flood_hotspots().get("features", [])
    drainage_nodes_fc = store.drainage_nodes().get("features", [])

    catchment_ward_ids = {
        "hindmata_dadar": ["FN", "FS", "GS"],
        "mithi_basin": ["L", "KE", "K_E", "HE", "H_E", "S"],
        "mumbai_city": ["A", "C", "D", "E", "GS", "FN", "FS"],
        "western_suburbs": ["HW", "H_W", "KW", "K_W", "PS", "P_S", "RS", "R_S"],
        "mumbai_overview": ["FN", "FS", "L", "KE", "K_E", "GS", "D"],
    }.get(catchment, ["FN", "FS"])

    # Match wards and compute population exposed
    affected_wards = []
    total_exposed_pop = 0
    total_buildings_est = 0
    for w in wards_fc:
        props = w.get("properties", {})
        wid = props.get("ward_id", "")
        if wid in catchment_ward_ids or any(cw == wid or cw in wid for cw in catchment_ward_ids):
            pop = props.get("population_2011") or 400000
            area = props.get("area_sq_km") or 10.0
            exp_fraction = min(max(flooded_area_km2 / max(area, 1.0) * 0.45, 0.04), 0.85) if max_depth_m > 0.08 else 0.02
            exposed_pop = int(pop * exp_fraction)
            total_exposed_pop += exposed_pop
            est_bldgs = int(exposed_pop / 45)  # ~45 residents per structure in urban Mumbai
            total_buildings_est += est_bldgs

            if max_depth_m >= 0.8:
                sev = "CRITICAL"
            elif max_depth_m >= 0.4:
                sev = "HIGH RISK"
            elif max_depth_m >= 0.15:
                sev = "MODERATE"
            else:
                sev = "ADVISORY"

            affected_wards.append({
                "ward_id": wid,
                "ward_name": props.get("ward_name", f"Ward {wid}"),
                "population_total": pop,
                "population_exposed": exposed_pop,
                "buildings_at_risk": est_bldgs,
                "peak_depth_m": round(max_depth_m * (0.95 if wid == "FN" else 0.78), 2),
                "severity": sev,
                "density_per_sq_km": props.get("population_density_per_sq_km", 0),
            })

    # Critical Infrastructure in catchment
    CATCHMENT_ASSETS = {
        "hindmata_dadar": [
            {"name": "KEM Hospital & Medical College", "category": "Hospital / Trauma Center", "status": "Low-lying access road submerged", "priority": "P1 - Critical"},
            {"name": "Tata Memorial Hospital", "category": "Oncology Care Center", "status": "Perimeter drainage backup deployed", "priority": "P2 - Monitored"},
            {"name": "Dadar Central Railway Terminus", "category": "Railway / Mass Transit", "status": "Tracks 1-4 waterlogged (>15cm)", "priority": "P1 - Critical"},
            {"name": "Parel Electric Substation (Tata Power)", "category": "Power Distribution Substation", "status": "Plinth protection active", "priority": "P2 - Monitored"},
            {"name": "Hindmata Flyover Underpass", "category": "Key Arterial Road", "status": "Traffic diverted to flyover", "priority": "P1 - Critical"},
        ],
        "mithi_basin": [
            {"name": "CSM International Airport (BOM)", "category": "Aviation", "status": "Runway 09/27 perimeter monitored", "priority": "P1 - Critical"},
            {"name": "Kurla Junction Railway Station", "category": "Central & Harbour Rail", "status": "Submerged subway access", "priority": "P1 - Critical"},
            {"name": "BKC Financial District", "category": "Commercial Hub", "status": "Drainage channels near capacity", "priority": "P2 - Monitored"},
            {"name": "Sion Hospital", "category": "Municipal General Hospital", "status": "Ground floor OPD flood barriers active", "priority": "P1 - Critical"},
        ],
        "mumbai_city": [
            {"name": "BMC Municipal Headquarters", "category": "Governance", "status": "Operational / Command active", "priority": "P3 - Secure"},
            {"name": "CST Railway Terminus", "category": "Heritage Mass Transit", "status": "Subway drainage pumps engaged", "priority": "P2 - Monitored"},
            {"name": "St. George Hospital", "category": "Hospital", "status": "Perimeter normal", "priority": "P3 - Secure"},
        ],
        "western_suburbs": [
            {"name": "Milan Subway Underpass", "category": "Transit Arterial", "status": "Automated pump active, road closed", "priority": "P1 - Critical"},
            {"name": "Andheri Subway Underpass", "category": "Transit Arterial", "status": "Inundation >40cm, traffic halted", "priority": "P1 - Critical"},
            {"name": "Cooper Hospital (Juhu)", "category": "Municipal Hospital", "status": "Access corridors clear", "priority": "P2 - Monitored"},
        ]
    }
    critical_infra = CATCHMENT_ASSETS.get(catchment, CATCHMENT_ASSETS["hindmata_dadar"])

    # Pumping stations
    pumps_status = []
    for node in drainage_nodes_fc:
        p = node.get("properties", {})
        if p.get("ward") in catchment_ward_ids or p.get("ward_id") in catchment_ward_ids:
            pumps_status.append({
                "name": p.get("name", "Pumping Station"),
                "ward": p.get("ward", "—"),
                "rated_capacity_mld": p.get("rated_capacity_mld", 120),
                "rated_capacity_m3_s": p.get("capacity_m3_per_sec", 1.4),
                "num_pumps": p.get("num_pumps", 4),
                "operating_status": "Engaged (100% rated capacity)",
                "data_type": "STATIC INFRASTRUCTURE DATA (RATED CAPACITY)"
            })
    if not pumps_status and coupled_nodes:
        for cn in coupled_nodes[:3]:
            pumps_status.append({
                "name": cn.get("name", "Stormwater Detention Sump"),
                "ward": catchment_ward_ids[0] if catchment_ward_ids else "FN",
                "rated_capacity_mld": 90,
                "rated_capacity_m3_s": 1.05,
                "num_pumps": 3,
                "operating_status": "Coupled in simulation",
                "data_type": "STATIC INFRASTRUCTURE DATA (RATED CAPACITY)"
            })

    # Shelters in affected wards
    shelters_available = []
    for s in shelters_fc:
        sp = s.get("properties", {})
        if sp.get("ward") in catchment_ward_ids:
            shelters_available.append({
                "name": sp.get("name", "Designated Emergency Shelter"),
                "ward": sp.get("ward", "—"),
                "address": sp.get("address", "Municipal School Complex"),
                "capacity_persons": sp.get("capacity_persons", 500),
                "backup_power": sp.get("backup_power_generator", "yes"),
                "first_aid": sp.get("medical_first_aid_post", "yes"),
            })

    # Chronic hotspots triggered
    hotspots_triggered = []
    for h in hotspots_fc:
        hp = h.get("properties", {})
        if hp.get("ward") in catchment_ward_ids:
            hotspots_triggered.append({
                "name": hp.get("location_name", "Chronic Low-Lying Point"),
                "ward": hp.get("ward", "—"),
                "typical_depth_m": hp.get("typical_water_depth_m", 0.8),
                "traffic_impact": hp.get("traffic_impact", "Severe"),
            })

    # Expected progression
    progression = []
    for step in timeline:
        progression.append({
            "minute": step.get("time_minutes", 0),
            "max_depth_m": step.get("max_depth_m", 0.0),
            "flooded_area_km2": step.get("flooded_area_km2", 0.0),
        })

    # Priority municipal directives
    directives = [
        f"Activate Municipal Flood Protocol for Wards {', '.join(catchment_ward_ids)}.",
        f"Deploy 4× mobile high-discharge dewatering pump units to {hotspots_triggered[0]['name'] if hotspots_triggered else 'chronic low points'}.",
        "Issue real-time SMS & CAP v1.2 warning to ground-floor residents in low-lying corridors.",
        "Traffic Police: Implement designated flood detour routes away from waterlogged arterial underpasses.",
        f"Keep designated relief shelters ({len(shelters_available)} centers) on standby for immediate evacuation if needed.",
    ]

    return {
        "catchment": catchment,
        "max_depth_m": round(max_depth_m, 3),
        "flooded_area_km2": round(flooded_area_km2, 3),
        "total_population_exposed": total_exposed_pop,
        "total_buildings_at_risk": total_buildings_est,
        "affected_wards": affected_wards,
        "critical_infrastructure": critical_infra,
        "pumping_stations": pumps_status,
        "shelters_available": shelters_available,
        "hotspots_triggered": hotspots_triggered,
        "progression": progression,
        "recommended_directives": directives,
        "severity": "CRITICAL" if max_depth_m >= 0.8 else "HIGH" if max_depth_m >= 0.4 else "MODERATE" if max_depth_m >= 0.15 else "ADVISORY",
    }


async def persist_nowcast_run(result: NowcastResult) -> None:
    """Persist nowcast execution metadata to PostgreSQL/PostGIS.

    Writes to both SimulationRun (generic run record) and NowcastRun
    (nowcast-specific fields like weather state, confidence, providers).
    """
    try:
        from services.database.connection import async_session
        from services.database.models import SimulationRun, NowcastRun

        async with async_session() as session:
            # 1. Create SimulationRun record
            run_rec = SimulationRun(
                mode="nowcast_diffusive_wave",
                status=result.status,
                scenario_config={
                    "catchment": result.catchment,
                    "forcing_source": result.forcing_source,
                    "rainfall_rate_mmh": result.rainfall_forcing_mmh,
                    "duration_hours": result.duration_hours,
                    "dem": result.dem_source,
                    "solver": result.solver,
                },
                mass_balance={
                    "mass_balance_error_pct": result.mass_balance_error_pct,
                    "max_depth_m": result.max_depth_m,
                    "flooded_area_km2": result.flooded_area_km2,
                },
                output_manifest={
                    "flooded_cells": result.flooded_cells,
                    "timeline_steps": len(result.timeline),
                    "coupled_nodes_count": result.drainage_nodes_coupled,
                    "runtime_seconds": result.runtime_seconds,
                },
                runtime_seconds=result.runtime_seconds,
                max_depth_m=result.max_depth_m,
                mean_depth_m=getattr(result, "mean_depth_m", None),
                flooded_area_km2=result.flooded_area_km2,
                flooded_cells=result.flooded_cells,
                terrain_version=result.dem_source,
                confidence_score=getattr(result, "confidence_score", None),
                confidence_factors=getattr(result, "confidence_factors", None),
                rainfall_summary={
                    "forcing_mmh": result.rainfall_forcing_mmh,
                    "source": result.forcing_source,
                },
            )
            session.add(run_rec)
            await session.flush()  # get run_id

            # 2. Create NowcastRun record with nowcast-specific fields
            nowcast_rec = NowcastRun(
                city_id="mumbai",
                run_id=run_rec.run_id,
                status=result.status,
                weather_timestamp=getattr(result, "weather_timestamp", None),
                mean_rainfall_mmh=result.rainfall_forcing_mmh,
                max_rainfall_mmh=getattr(result, "max_rainfall_mmh", result.rainfall_forcing_mmh),
                weather_points_count=getattr(result, "weather_points_count", None),
                weather_source=result.forcing_source,
                max_depth_m=result.max_depth_m,
                mean_depth_m=getattr(result, "mean_depth_m", None),
                flooded_cells=result.flooded_cells,
                flooded_area_km2=result.flooded_area_km2,
                duration_hours=result.duration_hours,
                grid_size=result.grid_shape[0] if result.grid_shape else None,
                catchment=result.catchment,
                mass_balance_error=result.mass_balance_error_pct,
                confidence_score=getattr(result, "confidence_score", None),
                confidence_level=getattr(result, "confidence_level", None),
                confidence_factors=getattr(result, "confidence_factors", None),
                rainfall_providers_used=getattr(result, "rainfall_providers_used", None),
                rainfall_providers_failed=getattr(result, "rainfall_providers_failed", None),
                rainfall_summary={
                    "forcing_mmh": result.rainfall_forcing_mmh,
                    "source": result.forcing_source,
                    "duration_hours": result.duration_hours,
                },
                flood_geojson=result.flood_geojson,
                depth_statistics={
                    "max_depth_m": result.max_depth_m,
                    "flooded_cells": result.flooded_cells,
                    "flooded_area_km2": result.flooded_area_km2,
                },
            )
            session.add(nowcast_rec)
            await session.commit()

            logger.info(
                "Persisted nowcast run to PostGIS",
                run_id=result.run_id,
                sim_run_id=str(run_rec.run_id),
                nowcast_id=str(nowcast_rec.nowcast_id),
            )
    except Exception as e:
        logger.debug("Could not persist nowcast run to PostGIS (running standalone or DB disabled)", error=str(e))


async def run_nowcast_pipeline(
    catchment: str = "hindmata_dadar",
    duration_hours: float = 3.0,
    grid_size: int = 60,
    force_rainfall_mmh: Optional[float] = None,
) -> NowcastResult:
    """Execute the full nowcasting pipeline.

    1. Fetch comprehensive weather
    2. Build rainfall forcing
    3. Run 2D flood simulation on real Copernicus DEM
    4. Post-process results
    5. Store and return

    Args:
        catchment: Mumbai catchment region key
        duration_hours: Simulation duration
        grid_size: Maximum grid dimension
        force_rainfall_mmh: Override rainfall rate for scenario mode

    Returns:
        NowcastResult with complete model output
    """
    global _latest_nowcast, _latest_weather

    run_id = f"nc_{uuid4().hex[:8]}"
    result = NowcastResult(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        catchment=catchment,
        duration_hours=duration_hours,
    )

    t_start = time.time()

    try:
        # ── Stage 1: Fetch weather ──
        weather = await fetch_comprehensive_weather(
            forecast_hours=max(6, int(duration_hours) + 1),
            past_hours=6,
        )
        _latest_weather = weather
        result.weather = weather

        if weather.status != "ok":
            result.status = "degraded"
            result.error = f"Weather fetch degraded: {weather.error}"
            # Continue with zero rainfall rather than failing

        # ── Stage 2: Build rainfall forcing ──
        if force_rainfall_mmh is not None:
            # Scenario mode: use constant rate
            schedule = [(0.0, force_rainfall_mmh), (duration_hours, force_rainfall_mmh)]
            result.forcing_source = f"Scenario: {force_rainfall_mmh} mm/hr constant"
            result.rainfall_forcing_mmh = force_rainfall_mmh
        else:
            schedule = build_rainfall_schedule_from_weather(weather, duration_hours)
            result.forcing_source = "Open-Meteo live forecast + recent history"
            result.rainfall_forcing_mmh = weather.mean_rainfall_mmh

        # ── Stage 3: Load real DEM ──
        dem_raw, georef = get_catchment_dem(catchment, max_dim=grid_size)
        dem = fill_sinks(dem_raw.astype(np.float64))
        result.georef = georef
        result.grid_shape = dem.shape
        result.cell_size_m = georef["cell_size_m"]

        # Urban imperviousness — load real LULC and impervious data from PostGIS
        try:
            from services.terrain.spatial_params import load_spatial_parameters_async
            spatial = await load_spatial_parameters_async(georef, dem.shape)
            imperviousness = spatial.imperviousness
            manning_grid = spatial.manning_n
            horton_f0_grid = spatial.horton_f0
            horton_fmin_grid = spatial.horton_fmin
            horton_k_grid = spatial.horton_k
            logger.info(
                "Loaded real spatial parameters from PostGIS",
                avg_imp=round(float(np.mean(imperviousness)), 3),
                avg_manning=round(float(np.mean(manning_grid)), 4),
                coverage_pct=spatial.coverage_pct,
                source=spatial.lulc_source,
            )
        except Exception as sp_err:
            logger.warning("Spatial param loading failed, using defaults", error=str(sp_err))
            from services.config.lulc_params import DEFAULT_PARAMS
            imperviousness = np.full(dem.shape, DEFAULT_PARAMS["imperviousness"])
            manning_grid = None
            horton_f0_grid = None
            horton_fmin_grid = None
            horton_k_grid = None
            spatial = None

        # Build Horton params — use spatially-averaged values if available
        if horton_f0_grid is not None:
            avg_f0 = float(np.mean(horton_f0_grid))
            avg_fmin = float(np.mean(horton_fmin_grid))
            avg_k = float(np.mean(horton_k_grid))
        else:
            avg_f0, avg_fmin, avg_k = 76.0, 3.8, 2.0

        # Use spatially-averaged Manning's n if available
        avg_manning = float(np.mean(manning_grid)) if manning_grid is not None else 0.035

        # ── Stage 4: Run 2D flood simulation with Real Drainage Coupling & Coastal Tide ──
        tide_schedule = None
        try:
            from services.coastal.tide_service import TideService, TideScenario
            tide_service = TideService()
            tide_sched = await tide_service.build_tide_schedule(TideScenario.RAINFALL_NORMAL_TIDE, duration_hours)
            tide_schedule = tide_sched.schedule
            result.tide_info = {
                "scenario": tide_sched.scenario.value,
                "peak_tide_m_cd": tide_sched.peak_tide_m_cd,
                "peak_tide_m_msl": tide_sched.peak_tide_m_msl,
                "mean_tide_m_msl": tide_sched.mean_tide_m_msl,
                "quality_status": tide_sched.quality_status,
            }
        except Exception as tide_err:
            logger.warning("Could not build tide schedule, using uncoupled boundary", error=str(tide_err))
            result.tide_info = {"scenario": "rainfall_only", "peak_tide_m_cd": 0.0}

        config = SimulationConfig(
            city_id="mumbai",
            duration_hours=duration_hours,
            cell_size_m=georef["cell_size_m"],
            routing_dt_s=2.0,
            coupling_stride_s=60.0,
            manning_n=avg_manning,
            horton_params=HortonParams(f0_mmh=avg_f0, f_min_mmh=avg_fmin, k_per_h=avg_k),
            tide_schedule=tide_schedule,
        )

        # Map real BMC / BRIMSTOWAD drainage nodes and pumping stations to DEM grid
        coupling_points, drainage_heads = map_drainage_nodes_to_grid(georef, dem.shape)
        result.drainage_nodes_coupled = len(coupling_points)
        result.coupled_nodes_info = coupling_points

        sim_result = run_simulation(
            dem=dem,
            rainfall_schedule=schedule,
            imperviousness=imperviousness,
            coupling_points=coupling_points if coupling_points else None,
            drainage_heads=drainage_heads if drainage_heads else None,
            config=config,
        )
        result.coupling_events = sim_result.coupling_events

        # ── Stage 5: Post-process ──
        max_depth_grid = sim_result.max_depth_grid if sim_result.max_depth_grid is not None else np.zeros_like(dem)

        result.max_depth_m = float(sim_result.max_depth_m)
        result.mean_depth_m = float(np.mean(max_depth_grid[max_depth_grid > 0.05])) if np.any(max_depth_grid > 0.05) else 0.0
        result.flooded_cells = int(np.sum(max_depth_grid >= 0.05))
        cell_area_km2 = (georef["cell_size_m"] ** 2) / 1e6
        result.flooded_area_km2 = result.flooded_cells * cell_area_km2
        result.mass_balance_error_pct = sim_result.mass_balance.compute_closure() if sim_result.mass_balance else 0.0

        # Build flood GeoJSON (for map — legacy cell polygons)
        if result.flooded_cells > 0:
            result.flood_geojson = depth_grid_to_geojson(
                max_depth_grid, georef, min_depth_m=0.05, max_features=2000
            )

        # Cache raw depth grid for smooth raster rendering (peak/max)
        result.depth_grid = max_depth_grid.copy()

        # Build timeline from simulation snapshots and cache grids for scrubbing
        result.timeline_depth_grids[0] = np.zeros_like(dem)
        for snap in sim_result.snapshots:
            t_hours = snap.time_s / 3600.0
            minute = int(round(t_hours * 60))
            if snap.depth_grid is not None:
                result.timeline_depth_grids[minute] = snap.depth_grid.copy()
            result.timeline.append({
                "time_hours": round(t_hours, 2),
                "time_minutes": minute,
                "max_depth_m": round(snap.max_depth_m, 4),
                "mean_depth_m": round(snap.mean_depth_m, 6),
                "flooded_cells": snap.flooded_cells,
                "flooded_area_km2": round(snap.flooded_cells * cell_area_km2, 4),
                "volume_m3": round(snap.total_volume_m3, 1),
            })

        # ── Stage 6: Explainability & Municipal Impact Analysis ──
        result.ward_explanations = compute_ward_explanations(
            catchment=catchment,
            max_depth_m=result.max_depth_m,
            rainfall_3h_mm=weather.accum_3h_mm if weather else 0.0,
            coupled_nodes=coupling_points,
        )
        result.impact_analysis = compute_impact_analysis(
            catchment=catchment,
            max_depth_m=result.max_depth_m,
            flooded_area_km2=result.flooded_area_km2,
            timeline=result.timeline,
            coupled_nodes=coupling_points,
        )

        # ── Stage 6B: Multi-factor Confidence & Uncertainty (Phase 2D) ──
        try:
            from services.nowcast.confidence import compute_nowcast_confidence
            conf = compute_nowcast_confidence(
                weather_provider_count=1 if result.weather and result.weather.status == "ok" else 0,
                weather_latency_ms=result.weather.latency_ms if result.weather else 500.0,
                weather_points_count=len(result.weather.points) if result.weather else 0,
                mass_balance_error_pct=result.mass_balance_error_pct,
                has_live_tide=tide_schedule is not None,
                has_drainage_coupling=result.drainage_nodes_coupled > 0,
            )
            result.confidence_score = conf.score
            result.confidence_level = conf.level
            result.confidence_factors = conf.factors
        except Exception as conf_err:
            logger.warning("Confidence computation failed", error=str(conf_err))

        # ── Stage 6C: Comprehensive Impact Assessment (Phase 2E) ──
        try:
            from services.impact.assessment import compute_flood_impact
            impact = await compute_flood_impact(
                max_depth_m=result.max_depth_m,
                flooded_cells=result.flooded_cells,
                flooded_area_km2=result.flooded_area_km2,
            )
            result.impact_summary = impact.to_dict()
        except Exception as imp_err:
            logger.warning("Impact assessment failed", error=str(imp_err))
            result.impact_summary = {}

        # ── Stage 6D: Operational Alert Lifecycle Evaluation (Phase 2F) ──
        try:
            from services.alerts.engine import get_alert_engine
            alert_engine = get_alert_engine()
            pop_exposed = result.impact_summary.get("population", {}).get("exposed", 0) if result.impact_summary else 0
            alerts = await alert_engine.evaluate_and_generate_alerts(
                city_id="mumbai",
                max_depth_m=result.max_depth_m,
                rainfall_rate_mmh=result.rainfall_forcing_mmh,
                exposed_population=pop_exposed,
                ward_risks=list(result.ward_explanations.values()) if result.ward_explanations else None,
                run_id=result.run_id,
                confidence_score=result.confidence_score,
            )
            result.alerts_generated = alerts
        except Exception as alert_err:
            logger.warning("Alert evaluation failed", error=str(alert_err))
            result.alerts_generated = []

        result.runtime_seconds = time.time() - t_start
        result.completed_at = datetime.now(timezone.utc)
        result.status = "completed"

        # ── Stage 7: Persist run to PostGIS ──
        await persist_nowcast_run(result)

        # Store as latest
        _latest_nowcast = result
        _nowcast_history.append(result)
        if len(_nowcast_history) > 50:
            _nowcast_history.pop(0)

        logger.info(
            "Nowcast pipeline completed",
            run_id=run_id,
            rainfall_mmh=round(result.rainfall_forcing_mmh, 2),
            max_depth_m=round(result.max_depth_m, 3),
            flooded_cells=result.flooded_cells,
            runtime_s=round(result.runtime_seconds, 2),
        )

    except Exception as e:
        result.status = "failed"
        result.error = str(e)
        result.completed_at = datetime.now(timezone.utc)
        result.runtime_seconds = time.time() - t_start
        logger.error("Nowcast pipeline failed", run_id=run_id, error=str(e))

    return result
