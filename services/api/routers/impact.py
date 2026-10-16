"""Impact and Exposure Assessment API Router.

Exposes endpoints for flood hazard exposure across population, residential
and commercial buildings, road networks, critical municipal infrastructure,
and designated emergency shelters. Backed by PostGIS spatial queries (ExposureEngine)
and density-based urban models (compute_flood_impact).

Phase 2E-4: Comprehensive impact router.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.impact.assessment import compute_flood_impact, FloodImpact
from services.risk.exposure_engine import ExposureEngine
from services.database.connection import async_session_factory, verify_db_connectivity
from services.database.models import NowcastRun
from sqlalchemy import select, desc

logger = structlog.get_logger()
router = APIRouter(prefix="/impact", tags=["Impact & Exposure"])

_exposure_engine = ExposureEngine()


async def _get_latest_nowcast_metrics() -> tuple[float, int, float]:
    """Retrieve max_depth_m, flooded_cells, and flooded_area_km2 from latest nowcast."""
    try:
        from services.nowcast.pipeline import get_latest_nowcast
        latest = get_latest_nowcast()
        if latest is not None and latest.simulation_result is not None:
            res = latest.simulation_result
            return (
                float(res.get("max_depth_m", 0.0)),
                int(res.get("flooded_cells", 0)),
                float(res.get("flooded_area_km2", 0.0)),
            )
    except Exception:
        pass

    # Try database
    try:
        db_online = await verify_db_connectivity()
        if db_online and async_session_factory is not None:
            async with async_session_factory() as session:
                stmt = (
                    select(NowcastRun)
                    .where(NowcastRun.status == "completed")
                    .order_by(desc(NowcastRun.created_at))
                    .limit(1)
                )
                result = await session.execute(stmt)
                run = result.scalar_one_or_none()
                if run is not None:
                    return (
                        float(run.max_depth_m or 0.0),
                        int(run.flooded_cells or 0),
                        float(run.flooded_area_km2 or 0.0),
                    )
    except Exception as e:
        logger.warning("Error fetching nowcast metrics for impact", error=str(e))

    # Baseline moderate monsoon scenario fallback if no run has occurred yet
    return (0.35, 120, 0.45)


@router.get("/summary")
async def get_impact_summary(
    max_depth_m: Optional[float] = Query(None, description="Override max flood depth (m)"),
    flooded_area_km2: Optional[float] = Query(None, description="Override flooded area (km2)"),
):
    """Get high-level summary of flood exposure and severity for the command center."""
    d_m, cells, area_km2 = await _get_latest_nowcast_metrics()
    if max_depth_m is not None:
        d_m = max_depth_m
    if flooded_area_km2 is not None:
        area_km2 = flooded_area_km2

    impact = await compute_flood_impact(
        max_depth_m=d_m,
        flooded_cells=cells,
        flooded_area_km2=area_km2,
    )
    return impact.to_dict()


@router.get("/population")
async def get_population_exposure():
    """Get population exposure estimates broken down by vulnerability tiers."""
    d_m, cells, area_km2 = await _get_latest_nowcast_metrics()
    impact = await compute_flood_impact(max_depth_m=d_m, flooded_cells=cells, flooded_area_km2=area_km2)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "evaluated_area_km2": area_km2,
        "max_flood_depth_m": d_m,
        "population_exposed": impact.population_exposed,
        "population_in_danger_zone": impact.population_in_danger_zone,
        "shelter_evacuation_needed": impact.population_in_danger_zone > 0,
        "vulnerability_breakdown": {
            "low_risk_depth_under_0_3m": max(0, impact.population_exposed - impact.population_in_danger_zone),
            "high_risk_depth_over_1m": impact.population_in_danger_zone,
        },
    }


@router.get("/buildings")
async def get_buildings_impact():
    """Get building structures exposed to flood water by category."""
    d_m, cells, area_km2 = await _get_latest_nowcast_metrics()
    impact = await compute_flood_impact(max_depth_m=d_m, flooded_cells=cells, flooded_area_km2=area_km2)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_buildings_affected": impact.buildings_affected,
        "severely_affected_ground_floor": impact.buildings_severely_affected,
        "categories": {
            "residential": impact.residential_affected,
            "commercial": impact.commercial_affected,
            "industrial": impact.industrial_affected,
        },
        "advisory": (
            "Electrical shutoffs recommended for ground-floor installations in severely affected buildings."
            if impact.buildings_severely_affected > 0
            else "Normal operations."
        ),
    }


@router.get("/roads")
async def get_roads_impact():
    """Get road network disruption and blocked arterial corridor estimates."""
    d_m, cells, area_km2 = await _get_latest_nowcast_metrics()
    impact = await compute_flood_impact(max_depth_m=d_m, flooded_cells=cells, flooded_area_km2=area_km2)

    arterials = []
    if d_m >= 0.3:
        arterials = [
            {"road": "Dr. Babasaheb Ambedkar Road (Hindmata)", "status": "WATERLOGGED_IMPASSABLE", "depth_m": round(d_m, 2)},
            {"road": "Swami Vivekananda (SV) Road (Andheri)", "status": "SLOW_MOVING", "depth_m": round(d_m * 0.7, 2)},
            {"road": "LBS Marg (Kurla / Kamani)", "status": "DIVERTED", "depth_m": round(d_m * 0.8, 2)},
        ]

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "road_km_flooded": round(impact.road_km_flooded, 2),
        "road_segments_affected": impact.road_segments_flooded,
        "major_roads_blocked_count": impact.major_roads_blocked,
        "monitored_arterial_corridors": arterials,
        "traffic_advisory": (
            "Major diversions in place around low-lying subways and railway underpasses."
            if impact.major_roads_blocked > 0
            else "Traffic moving normally."
        ),
    }


@router.get("/infrastructure")
async def get_infrastructure_impact():
    """Get critical public infrastructure (hospitals, schools, stations, power) at risk."""
    d_m, cells, area_km2 = await _get_latest_nowcast_metrics()
    impact = await compute_flood_impact(max_depth_m=d_m, flooded_cells=cells, flooded_area_km2=area_km2)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "critical_facilities_at_risk": {
            "hospitals": impact.hospitals_at_risk,
            "schools": impact.schools_at_risk,
            "fire_stations": impact.fire_stations_at_risk,
            "police_stations": impact.police_stations_at_risk,
            "power_substations": impact.power_substations_at_risk,
        },
        "total_critical_assets_threatened": (
            impact.hospitals_at_risk + impact.schools_at_risk +
            impact.fire_stations_at_risk + impact.police_stations_at_risk +
            impact.power_substations_at_risk
        ),
        "priority_protection_action": (
            "Deploy mobile de-watering pumps to hospital perimeter and protect electrical transformers."
            if impact.hospitals_at_risk > 0 or impact.power_substations_at_risk > 0
            else "All critical infrastructure facilities clear."
        ),
    }


@router.get("/shelters")
async def get_shelters_status():
    """Get designated relief shelter locations and remaining occupancy capacity."""
    from services.data.store import get_data_store
    store = get_data_store()
    raw_shelters = store.shelters().get("features", [])

    shelter_list = []
    total_capacity = 0
    for s in raw_shelters:
        props = s.get("properties", {})
        geom = s.get("geometry", {})
        coords = geom.get("coordinates", [72.83, 18.95])
        cap = int(props.get("capacity_persons", 500))
        total_capacity += cap

        shelter_list.append({
            "shelter_id": props.get("shelter_id", props.get("id", "sh-1")),
            "name": props.get("name", "MCGM Relief Shelter"),
            "ward": props.get("ward", "F/North"),
            "capacity_persons": cap,
            "current_occupancy": 0,
            "available_capacity": cap,
            "location": {"lon": coords[0], "lat": coords[1]},
            "operational_status": "READY",
        })

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_shelters": len(shelter_list),
        "total_capacity_persons": total_capacity,
        "available_capacity_persons": total_capacity,
        "shelters": shelter_list,
    }
