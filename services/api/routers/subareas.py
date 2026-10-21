"""FastAPI Router for Phase 4: Adaptive Subarea-Based 3D Flood Simulation & Evacuation Routing.

Provides endpoints for:
- Dynamic subarea hierarchy and neighbor discovery
- Spatially bounded 3D terrain heightfield extraction (Copernicus DEM)
- Spatially bounded 3D flood depth & water-surface elevation matrices (2D Diffusive Wave)
- Eligible candidate evacuation destinations (BMC shelters & hospitals)
- Flood-impeded evacuation routing (FIGER v1.0)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
import structlog

from services.spatial.hierarchy import get_hierarchy_engine
from services.terrain.subarea_3d import extract_subarea_terrain_3d, extract_city_terrain_3d
from services.flood.subarea_flood3d import extract_subarea_flood_3d, extract_city_flood_3d
from services.buildings.building_3d import extract_subarea_buildings_3d, extract_city_buildings_3d
from services.routing.evacuation_engine import get_evacuation_routing_engine

logger = structlog.get_logger()
router = APIRouter(prefix="/subareas", tags=["Adaptive Subarea 3D & Routing"])


class RouteRequest(BaseModel):
    destination_id: Optional[str] = Field(None, description="Optional target destination ID from eligible list")
    dest_lon: Optional[float] = Field(None, description="Optional custom destination longitude")
    dest_lat: Optional[float] = Field(None, description="Optional custom destination latitude")
    destination_name: Optional[str] = Field(None, description="Optional custom destination name")
    origin_lon: Optional[float] = Field(None, description="Optional custom origin lon (defaults to subarea centroid)")
    origin_lat: Optional[float] = Field(None, description="Optional custom origin lat (defaults to subarea centroid)")
    vehicle_type: str = Field("car", description="Vehicle type: 'car' or 'pedestrian'")


class PointRouteRequest(BaseModel):
    origin_lon: float = Field(..., description="Clicked origin longitude")
    origin_lat: float = Field(..., description="Clicked origin latitude")
    destination_id: Optional[str] = Field(None, description="Optional chosen destination ID")
    vehicle_type: str = Field("standard_car", description="Vehicle type: 'standard_car', 'emergency_high_clearance', or 'pedestrian'")
    max_search_radius_km: float = Field(12.0, ge=1.0, le=25.0, description="Max search radius in km")


@router.get("/city-terrain-3d")
async def get_city_terrain_3d_endpoint(
    target_dim: int = Query(96, ge=32, le=128, description="Grid resolution for 3D mesh (default 96x96)"),
):
    """Extract citywide 3D terrain heightfield (Copernicus DEM) covering Greater Mumbai."""
    return extract_city_terrain_3d(target_grid_dim=target_dim)


@router.get("/city-flood-3d")
async def get_city_flood_3d_endpoint(
    target_dim: int = Query(96, ge=32, le=128, description="Grid resolution for 3D mesh (default 96x96)"),
    minute: Optional[str] = Query(None, description="Optional timeline timestep minute"),
):
    """Extract citywide simulated 2D flood depth and calculate 3D water-surface elevation."""
    parsed_minute: Optional[int] = None
    if minute is not None and str(minute).strip() not in ("", "undefined", "null", "none"):
        try:
            parsed_minute = int(minute)
        except (ValueError, TypeError):
            parsed_minute = None
    return extract_city_flood_3d(target_grid_dim=target_dim, timeline_minute=parsed_minute)


@router.get("/city-buildings-3d")
async def get_city_buildings_3d_endpoint(
    limit: int = Query(180, ge=10, le=500, description="Max building footprints to extract"),
):
    """Extract representative 3D building footprints across Greater Mumbai with terrain base heights."""
    return extract_city_buildings_3d(limit=limit)


@router.get("/destinations-near")
async def get_destinations_near_point_endpoint(
    lon: float = Query(..., description="Origin longitude"),
    lat: float = Query(..., description="Origin latitude"),
    max_radius_km: float = Query(12.0, ge=1.0, le=25.0, description="Search radius in kilometers"),
    limit: int = Query(10, ge=1, le=50, description="Max destinations to return"),
):
    """Discover and rank candidate evacuation destinations (BMC shelters & hospitals) near any clicked map point."""
    router_eng = get_evacuation_routing_engine()
    candidates = router_eng.get_destinations_near_point(lon=lon, lat=lat, max_search_radius_km=max_radius_km, limit=limit)
    return {
        "origin": [lon, lat],
        "count": len(candidates),
        "destinations": candidates,
        "disclaimer": "Candidate destinations ranked by modeled flood safety and road proximity. Always heed official BMC disaster directives.",
    }


@router.post("/point-evacuation-route")
async def compute_point_evacuation_route(req: PointRouteRequest):
    """Compute a flood-impeded evacuation corridor from any clicked point on the map.

    Evaluates real road connectivity (14,563 segments) and samples flood depth to calculate
    optimal traversable route with passability classification and non-guaranteed safety disclaimer.
    """
    router_eng = get_evacuation_routing_engine()
    route_res = router_eng.find_safest_evacuation_from_point(
        origin_lon=req.origin_lon,
        origin_lat=req.origin_lat,
        vehicle_type=req.vehicle_type,
        destination_id=req.destination_id,
        max_search_radius_km=req.max_search_radius_km,
    )
    return route_res


@router.post("/check-route-staleness")
async def check_evacuation_route_staleness(route_payload: Dict[str, Any]):
    """Evaluate whether an active evacuation route is stale due to updated simulation flood outputs."""
    router_eng = get_evacuation_routing_engine()
    return router_eng.check_route_staleness(route_payload)


@router.get("")
async def list_all_subareas(
    ward: Optional[str] = Query(None, description="Filter subareas by parent ward ID (e.g. 'A', 'KE', 'GN')"),
):
    """List all dynamically discovered subareas across Mumbai wards.

    Never hardcodes subarea names, counts, or arrangements.
    """
    engine = get_hierarchy_engine()
    subareas = engine.list_subareas(ward_filter=ward)
    return {
        "type": "SubareaCollection",
        "total": len(subareas),
        "source": "Brihanmumbai Municipal Corporation (BMC) / Census 2011 Partition",
        "subareas": subareas,
    }


@router.get("/hierarchy-validation")
async def get_hierarchy_validation():
    """Validate spatial consistency, unique IDs, and geometry validity across all subareas."""
    engine = get_hierarchy_engine()
    return engine.validate_hierarchy()


@router.get("/{subarea_id}")
async def get_subarea_details(subarea_id: str):
    """Get full geometry, parent ward, centroid, and topological neighbors for a subarea."""
    engine = get_hierarchy_engine()
    subarea = engine.get_subarea(subarea_id)
    if subarea is None:
        raise HTTPException(status_code=404, detail=f"Subarea '{subarea_id}' not found.")

    neighbors = engine.get_neighbors(subarea_id)
    return {
        **subarea,
        "neighbor_count": len(neighbors),
        "neighbors": neighbors,
    }


@router.get("/{subarea_id}/terrain3d")
async def get_subarea_terrain_3d_endpoint(
    subarea_id: str,
    target_dim: int = Query(64, ge=32, le=128, description="Grid resolution for 3D mesh (default 64x64)"),
    include_neighbors: bool = Query(True, description="Include neighboring subareas for contextual scene"),
):
    """Extract bounded 3D terrain heightfield (Copernicus DEM) for active subarea + context."""
    terrain = extract_subarea_terrain_3d(
        subarea_id=subarea_id,
        target_grid_dim=target_dim,
        include_neighbors=include_neighbors,
    )
    if terrain is None:
        raise HTTPException(status_code=404, detail=f"Terrain could not be extracted for subarea '{subarea_id}'.")
    return terrain


@router.get("/{subarea_id}/flood3d")
async def get_subarea_flood_3d_endpoint(
    subarea_id: str,
    target_dim: int = Query(64, ge=32, le=128, description="Grid resolution for 3D mesh (default 64x64)"),
    minute: Optional[str] = Query(None, description="Optional timeline timestep minute"),
):
    """Extract genuine simulated 2D flood depth and calculate 3D water-surface elevation.

    z_water = z_terrain + depth (for depth >= 0.01m). Dry cells are transparent/zero.
    """
    parsed_minute: Optional[int] = None
    if minute is not None and str(minute).strip() not in ("", "undefined", "null", "none"):
        try:
            parsed_minute = int(minute)
        except (ValueError, TypeError):
            parsed_minute = None
    flood_data = extract_subarea_flood_3d(
        subarea_id=subarea_id,
        target_grid_dim=target_dim,
        timeline_minute=parsed_minute,
    )
    return flood_data


@router.get("/{subarea_id}/buildings-3d")
async def get_subarea_buildings_3d_endpoint(
    subarea_id: str,
    limit: int = Query(150, ge=10, le=500, description="Max building footprints to extract"),
):
    """Extract 3D building footprints for the active subarea with DEM terrain base heights."""
    return extract_subarea_buildings_3d(subarea_id=subarea_id, limit=limit)


@router.get("/{subarea_id}/destinations")
async def get_subarea_destinations(
    subarea_id: str,
    max_radius_km: float = Query(8.0, ge=1.0, le=25.0, description="Search radius in kilometers"),
):
    """Discover and rank authoritative candidate evacuation destinations for the subarea.

    Includes verified BMC flood shelters and major emergency medical hospitals.
    Evaluates current modeled flood depth at each candidate.
    """
    router_eng = get_evacuation_routing_engine()
    candidates = router_eng.get_eligible_destinations(subarea_id=subarea_id, max_search_radius_km=max_radius_km)
    return {
        "subarea_id": subarea_id,
        "eligible_destinations_count": len(candidates),
        "destinations": candidates,
        "disclaimer": "Candidate destinations ranked by modeled flood safety and road proximity. Always heed official BMC disaster directives.",
    }


@router.post("/{subarea_id}/evacuation-route")
async def compute_subarea_evacuation_route(
    subarea_id: str,
    req: RouteRequest,
):
    """Compute a flood-impeded evacuation corridor from subarea to designated destination.

    Uses real road geometry (14,563 segments) and samples flood depth to calculate
    optimal traversable route with passability classification.
    """
    engine = get_hierarchy_engine()
    subarea = engine.get_subarea(subarea_id)
    if subarea is None:
        raise HTTPException(status_code=404, detail=f"Subarea '{subarea_id}' not found.")

    router_eng = get_evacuation_routing_engine()

    # Determine origin coordinates (custom origin or subarea centroid)
    orig_lon = req.origin_lon if req.origin_lon is not None else subarea["centroid"][0]
    orig_lat = req.origin_lat if req.origin_lat is not None else subarea["centroid"][1]

    # Determine destination coordinates
    dest_lon = req.dest_lon
    dest_lat = req.dest_lat
    dest_name = req.destination_name or "Designated Emergency Shelter"

    if (dest_lon is None or dest_lat is None) and req.destination_id:
        # Resolve destination from candidate list
        candidates = router_eng.get_eligible_destinations(subarea_id=subarea_id)
        for c in candidates:
            if c["destination_id"] == req.destination_id:
                dest_lon, dest_lat = c["coordinates"][0], c["coordinates"][1]
                dest_name = c["name"]
                break

    if dest_lon is None or dest_lat is None:
        # Default to the top-ranked eligible candidate destination
        candidates = router_eng.get_eligible_destinations(subarea_id=subarea_id)
        if candidates:
            top = candidates[0]
            dest_lon, dest_lat = top["coordinates"][0], top["coordinates"][1]
            dest_name = top["name"]
        else:
            raise HTTPException(status_code=400, detail="No eligible candidate destinations reachable in search radius.")

    route_res = router_eng.compute_evacuation_route(
        origin_lon=orig_lon,
        origin_lat=orig_lat,
        dest_lon=dest_lon,
        dest_lat=dest_lat,
        destination_name=dest_name,
        vehicle_type=req.vehicle_type,
    )
    return {
        "subarea_id": subarea_id,
        "subarea_name": subarea["name"],
        **route_res,
    }
