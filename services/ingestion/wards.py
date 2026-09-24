"""Ward boundary ingestion — download and load ward GeoJSON into PostGIS.

Mumbai ward boundaries (24 wards) are available from:
- Bharatlas (GeoJSON/SHP)
- OpenCity.in (KML)
- GitHub community repos

This module handles downloading, parsing, and inserting ward boundaries.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import httpx
import structlog
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

logger = structlog.get_logger()

# Known Mumbai ward boundary sources
BHARATLAS_MUMBAI_WARDS_URL = (
    "https://bharatlas.com/api/v1/data/wards_mumbai.geojson"
)

# Fallback: GitHub community repo
GITHUB_MUMBAI_GEOJSON_URL = (
    "https://raw.githubusercontent.com/sanjanakrishnan/mumbai_spatial_data/"
    "main/administrative_boundaries/mumbai_wards.geojson"
)


async def download_ward_boundaries(
    city_id: str,
    output_path: Path,
    source_url: Optional[str] = None,
) -> Path:
    """Download ward boundary GeoJSON for a city.

    Args:
        city_id: City identifier (used to pick source URL)
        output_path: Where to save the downloaded GeoJSON
        source_url: Override URL (if None, uses known sources)

    Returns:
        Path to downloaded GeoJSON file
    """
    if source_url is None:
        if city_id == "mumbai":
            source_url = BHARATLAS_MUMBAI_WARDS_URL
        else:
            raise ValueError(f"No known ward boundary source for city '{city_id}'")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Downloading ward boundaries", city=city_id, url=source_url)

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        response = await client.get(source_url)

        if response.status_code != 200:
            # Try fallback
            if city_id == "mumbai":
                logger.warning("Primary source failed, trying GitHub fallback")
                response = await client.get(GITHUB_MUMBAI_GEOJSON_URL)

        response.raise_for_status()

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(response.text)

    logger.info("Ward boundaries downloaded", path=str(output_path))
    return output_path


def parse_ward_geojson(geojson_path: Path) -> list[dict[str, Any]]:
    """Parse a ward boundary GeoJSON file into a list of ward records.

    Returns:
        List of dicts with keys: ward_id, name, geometry (Shapely), properties
    """
    with open(geojson_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    features = data.get("features", [])
    wards = []

    for i, feature in enumerate(features):
        props = feature.get("properties", {})
        geom = feature.get("geometry")

        if geom is None:
            logger.warning("Ward feature has no geometry", index=i)
            continue

        # Try to extract ward identifier from common property names
        ward_name = (
            props.get("ward_name")
            or props.get("WARD_NAME")
            or props.get("name")
            or props.get("NAME")
            or props.get("Ward")
            or props.get("ward")
            or props.get("WARDNAME")
            or f"ward_{i + 1}"
        )

        ward_id = (
            props.get("ward_id")
            or props.get("WARD_ID")
            or props.get("Ward_No")
            or props.get("ward_no")
            or ward_name.lower().replace(" ", "_").replace("/", "_")
        )

        try:
            shapely_geom = shape(geom)
            # Ensure MultiPolygon for consistency
            if shapely_geom.geom_type == "Polygon":
                from shapely.geometry import MultiPolygon
                shapely_geom = MultiPolygon([shapely_geom])

            area_sq_km = None
            if shapely_geom.is_valid:
                # Rough area in sq degrees → approximate sq km at Mumbai latitude
                # More accurate area should use projected CRS
                area_deg2 = shapely_geom.area
                # At ~19° N: 1° lat ≈ 111km, 1° lon ≈ 105km
                area_sq_km = round(area_deg2 * 111.0 * 105.0, 2)

            wards.append({
                "ward_id": str(ward_id),
                "name": str(ward_name),
                "geometry": shapely_geom,
                "geometry_geojson": mapping(shapely_geom),
                "area_sq_km": area_sq_km,
                "population": props.get("population") or props.get("POPULATION"),
                "properties": props,
            })
        except Exception as e:
            logger.warning("Failed to parse ward geometry", index=i, error=str(e))

    logger.info("Parsed ward boundaries", count=len(wards))
    return wards
