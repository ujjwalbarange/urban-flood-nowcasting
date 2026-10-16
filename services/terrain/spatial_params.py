"""Spatial parameter loader — replaces hardcoded assumptions with real PostGIS data.

Loads LULC classes, imperviousness fractions, and drainage nodes from the actual
database and maps them onto the simulation DEM grid.

This module is the Stage 2 replacement for:
    np.full(dem.shape, 0.80)  # hardcoded imperviousness

It instead queries PostGIS spatial data and builds per-cell parameter grids.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Optional, Tuple

import numpy as np
import structlog

logger = structlog.get_logger()


@dataclass
class SpatialParameters:
    """Container for spatially-varying simulation parameters.

    Each grid is aligned to the DEM grid (rows, cols) for the simulation catchment.
    """
    # Grid dimensions
    rows: int = 0
    cols: int = 0
    georef: dict = field(default_factory=dict)

    # From LULC
    manning_n: Optional[np.ndarray] = None        # Manning's roughness per cell
    imperviousness: Optional[np.ndarray] = None    # Impervious fraction per cell [0-1]
    cn_grid: Optional[np.ndarray] = None           # SCS Curve Number per cell

    # From Horton / soil
    horton_f0: Optional[np.ndarray] = None         # Initial infiltration rate mm/hr
    horton_fmin: Optional[np.ndarray] = None       # Minimum infiltration rate mm/hr
    horton_k: Optional[np.ndarray] = None          # Decay constant 1/hr

    # Metadata
    lulc_source: str = "unknown"
    imperviousness_source: str = "unknown"
    quality_status: str = "assumed"
    class_distribution: dict = field(default_factory=dict)
    coverage_pct: float = 0.0  # % of grid covered by real data


def build_spatial_parameters_from_db(
    georef: dict,
    grid_shape: Tuple[int, int],
    lulc_data: list[dict],
    imperviousness_data: list[dict],
) -> SpatialParameters:
    """Build spatial parameter grids from PostGIS query results.

    Args:
        georef: Dict with min_lat, max_lat, min_lon, max_lon, cell_size_m
        grid_shape: (rows, cols) of the simulation DEM grid
        lulc_data: List of dicts from land_use_land_cover table with geometry centroids
        imperviousness_data: List of dicts from impervious_surface_grid with geometry centroids
    """
    from services.config.lulc_params import LULC_PARAMS, DEFAULT_PARAMS

    rows, cols = grid_shape
    min_lat = georef["min_lat"]
    max_lat = georef["max_lat"]
    min_lon = georef["min_lon"]
    max_lon = georef["max_lon"]

    params = SpatialParameters(rows=rows, cols=cols, georef=georef)

    # Initialize with conservative urban defaults
    params.manning_n = np.full(grid_shape, DEFAULT_PARAMS["manning_n"], dtype=np.float32)
    params.imperviousness = np.full(grid_shape, DEFAULT_PARAMS["imperviousness"], dtype=np.float32)
    params.cn_grid = np.full(grid_shape, DEFAULT_PARAMS["cn"], dtype=np.float32)
    params.horton_f0 = np.full(grid_shape, DEFAULT_PARAMS["horton_f0_mmh"], dtype=np.float32)
    params.horton_fmin = np.full(grid_shape, DEFAULT_PARAMS["horton_fmin_mmh"], dtype=np.float32)
    params.horton_k = np.full(grid_shape, DEFAULT_PARAMS["horton_k_per_h"], dtype=np.float32)

    cells_covered = 0
    class_counts = {}

    # 1. Apply LULC-based parameters
    for lulc in lulc_data:
        lat = lulc.get("centroid_lat")
        lon = lulc.get("centroid_lon")
        class_code = lulc.get("class_code")

        if lat is None or lon is None or class_code is None:
            continue

        # Map to grid cell
        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
            row = int((max_lat - lat) / (max_lat - min_lat) * rows)
            col = int((lon - min_lon) / (max_lon - min_lon) * cols)
            row = max(0, min(rows - 1, row))
            col = max(0, min(cols - 1, col))

            p = LULC_PARAMS.get(class_code, DEFAULT_PARAMS)
            params.manning_n[row, col] = p["manning_n"]
            params.imperviousness[row, col] = p["imperviousness"]
            params.cn_grid[row, col] = p["cn"]
            params.horton_f0[row, col] = p["horton_f0_mmh"]
            params.horton_fmin[row, col] = p["horton_fmin_mmh"]
            params.horton_k[row, col] = p["horton_k_per_h"]

            cells_covered += 1
            cls_name = p.get("class", f"code_{class_code}")
            class_counts[cls_name] = class_counts.get(cls_name, 0) + 1

    # 2. Override imperviousness with direct grid data where available
    imp_cells_applied = 0
    for imp in imperviousness_data:
        lat = imp.get("centroid_lat")
        lon = imp.get("centroid_lon")
        frac = imp.get("impervious_fraction")

        if lat is None or lon is None or frac is None:
            continue

        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
            row = int((max_lat - lat) / (max_lat - min_lat) * rows)
            col = int((lon - min_lon) / (max_lon - min_lon) * cols)
            row = max(0, min(rows - 1, row))
            col = max(0, min(cols - 1, col))

            params.imperviousness[row, col] = float(frac)
            imp_cells_applied += 1

    total_cells = rows * cols
    params.coverage_pct = round(cells_covered / total_cells * 100, 1) if total_cells > 0 else 0.0
    params.class_distribution = class_counts
    params.lulc_source = "PostGIS:land_use_land_cover"
    params.imperviousness_source = f"PostGIS:impervious_surface_grid ({imp_cells_applied} cells applied)"
    params.quality_status = "assumed" if cells_covered > 0 else "default"

    logger.info(
        "Spatial parameters built from PostGIS",
        lulc_classes_applied=cells_covered,
        imp_cells_applied=imp_cells_applied,
        coverage_pct=params.coverage_pct,
        grid_shape=grid_shape,
        avg_imperviousness=round(float(np.mean(params.imperviousness)), 3),
        avg_manning_n=round(float(np.mean(params.manning_n)), 4),
    )

    return params


async def load_spatial_parameters_async(
    georef: dict,
    grid_shape: Tuple[int, int],
) -> SpatialParameters:
    """Load spatial parameters from the live PostGIS database.

    This is the async version that queries the database directly.
    Falls back to defaults if the database is unavailable.
    """
    from services.config.lulc_params import DEFAULT_PARAMS

    try:
        from services.database.connection import engine
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import text

        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as session:
            # Query LULC with centroids
            result = await session.execute(text("""
                SELECT class_code, class, ST_Y(ST_Centroid(geometry)) as centroid_lat,
                       ST_X(ST_Centroid(geometry)) as centroid_lon
                FROM land_use_land_cover
                WHERE geometry IS NOT NULL
            """))
            lulc_data = [dict(r._mapping) for r in result]

            # Query imperviousness with centroids
            result = await session.execute(text("""
                SELECT impervious_fraction, built_up_fraction,
                       ST_Y(ST_Centroid(geometry)) as centroid_lat,
                       ST_X(ST_Centroid(geometry)) as centroid_lon
                FROM impervious_surface_grid
                WHERE geometry IS NOT NULL
            """))
            imp_data = [dict(r._mapping) for r in result]

        logger.info(
            "Loaded spatial data from PostGIS",
            lulc_records=len(lulc_data),
            imperviousness_records=len(imp_data),
        )

        return build_spatial_parameters_from_db(georef, grid_shape, lulc_data, imp_data)

    except Exception as e:
        logger.warning(
            "Failed to load spatial parameters from PostGIS, using defaults",
            error=str(e),
        )
        # Return defaults
        rows, cols = grid_shape
        params = SpatialParameters(rows=rows, cols=cols, georef=georef)
        params.manning_n = np.full(grid_shape, DEFAULT_PARAMS["manning_n"], dtype=np.float32)
        params.imperviousness = np.full(grid_shape, DEFAULT_PARAMS["imperviousness"], dtype=np.float32)
        params.cn_grid = np.full(grid_shape, DEFAULT_PARAMS["cn"], dtype=np.float32)
        params.horton_f0 = np.full(grid_shape, DEFAULT_PARAMS["horton_f0_mmh"], dtype=np.float32)
        params.horton_fmin = np.full(grid_shape, DEFAULT_PARAMS["horton_fmin_mmh"], dtype=np.float32)
        params.horton_k = np.full(grid_shape, DEFAULT_PARAMS["horton_k_per_h"], dtype=np.float32)
        params.quality_status = "default_fallback"
        params.lulc_source = "default (PostGIS unavailable)"
        params.imperviousness_source = "default (PostGIS unavailable)"
        return params


def load_spatial_parameters_sync(
    georef: dict,
    grid_shape: Tuple[int, int],
) -> SpatialParameters:
    """Synchronous wrapper for loading spatial parameters.

    Suitable for use from background threads (e.g. simulation tasks).
    Uses asyncio.run() internally, falling back to defaults on any error.
    """
    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(load_spatial_parameters_async(georef, grid_shape))
        loop.close()
        return result
    except Exception as e:
        logger.warning("Sync spatial params load failed, using defaults", error=str(e))
        from services.config.lulc_params import DEFAULT_PARAMS
        rows, cols = grid_shape
        params = SpatialParameters(rows=rows, cols=cols, georef=georef)
        params.manning_n = np.full(grid_shape, DEFAULT_PARAMS["manning_n"], dtype=np.float32)
        params.imperviousness = np.full(grid_shape, DEFAULT_PARAMS["imperviousness"], dtype=np.float32)
        params.cn_grid = np.full(grid_shape, DEFAULT_PARAMS["cn"], dtype=np.float32)
        params.horton_f0 = np.full(grid_shape, DEFAULT_PARAMS["horton_f0_mmh"], dtype=np.float32)
        params.horton_fmin = np.full(grid_shape, DEFAULT_PARAMS["horton_fmin_mmh"], dtype=np.float32)
        params.horton_k = np.full(grid_shape, DEFAULT_PARAMS["horton_k_per_h"], dtype=np.float32)
        params.quality_status = "default_fallback"
        params.lulc_source = "default (sync load failed)"
        params.imperviousness_source = "default (sync load failed)"
        return params

