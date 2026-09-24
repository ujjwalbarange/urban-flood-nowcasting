"""Loader and georeferencing service for Mumbai Copernicus GLO-30 DEM."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple
import numpy as np
from PIL import Image
import structlog

logger = structlog.get_logger()

# Bounding box of the downloaded Copernicus DEM:
# west: 72.65, south: 18.85, east: 73.10, north: 19.35
DEM_BBOX = {
    "west": 72.65,
    "south": 18.85,
    "east": 73.10,
    "north": 19.35,
}

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEM_FILE = _PROJECT_ROOT / "data" / "raw" / "terrain" / "opentopography_cop30_mumbai_bbox.tif"

# Pre-defined regions of interest for fast hydraulic simulation
CATCHMENT_REGIONS = {
    "mithi_basin": {
        "name": "Mithi River Catchment (Kurla, Kalina, Airport, Powai)",
        "bounds": [72.83, 19.03, 72.93, 19.14], # [min_lon, min_lat, max_lon, max_lat]
    },
    "hindmata_dadar": {
        "name": "Hindmata / Dadar / Wadala Basin (Ward F/N, F/S)",
        "bounds": [72.82, 18.98, 72.87, 19.04],
    },
    "mumbai_city": {
        "name": "South & Central Mumbai (Island City)",
        "bounds": [72.80, 18.90, 72.88, 19.04],
    },
    "western_suburbs": {
        "name": "Western Suburbs (Bandra, Andheri, Milan Subway)",
        "bounds": [72.81, 19.05, 72.87, 19.16],
    },
    "mumbai_overview": {
        "name": "Mumbai Greater Metro (Subsampled)",
        "bounds": [72.75, 18.90, 72.98, 19.25],
    },
}

_dem_cache: Optional[np.ndarray] = None


def load_full_dem() -> np.ndarray:
    """Load full Copernicus DEM array into memory (cached)."""
    global _dem_cache
    if _dem_cache is not None:
        return _dem_cache

    if not DEM_FILE.exists():
        logger.error("DEM GeoTIFF not found", path=str(DEM_FILE))
        raise FileNotFoundError(f"DEM raster file not found at {DEM_FILE}")

    logger.info("Loading Copernicus GLO-30 DEM raster", path=str(DEM_FILE))
    im = Image.open(DEM_FILE)
    _dem_cache = np.array(im, dtype=np.float32)
    logger.info("DEM loaded", shape=_dem_cache.shape, min_elev=float(_dem_cache.min()), max_elev=float(_dem_cache.max()))
    return _dem_cache


def get_subgrid_for_bounds(
    min_lon: float, min_lat: float, max_lon: float, max_lat: float, max_dim: int = 150
) -> Tuple[np.ndarray, dict]:
    """Extract a DEM subgrid for given geographic bounds.
    
    Returns:
        (dem_grid, georef_metadata)
    """
    dem = load_full_dem()
    total_rows, total_cols = dem.shape
    
    # Clip to available DEM bounds
    min_lon = max(min_lon, DEM_BBOX["west"])
    max_lon = min(max_lon, DEM_BBOX["east"])
    min_lat = max(min_lat, DEM_BBOX["south"])
    max_lat = min(max_lat, DEM_BBOX["north"])

    # Calculate row and col indices
    # Row 0 is North (19.35), Row max is South (18.85)
    r_start = int((DEM_BBOX["north"] - max_lat) / (DEM_BBOX["north"] - DEM_BBOX["south"]) * total_rows)
    r_end = int((DEM_BBOX["north"] - min_lat) / (DEM_BBOX["north"] - DEM_BBOX["south"]) * total_rows)
    c_start = int((min_lon - DEM_BBOX["west"]) / (DEM_BBOX["east"] - DEM_BBOX["west"]) * total_cols)
    c_end = int((max_lon - DEM_BBOX["west"]) / (DEM_BBOX["east"] - DEM_BBOX["west"]) * total_cols)

    # Clamp indices
    r_start = max(0, min(r_start, total_rows - 2))
    r_end = max(r_start + 2, min(r_end, total_rows))
    c_start = max(0, min(c_start, total_cols - 2))
    c_end = max(c_start + 2, min(c_end, total_cols))

    subgrid = dem[r_start:r_end, c_start:c_end].copy()
    
    # Replace negative sea elevations with a stable low datum (0.2m)
    subgrid = np.maximum(subgrid, 0.2)

    # Subsample if too large for real-time 2D diffusive wave
    nrows, ncols = subgrid.shape
    step_r = max(1, int(np.ceil(nrows / max_dim)))
    step_c = max(1, int(np.ceil(ncols / max_dim)))
    
    if step_r > 1 or step_c > 1:
        subgrid = subgrid[::step_r, ::step_c]
    
    final_rows, final_cols = subgrid.shape
    cell_size_m = 30.0 * max(step_r, step_c)

    georef = {
        "min_lon": min_lon,
        "max_lon": max_lon,
        "min_lat": min_lat,
        "max_lat": max_lat,
        "rows": final_rows,
        "cols": final_cols,
        "cell_size_m": cell_size_m,
        "source": "Copernicus GLO-30 Digital Surface Model via OpenTopography",
    }
    
    return subgrid, georef


def get_catchment_dem(region_key: str = "mithi_basin", max_dim: int = 120) -> Tuple[np.ndarray, dict]:
    """Get georeferenced DEM for a predefined Mumbai catchment area."""
    if region_key not in CATCHMENT_REGIONS:
        region_key = "mithi_basin"
    
    region = CATCHMENT_REGIONS[region_key]
    bounds = region["bounds"]
    subgrid, georef = get_subgrid_for_bounds(bounds[0], bounds[1], bounds[2], bounds[3], max_dim=max_dim)
    georef["region_key"] = region_key
    georef["region_name"] = region["name"]
    return subgrid, georef


def depth_grid_to_geojson(
    depth_grid: np.ndarray,
    georef: dict,
    min_depth_m: float = 0.08,
    max_features: int = 1200,
) -> dict:
    """Convert a 2D water depth grid into a georeferenced GeoJSON FeatureCollection.

    Each polygon corresponds to a flooded cell above min_depth_m, with real WGS84
    coordinates, flood depth in metres, and risk classification.
    """
    rows, cols = depth_grid.shape
    d_lon = (georef["max_lon"] - georef["min_lon"]) / cols
    d_lat = (georef["max_lat"] - georef["min_lat"]) / rows

    features = []
    
    # Extract cells with significant water
    flooded_coords = np.argwhere(depth_grid >= min_depth_m)
    
    # If too many features, stride sample to keep GeoJSON payload fast and responsive
    if len(flooded_coords) > max_features:
        step = int(np.ceil(len(flooded_coords) / max_features))
        flooded_coords = flooded_coords[::step]

    for r, c in flooded_coords:
        depth = float(depth_grid[r, c])
        lat_top = round(georef["max_lat"] - r * d_lat, 6)
        lat_bot = round(lat_top - d_lat, 6)
        lon_left = round(georef["min_lon"] + c * d_lon, 6)
        lon_right = round(lon_left + d_lon, 6)

        if depth >= 1.0:
            severity = "critical"
            color = "#dc2626"
        elif depth >= 0.5:
            severity = "high"
            color = "#ea580c"
        elif depth >= 0.25:
            severity = "moderate"
            color = "#d97706"
        else:
            severity = "low"
            color = "#0284c7"

        poly_coords = [[
            [lon_left, lat_top],
            [lon_right, lat_top],
            [lon_right, lat_bot],
            [lon_left, lat_bot],
            [lon_left, lat_top],
        ]]

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": poly_coords,
            },
            "properties": {
                "water_depth_m": round(depth, 3),
                "severity": severity,
                "color": color,
                "grid_cell": [int(r), int(c)],
                "center_lat": round((lat_top + lat_bot) / 2.0, 6),
                "center_lon": round((lon_left + lon_right) / 2.0, 6),
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "feature_count": len(features),
        "georef": georef,
    }

