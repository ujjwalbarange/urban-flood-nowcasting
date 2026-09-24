"""Road network ingestion from OpenStreetMap via Overpass API.

Downloads road geometry for a city's bounding box and stores in PostGIS.
Used for:
1. Flood-aware evacuation routing
2. Road impact assessment
3. Imperviousness estimation (road surface = impervious)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import httpx
import structlog

logger = structlog.get_logger()

OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"

# OSM highway types we care about for flood routing
HIGHWAY_CLASSES = [
    "motorway", "trunk", "primary", "secondary", "tertiary",
    "motorway_link", "trunk_link", "primary_link", "secondary_link",
    "tertiary_link", "residential", "unclassified", "living_street",
]


def build_overpass_query(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    highway_classes: Optional[list[str]] = None,
) -> str:
    """Build an Overpass QL query for road network extraction.

    Returns roads as GeoJSON within the bounding box.
    """
    if highway_classes is None:
        highway_classes = HIGHWAY_CLASSES

    bbox = f"{min_lat},{min_lon},{max_lat},{max_lon}"
    highway_filter = "|".join(highway_classes)

    query = f"""
[out:json][timeout:120];
(
  way["highway"~"^({highway_filter})$"]({bbox});
);
out body;
>;
out skel qt;
"""
    return query.strip()


async def download_road_network(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    output_path: Path,
) -> Path:
    """Download road network from OSM Overpass API.

    Args:
        min_lon, min_lat, max_lon, max_lat: WGS84 bounding box
        output_path: Where to save the raw Overpass JSON

    Returns:
        Path to downloaded JSON file
    """
    query = build_overpass_query(min_lon, min_lat, max_lon, max_lat)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Downloading road network from OSM",
        bbox=f"[{min_lon},{min_lat},{max_lon},{max_lat}]",
    )

    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(
            OVERPASS_API_URL,
            data={"data": query},
        )
        response.raise_for_status()

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(response.text)

    data = json.loads(response.text)
    elements = data.get("elements", [])
    way_count = sum(1 for e in elements if e.get("type") == "way")

    logger.info(
        "Road network downloaded",
        total_elements=len(elements),
        ways=way_count,
        path=str(output_path),
    )
    return output_path


def parse_overpass_roads(overpass_json_path: Path) -> list[dict[str, Any]]:
    """Parse Overpass JSON into road segment records.

    Resolves node references to build LineString geometries.

    Returns:
        List of dicts with keys: segment_id, name, road_class, geometry_coords, osm_id, etc.
    """
    with open(overpass_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    elements = data.get("elements", [])

    # Build node lookup: id → (lon, lat)
    nodes = {}
    for el in elements:
        if el.get("type") == "node":
            nodes[el["id"]] = (el["lon"], el["lat"])

    # Build road segments from ways
    roads = []
    for el in elements:
        if el.get("type") != "way":
            continue

        tags = el.get("tags", {})
        node_ids = el.get("nodes", [])

        # Resolve node references to coordinates
        coords = []
        for nid in node_ids:
            if nid in nodes:
                coords.append(nodes[nid])

        if len(coords) < 2:
            continue  # Need at least 2 points for a line

        # Compute approximate length using Haversine
        length_m = _compute_line_length(coords)

        road_class = tags.get("highway", "unclassified")
        name = tags.get("name", "")
        speed_limit = _parse_speed_limit(tags.get("maxspeed"))

        roads.append({
            "segment_id": f"osm_{el['id']}",
            "osm_id": el["id"],
            "name": name,
            "road_class": road_class,
            "geometry_coords": coords,  # List of (lon, lat) tuples
            "length_m": round(length_m, 1),
            "speed_limit_kmh": speed_limit,
            "lanes": tags.get("lanes"),
            "surface": tags.get("surface"),
            "oneway": tags.get("oneway") == "yes",
        })

    logger.info("Parsed road segments", count=len(roads))
    return roads


def _compute_line_length(coords: list[tuple[float, float]]) -> float:
    """Compute approximate line length in metres using Haversine."""
    import math

    total = 0.0
    for i in range(len(coords) - 1):
        lon1, lat1 = coords[i]
        lon2, lat2 = coords[i + 1]
        total += _haversine_m(lat1, lon1, lat2, lon2)
    return total


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in metres."""
    import math

    R = 6371000  # Earth radius in metres
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _parse_speed_limit(maxspeed: Optional[str]) -> Optional[float]:
    """Parse OSM maxspeed tag to km/h float."""
    if not maxspeed:
        return None
    try:
        # Handle "50", "50 km/h", "30 mph"
        cleaned = maxspeed.replace("km/h", "").replace("mph", "").strip()
        val = float(cleaned)
        if "mph" in maxspeed:
            val *= 1.60934
        return round(val, 1)
    except (ValueError, TypeError):
        return None
