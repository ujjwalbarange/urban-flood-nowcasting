"""Spatially bounded 3D terrain heightfield extraction service for MUFNS.

Extracts real Copernicus GLO-30 DEM elevation grids for an active subarea
and its immediate surrounding context, avoiding transfer of the full 1800x1620
city-wide DEM to the browser.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from shapely.geometry import shape, Point
from shapely.prepared import prep
import structlog

from services.terrain.elevation_service import load_dem_array, DEM_METADATA
from services.spatial.hierarchy import get_hierarchy_engine

logger = structlog.get_logger()

# In-memory cache for bounded subarea 3D heightfields: { subarea_id: payload }
_subarea_terrain_cache: Dict[str, Dict[str, Any]] = {}


def extract_subarea_terrain_3d(
    subarea_id: str,
    target_grid_dim: int = 64,  # Adaptive high-perf 3D grid: 64x64 vertices (~4,096 vertices, <50KB)
    include_neighbors: bool = True,
    margin_factor: float = 0.25,
) -> Optional[Dict[str, Any]]:
    """Extract bounded 3D terrain elevation matrix for a subarea and surrounding context.

    Returns:
        Dictionary containing:
        - subarea_id, name, parent_ward_id
        - bounds: { min_lat, max_lat, min_lon, max_lon }
        - dimensions: { rows, cols, cell_size_m }
        - min_elevation_m, max_elevation_m
        - elevations: 2D array of elevation values in metres MSL (EGM96)
        - subarea_mask: 2D boolean array (True if cell is inside primary subarea)
        - neighbors: list of neighboring subarea summaries
    """
    cache_key = f"{subarea_id}_{target_grid_dim}_{include_neighbors}_{margin_factor}"
    if cache_key in _subarea_terrain_cache:
        return _subarea_terrain_cache[cache_key]

    engine = get_hierarchy_engine()
    subarea = engine.get_subarea(subarea_id)
    if subarea is None:
        logger.warning("Subarea not found for 3D terrain extraction", subarea_id=subarea_id)
        return None

    bounds = engine.get_context_bounds(
        subarea_id=subarea_id,
        include_neighbors=include_neighbors,
        margin_factor=margin_factor,
    )
    if bounds is None:
        return None

    dem = load_dem_array()
    full_rows, full_cols = dem.shape

    # Map geographic bounding box to DEM pixel indices
    # Row 0 = North (19.35), Row max = South (18.85)
    r_north = int((DEM_METADATA["north"] - bounds["max_lat"]) / (DEM_METADATA["north"] - DEM_METADATA["south"]) * full_rows)
    r_south = int((DEM_METADATA["north"] - bounds["min_lat"]) / (DEM_METADATA["north"] - DEM_METADATA["south"]) * full_rows)
    c_west = int((bounds["min_lon"] - DEM_METADATA["west"]) / (DEM_METADATA["east"] - DEM_METADATA["west"]) * full_cols)
    c_east = int((bounds["max_lon"] - DEM_METADATA["west"]) / (DEM_METADATA["east"] - DEM_METADATA["west"]) * full_cols)

    # Clamp to DEM dimensions
    r_min = max(0, min(r_north, r_south))
    r_max = min(full_rows, max(r_north, r_south) + 1)
    c_min = max(0, min(c_west, c_east))
    c_max = min(full_cols, max(c_west, c_east) + 1)

    cropped_raw = dem[r_min:r_max, c_min:c_max]
    if cropped_raw.size == 0:
        logger.error("Cropped DEM has 0 size", subarea_id=subarea_id, bounds=bounds)
        return None

    # Resample smoothly to target_grid_dim for optimal WebGL/Three.js rendering
    from PIL import Image
    im = Image.fromarray(cropped_raw)
    im_resized = im.resize((target_grid_dim, target_grid_dim), Image.Resampling.BILINEAR)
    grid_elev = np.array(im_resized, dtype=np.float32)

    # Replace extreme nodata with coastal elevation (~0.5m)
    grid_elev = np.where(grid_elev <= -100.0, 0.5, grid_elev)

    # Spatial mask: evaluate whether each resampled grid point falls inside the primary subarea
    poly = shape(subarea["geometry"])
    prep_poly = prep(poly)

    lons = np.linspace(bounds["min_lon"], bounds["max_lon"], target_grid_dim)
    lats = np.linspace(bounds["max_lat"], bounds["min_lat"], target_grid_dim)  # North to South

    mask = np.zeros((target_grid_dim, target_grid_dim), dtype=bool)
    for r in range(target_grid_dim):
        lat_val = float(lats[r])
        for c in range(target_grid_dim):
            pt = Point(float(lons[c]), lat_val)
            if prep_poly.contains(pt):
                mask[r, c] = True

    # Identify neighbors for contextual display
    neighbors = engine.get_neighbors(subarea_id)

    payload = {
        "subarea_id": subarea_id,
        "name": subarea["name"],
        "parent_ward_id": subarea["parent_ward_id"],
        "parent_ward_name": subarea["parent_ward_name"],
        "bounds": bounds,
        "dimensions": {
            "rows": target_grid_dim,
            "cols": target_grid_dim,
            "cell_size_lon": round((bounds["max_lon"] - bounds["min_lon"]) / target_grid_dim, 6),
            "cell_size_lat": round((bounds["max_lat"] - bounds["min_lat"]) / target_grid_dim, 6),
            "vertical_datum": "EGM96 Geoid (metres MSL)",
            "data_source": "Copernicus GLO-30 DSM (ESA)",
        },
        "min_elevation_m": round(float(np.min(grid_elev)), 2),
        "max_elevation_m": round(float(np.max(grid_elev)), 2),
        "mean_elevation_m": round(float(np.mean(grid_elev)), 2),
        "elevations": [[round(float(v), 2) for v in row] for row in grid_elev],
        "subarea_mask": mask.tolist(),
        "neighbors": [
            {
                "subarea_id": n["subarea_id"],
                "name": n["name"],
                "parent_ward_id": n["parent_ward_id"],
                "is_touching": n["is_touching"],
                "shared_boundary_length_m": n["shared_boundary_length_m"],
            }
            for n in neighbors[:8]  # Context immediate neighbors
        ],
    }

    _subarea_terrain_cache[cache_key] = payload
    return payload


def extract_city_terrain_3d(
    target_grid_dim: int = 96,
    bounds: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Extract citywide 3D terrain heightfield for Greater Mumbai from Copernicus GLO-30 DEM.

    Defaults to the entire supported study area (72.75E - 73.05E, 18.88N - 19.32N).
    Enforces physically consistent dimensions (width_m, height_m) to prevent vertical exaggeration artifacts.
    """
    if bounds is None:
        bounds = {
            "min_lon": 72.75,
            "max_lon": 73.05,
            "min_lat": 18.88,
            "max_lat": 19.32,
        }

    cache_key = f"citywide_{target_grid_dim}_{bounds['min_lon']}_{bounds['max_lon']}_{bounds['min_lat']}_{bounds['max_lat']}"
    if cache_key in _subarea_terrain_cache:
        return _subarea_terrain_cache[cache_key]

    dem = load_dem_array()
    full_rows, full_cols = dem.shape

    # Map geographic bounds to DEM indices
    r_north = int((DEM_METADATA["north"] - bounds["max_lat"]) / (DEM_METADATA["north"] - DEM_METADATA["south"]) * full_rows)
    r_south = int((DEM_METADATA["north"] - bounds["min_lat"]) / (DEM_METADATA["north"] - DEM_METADATA["south"]) * full_rows)
    c_west = int((bounds["min_lon"] - DEM_METADATA["west"]) / (DEM_METADATA["east"] - DEM_METADATA["west"]) * full_cols)
    c_east = int((bounds["max_lon"] - DEM_METADATA["west"]) / (DEM_METADATA["east"] - DEM_METADATA["west"]) * full_cols)

    r_min = max(0, min(r_north, r_south))
    r_max = min(full_rows, max(r_north, r_south) + 1)
    c_min = max(0, min(c_west, c_east))
    c_max = min(full_cols, max(c_west, c_east) + 1)

    cropped = dem[r_min:r_max, c_min:c_max]
    if cropped.size == 0:
        cropped = np.zeros((target_grid_dim, target_grid_dim), dtype=np.float32)

    from PIL import Image
    im = Image.fromarray(cropped)
    im_resized = im.resize((target_grid_dim, target_grid_dim), Image.Resampling.BILINEAR)
    grid_elev = np.array(im_resized, dtype=np.float32)

    # Ocean / NoData handling: Replace deep nodata or negative sea values with 0.0m MSL
    grid_elev = np.where(grid_elev < 0.0, 0.0, grid_elev)

    mid_lat = (bounds["min_lat"] + bounds["max_lat"]) / 2.0
    width_m = (bounds["max_lon"] - bounds["min_lon"]) * 111320.0 * np.cos(np.radians(mid_lat))
    height_m = (bounds["max_lat"] - bounds["min_lat"]) * 110700.0

    payload = {
        "is_citywide": True,
        "area_name": "Greater Mumbai Study Area (City-Wide)",
        "bounds": bounds,
        "dimensions": {
            "rows": target_grid_dim,
            "cols": target_grid_dim,
            "cell_size_lon": round((bounds["max_lon"] - bounds["min_lon"]) / target_grid_dim, 6),
            "cell_size_lat": round((bounds["max_lat"] - bounds["min_lat"]) / target_grid_dim, 6),
            "width_m": round(float(width_m), 1),
            "height_m": round(float(height_m), 1),
            "vertical_datum": "EGM96 Geoid (metres MSL)",
            "data_source": "Copernicus GLO-30 DSM (ESA)",
        },
        "min_elevation_m": round(float(np.min(grid_elev)), 2),
        "max_elevation_m": round(float(np.max(grid_elev)), 2),
        "mean_elevation_m": round(float(np.mean(grid_elev)), 2),
        "elevations": [[round(float(v), 2) for v in row] for row in grid_elev],
    }

    _subarea_terrain_cache[cache_key] = payload
    return payload


def clear_subarea_terrain_cache() -> None:
    """Clear cached 3D terrain grids."""
    _subarea_terrain_cache.clear()

