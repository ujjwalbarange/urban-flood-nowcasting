"""Elevation service for Copernicus GLO-30 DEM in Mumbai.

Provides:
- Exact ground elevation point lookup (meters MSL, EGM96 vertical datum)
- Elevation metadata (CRS, bounds, resolution, stats)
- 2D Topography color-mapped raster PNG generation for Leaflet ImageOverlay
- Preserves nodata cells as 100% transparent RGBA
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import numpy as np
from PIL import Image
import structlog

logger = structlog.get_logger()

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEM_FILE = _PROJECT_ROOT / "data" / "raw" / "terrain" / "opentopography_cop30_mumbai_bbox.tif"

# Exact Copernicus DEM bounds for Mumbai bounding box:
# West: 72.65, South: 18.85, East: 73.10, North: 19.35
# Resolution: 1 arc-second (~30m), EPSG:4326, 1800 rows x 1620 cols
DEM_METADATA = {
    "dataset": "Copernicus GLO-30 Digital Surface Model",
    "provider": "European Space Agency (ESA) / OpenTopography",
    "crs": "EPSG:4326",
    "vertical_datum": "EGM96 Geoid (Orthometric height in metres)",
    "units": "metres",
    "nominal_resolution_m": 30.0,
    "arc_second_resolution": 1.0,
    "west": 72.65,
    "south": 18.85,
    "east": 73.10,
    "north": 19.35,
    "rows": 1800,
    "cols": 1620,
    "nodata_value": None,
    "coverage": "Greater Mumbai, Salsette Island, Thane Creek, and Mumbai Harbour",
    "provenance": "Copernicus GLO-30 DSM via OpenTopography Global Datasets API",
}

_dem_array: Optional[np.ndarray] = None
_elevation_raster_cache: Optional[bytes] = None


def load_dem_array() -> np.ndarray:
    """Load the full Copernicus DEM into memory (cached)."""
    global _dem_array
    if _dem_array is not None:
        return _dem_array

    if not DEM_FILE.exists():
        logger.error("DEM file missing", path=str(DEM_FILE))
        raise FileNotFoundError(f"Copernicus DEM not found at {DEM_FILE}")

    im = Image.open(DEM_FILE)
    _dem_array = np.array(im, dtype=np.float32)
    logger.info(
        "Copernicus GLO-30 DEM loaded",
        shape=_dem_array.shape,
        min_elev=float(_dem_array.min()),
        max_elev=float(_dem_array.max()),
    )
    return _dem_array


def get_elevation_metadata() -> Dict[str, Any]:
    """Return verified metadata and summary statistics for Copernicus GLO-30."""
    dem = load_dem_array()
    valid_mask = dem > -100.0  # mask extreme nodata if any
    valid_elevs = dem[valid_mask]

    return {
        **DEM_METADATA,
        "actual_rows": int(dem.shape[0]),
        "actual_cols": int(dem.shape[1]),
        "min_elevation_m": round(float(valid_elevs.min()), 2),
        "max_elevation_m": round(float(valid_elevs.max()), 2),
        "mean_elevation_m": round(float(valid_elevs.mean()), 2),
        "median_elevation_m": round(float(np.median(valid_elevs)), 2),
        "coastal_cells_pct": round(float(np.sum(dem <= 2.0) / dem.size * 100), 2),
    }


def lookup_elevation(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """Look up exact terrain elevation in metres at a given WGS84 coordinate.

    Returns None if coordinate is outside coverage bounds.
    """
    if not (DEM_METADATA["west"] <= lon <= DEM_METADATA["east"] and
            DEM_METADATA["south"] <= lat <= DEM_METADATA["north"]):
        return None

    dem = load_dem_array()
    rows, cols = dem.shape

    # Row 0 is North (19.35), Row max is South (18.85)
    r = int((DEM_METADATA["north"] - lat) / (DEM_METADATA["north"] - DEM_METADATA["south"]) * rows)
    c = int((lon - DEM_METADATA["west"]) / (DEM_METADATA["east"] - DEM_METADATA["west"]) * cols)

    r = max(0, min(r, rows - 1))
    c = max(0, min(c, cols - 1))

    elev = float(dem[r, c])

    return {
        "latitude": round(lat, 6),
        "longitude": round(lon, 6),
        "elevation_m": round(elev, 2),
        "vertical_datum": DEM_METADATA["vertical_datum"],
        "units": "metres",
        "grid_resolution_m": 30.0,
        "is_coastal_lowland": elev <= 3.5,
        "is_depression": elev < 1.0,
        "provenance": "Copernicus GLO-30 DSM (ESA)",
    }


# Scientific Hypsometric Tinting Colormap for Urban Coastal Topography
# Elevation in meters -> RGBA (0-255)
# Designed for high contrast against flood water (blue) and basemaps
TOPOGRAPHY_COLORMAP = [
    # (elev_m, r, g, b, alpha)
    (-20.0, 30,  58, 138, 0),    # Sea bathymetry / Arabian Sea: transparent
    (  0.0, 30,  58, 138, 0),    # Sea level: transparent to show basemap coast
    (  0.5, 46, 125,  50, 150),  # Low coastal plain (0.5m - 5m): deep lush green
    (  5.0, 76, 175,  80, 160),  # Urban plain (5m - 15m): light grass green
    ( 15.0, 139, 195, 74, 170),  # Gentle terrace (15m - 30m): lime green
    ( 30.0, 255, 235, 59, 180),  # Low plateau (30m - 50m): pale yellow
    ( 50.0, 255, 179,  0, 190),  # Foot hills (50m - 100m): warm amber
    (100.0, 245, 124,  0, 200),  # Midland ridges (100m - 200m): orange-ochre
    (200.0, 165,  42, 42, 210),  # Uplands (200m - 350m): saddle brown
    (350.0, 120,  60, 40, 220),  # SGNP summits (350m - 450m): deep mountain brown
    (480.0, 220, 220, 220, 240), # Kanheri peak (>450m): stone gray
]


def render_elevation_raster(
    target_width: int = 810,
    target_height: int = 900,
) -> Tuple[bytes, Dict[str, Any]]:
    """Render full Copernicus DEM into a georeferenced RGBA PNG overlay for Leaflet.

    Returns:
        (png_bytes, georef_headers)
    """
    global _elevation_raster_cache
    if _elevation_raster_cache is not None and target_width == 810 and target_height == 900:
        headers = {
            "X-Georef-MinLat": str(DEM_METADATA["south"]),
            "X-Georef-MaxLat": str(DEM_METADATA["north"]),
            "X-Georef-MinLon": str(DEM_METADATA["west"]),
            "X-Georef-MaxLon": str(DEM_METADATA["east"]),
            "X-Min-Elevation": "0.0",
            "X-Max-Elevation": "488.6",
            "X-Elevation-Units": "metres",
        }
        return _elevation_raster_cache, headers

    dem = load_dem_array()
    orig_rows, orig_cols = dem.shape

    # Subsample / resize for fast browser rendering
    step_r = max(1, orig_rows // target_height)
    step_c = max(1, orig_cols // target_width)
    sub = dem[::step_r, ::step_c]
    rows, cols = sub.shape

    rgba = np.zeros((rows, cols, 4), dtype=np.uint8)

    # Vectorized colormap interpolation
    flat_elev = sub.flatten()
    r_chan = np.zeros_like(flat_elev, dtype=np.float32)
    g_chan = np.zeros_like(flat_elev, dtype=np.float32)
    b_chan = np.zeros_like(flat_elev, dtype=np.float32)
    a_chan = np.zeros_like(flat_elev, dtype=np.float32)

    # Segments
    for i in range(len(TOPOGRAPHY_COLORMAP) - 1):
        e0, r0, g0, b0, a0 = TOPOGRAPHY_COLORMAP[i]
        e1, r1, g1, b1, a1 = TOPOGRAPHY_COLORMAP[i + 1]

        mask = (flat_elev >= e0) & (flat_elev < e1)
        if not np.any(mask):
            continue

        frac = (flat_elev[mask] - e0) / (e1 - e0) if (e1 - e0) > 0 else 0
        r_chan[mask] = r0 + frac * (r1 - r0)
        g_chan[mask] = g0 + frac * (g1 - g0)
        b_chan[mask] = b0 + frac * (b1 - b0)
        a_chan[mask] = a0 + frac * (a1 - a0)

    # Beyond highest
    max_e, max_r, max_g, max_b, max_a = TOPOGRAPHY_COLORMAP[-1]
    high_mask = flat_elev >= max_e
    r_chan[high_mask] = max_r
    g_chan[high_mask] = max_g
    b_chan[high_mask] = max_b
    a_chan[high_mask] = max_a

    # Below sea level: keep completely transparent
    sea_mask = flat_elev <= 0.2
    a_chan[sea_mask] = 0

    rgba[:, :, 0] = r_chan.reshape((rows, cols)).astype(np.uint8)
    rgba[:, :, 1] = g_chan.reshape((rows, cols)).astype(np.uint8)
    rgba[:, :, 2] = b_chan.reshape((rows, cols)).astype(np.uint8)
    rgba[:, :, 3] = a_chan.reshape((rows, cols)).astype(np.uint8)

    img = Image.fromarray(rgba, mode="RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    png_bytes = buf.getvalue()

    if target_width == 810 and target_height == 900:
        _elevation_raster_cache = png_bytes

    headers = {
        "X-Georef-MinLat": str(DEM_METADATA["south"]),
        "X-Georef-MaxLat": str(DEM_METADATA["north"]),
        "X-Georef-MinLon": str(DEM_METADATA["west"]),
        "X-Georef-MaxLon": str(DEM_METADATA["east"]),
        "X-Min-Elevation": "0.0",
        "X-Max-Elevation": "488.6",
        "X-Elevation-Units": "metres",
    }
    return png_bytes, headers
