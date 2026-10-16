"""Drainage Network and Hydraulic Surcharge API Router.

Provides real-time visibility into Mumbai's stormwater drainage network (BRIMSTOWAD),
monitoring network capacity utilization, outfall tidal locking, pipe surcharge risks,
and storm water pumping station (SWPS) status.

Phase 2E-3: Drainage status and surcharge evaluation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.data.store import get_data_store
from services.coastal.tide_service import (
    TideService,
    MUMBAI_DATUM_OFFSET_M,
    MUMBAI_MHWS_M_CD,
    MUMBAI_MHWN_M_CD,
)
from services.database.connection import verify_db_connectivity

logger = structlog.get_logger()
router = APIRouter(prefix="/drainage", tags=["Drainage & SWMM"])

_tide_service = TideService()

# 8 Major Mumbai Storm Water Pumping Stations (SWPS - BRIMSTOWAD)
MUMBAI_SWPS_FACILITIES = [
    {
        "station_id": "swps-01",
        "name": "Love Grove Pumping Station",
        "ward": "G/South",
        "location": {"lat": 18.9983, "lon": 72.8152},
        "num_pumps": 8,
        "capacity_cumecs": 48.0,
        "catchment": "Worli, Prabhadevi, Lower Parel",
        "outfall_waterbody": "Arabian Sea",
        "flood_gates": "Automated flap gates + sluice gates",
        "status": "OPERATIONAL",
    },
    {
        "station_id": "swps-02",
        "name": "Cleveland Bunder Pumping Station",
        "ward": "G/South",
        "location": {"lat": 19.0062, "lon": 72.8184},
        "num_pumps": 7,
        "capacity_cumecs": 42.0,
        "catchment": "Dadar West, Worli Koliwada",
        "outfall_waterbody": "Mahim Bay / Arabian Sea",
        "flood_gates": "Automated sluice gates",
        "status": "OPERATIONAL",
    },
    {
        "station_id": "swps-03",
        "name": "Haji Ali Pumping Station",
        "ward": "D",
        "location": {"lat": 18.9782, "lon": 72.8091},
        "num_pumps": 6,
        "capacity_cumecs": 36.0,
        "catchment": "Tardeo, Breach Candy, Peddar Road",
        "outfall_waterbody": "Arabian Sea",
        "flood_gates": "Hydraulic crest gates",
        "status": "OPERATIONAL",
    },
    {
        "station_id": "swps-04",
        "name": "Britannia Pumping Station",
        "ward": "E",
        "location": {"lat": 18.9663, "lon": 72.8481},
        "num_pumps": 6,
        "capacity_cumecs": 36.0,
        "catchment": "Hindmata, Dadar TT, Parel, Byculla",
        "outfall_waterbody": "Thane Creek / Mumbai Harbour",
        "flood_gates": "Automated vertical gates",
        "status": "OPERATIONAL",
    },
    {
        "station_id": "swps-05",
        "name": "Irla Pumping Station",
        "ward": "K/West",
        "location": {"lat": 19.1128, "lon": 72.8364},
        "num_pumps": 8,
        "capacity_cumecs": 48.0,
        "catchment": "Vile Parle, Juhu, Andheri West",
        "outfall_waterbody": "Arabian Sea / Irla Nullah",
        "flood_gates": "Radial gates + trash racks",
        "status": "OPERATIONAL",
    },
    {
        "station_id": "swps-06",
        "name": "Gazdarband Pumping Station",
        "ward": "H/West",
        "location": {"lat": 19.0834, "lon": 72.8276},
        "num_pumps": 6,
        "capacity_cumecs": 36.0,
        "catchment": "Santacruz West, Khar, Bandra",
        "outfall_waterbody": "Arabian Sea",
        "flood_gates": "Vertical lift gates",
        "status": "OPERATIONAL",
    },
    {
        "station_id": "swps-07",
        "name": "Mahabali Pumping Station (Mithi Confluence)",
        "ward": "L",
        "location": {"lat": 19.0620, "lon": 72.8680},
        "num_pumps": 4,
        "capacity_cumecs": 24.0,
        "catchment": "Kurla, Kalina, BKC",
        "outfall_waterbody": "Mithi River / Mahim Creek",
        "flood_gates": "Dual flap check gates",
        "status": "OPERATIONAL",
    },
    {
        "station_id": "swps-08",
        "name": "Mograne Pumping Station",
        "ward": "K/East",
        "location": {"lat": 19.1245, "lon": 72.8612},
        "num_pumps": 4,
        "capacity_cumecs": 24.0,
        "catchment": "Andheri East, MIDC, Jogeshwari",
        "outfall_waterbody": "Mogra Nullah / Oshiwara River",
        "flood_gates": "Automated sluice gates",
        "status": "OPERATIONAL",
    },
]


@router.get("/status")
async def get_drainage_status():
    """Get high-level status of the stormwater drainage network and facilities."""
    store = get_data_store()
    nodes = store.drainage_nodes().get("features", [])
    links = store.drainage_links().get("features", [])
    outfalls = store.drainage_outfalls().get("features", [])

    # Estimate current tide to determine tidal lock impact
    now = datetime.now(timezone.utc)
    tide_rec = await _tide_service.build_tide_schedule("rainfall_normal_tide", duration_hours=1.0)
    current_tide_msl = tide_rec.mean_tide_m_msl

    # Surcharged outfalls: outfall invert elevation < current sea level
    surcharged_outfalls = 0
    for of in outfalls:
        props = of.get("properties", {})
        invert = float(props.get("invert_elevation_m", 0.5))
        if current_tide_msl > invert:
            surcharged_outfalls += 1

    total_pump_capacity = sum(s["capacity_cumecs"] for s in MUMBAI_SWPS_FACILITIES)
    total_pumps = sum(s["num_pumps"] for s in MUMBAI_SWPS_FACILITIES)

    return {
        "status": "operational",
        "timestamp": now.isoformat(),
        "network_metrics": {
            "total_nodes": len(nodes),
            "total_links": len(links),
            "total_outfalls": len(outfalls),
            "outfalls_tidally_locked": surcharged_outfalls,
            "outfalls_free_flowing": max(0, len(outfalls) - surcharged_outfalls),
        },
        "pumping_infrastructure": {
            "total_stations": len(MUMBAI_SWPS_FACILITIES),
            "total_pumps": total_pumps,
            "total_capacity_cumecs": total_pump_capacity,
            "stations_operational": len(MUMBAI_SWPS_FACILITIES),
        },
        "coastal_boundary": {
            "current_sea_level_m_msl": round(current_tide_msl, 2),
            "tidal_locking_level": "MODERATE" if surcharged_outfalls > 0 else "LOW",
        },
    }


@router.get("/surcharge")
async def get_surcharge_analysis(
    rainfall_intensity_mmh: float = Query(
        default=25.0,
        ge=0.0,
        le=300.0,
        description="Current or hypothetical rainfall intensity for surcharge evaluation",
    ),
):
    """Identify drainage nodes and conduit links at imminent risk of hydraulic surcharge."""
    store = get_data_store()
    links = store.drainage_links().get("features", [])
    nodes = store.drainage_nodes().get("features", [])

    surcharged_links = []
    # Design capacity benchmark: BMC drains are historically designed for 25 mm/h
    # When rainfall > 25 mm/h, older culverts and brick arch drains surcharge
    design_capacity_mmh = 25.0
    utilization_ratio = round(rainfall_intensity_mmh / design_capacity_mmh, 2)

    for i, link in enumerate(links[:50]):
        props = link.get("properties", {})
        link_id = props.get("link_id", f"link_{i}")
        diameter_m = float(props.get("diameter_m", 1.2))
        
        # Link capacity ratio
        link_cap = 25.0 * (diameter_m / 1.0)
        link_util = min(2.5, round(rainfall_intensity_mmh / max(5.0, link_cap), 2))
        is_surcharged = link_util >= 1.0
        
        if is_surcharged or link_util >= 0.8:
            surcharged_links.append({
                "link_id": link_id,
                "from_node": props.get("from_node", ""),
                "to_node": props.get("to_node", ""),
                "diameter_m": diameter_m,
                "utilization_ratio": link_util,
                "surcharged": is_surcharged,
                "risk_level": "CRITICAL" if link_util >= 1.2 else "HIGH" if link_util >= 1.0 else "WARNING",
            })

    return {
        "evaluation_timestamp": datetime.now(timezone.utc).isoformat(),
        "rainfall_intensity_mmh": rainfall_intensity_mmh,
        "design_standard_mmh": design_capacity_mmh,
        "overall_utilization_ratio": utilization_ratio,
        "surcharged_links_count": len([l for l in surcharged_links if l["surcharged"]]),
        "bottlenecks_identified": surcharged_links[:20],
        "advisory": (
            "Severe surcharge detected across trunk drains. Flap gates and pumping stations must operate at full capacity."
            if utilization_ratio > 1.2
            else "Drainage operating within nominal capacity. Standard gravity flow active."
        ),
    }


@router.get("/outfalls")
async def get_drainage_outfalls():
    """Get detailed list of tidal outfalls with invert elevation and locking state."""
    store = get_data_store()
    raw_outfalls = store.drainage_outfalls().get("features", [])

    # Current tide MSL
    tide_rec = await _tide_service.build_tide_schedule("rainfall_normal_tide", duration_hours=1.0)
    current_tide_msl = tide_rec.mean_tide_m_msl

    outfalls_list = []
    for of in raw_outfalls:
        props = of.get("properties", {})
        geom = of.get("geometry", {})
        coords = geom.get("coordinates", [72.83, 18.95])
        invert = float(props.get("invert_elevation_m", 0.6))
        is_locked = current_tide_msl > invert

        outfalls_list.append({
            "outfall_id": props.get("outfall_id", props.get("id", "of-unknown")),
            "name": props.get("name", "Stormwater Outfall"),
            "location": {"lon": coords[0], "lat": coords[1]},
            "waterbody": props.get("waterbody", "Arabian Sea"),
            "invert_elevation_m_msl": invert,
            "current_sea_level_m_msl": round(current_tide_msl, 2),
            "is_tidally_locked": is_locked,
            "discharge_status": "LOCKED_BACKFLOW_PREVENTED" if is_locked else "FREE_DISCHARGE",
        })

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "count": len(outfalls_list),
        "current_tide_msl": round(current_tide_msl, 2),
        "outfalls": outfalls_list,
    }


@router.get("/pumping-stations")
async def get_pumping_stations():
    """Get the 8 major storm water pumping stations in Mumbai and their operational status."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_stations": len(MUMBAI_SWPS_FACILITIES),
        "total_capacity_cumecs": sum(s["capacity_cumecs"] for s in MUMBAI_SWPS_FACILITIES),
        "stations": MUMBAI_SWPS_FACILITIES,
    }
