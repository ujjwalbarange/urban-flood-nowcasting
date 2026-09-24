"""DEM ingestion — download, validate, reproject, normalize.

Supports:
- Copernicus GLO-30 (via OpenTopography API)
- SRTM 30m (via USGS EarthExplorer / OpenTopography)
- CartoDEM (manual download from Bhuvan, ingested from local file)

The ingestion pipeline:
1. Download / locate source DEM GeoTIFF
2. Validate: CRS, resolution, nodata, bounds
3. Clip to city bounding box
4. Reproject to city's projected CRS (e.g. EPSG:32643)
5. Resample to simulation cell size (bilinear for continuous elevation)
6. Store: GeoTIFF in object storage, metadata in PostGIS
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

import httpx
import numpy as np
import structlog

logger = structlog.get_logger()

# OpenTopography API for Copernicus GLO-30 DEM
OPENTOPO_API_URL = "https://portal.opentopography.org/API/globaldem"
OPENTOPO_DEM_TYPE = "COP30"  # Copernicus GLO-30


async def download_copernicus_dem(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    output_path: Path,
    api_key: Optional[str] = None,
) -> Path:
    """Download Copernicus GLO-30 DEM tile from OpenTopography.

    Args:
        min_lon, min_lat, max_lon, max_lat: WGS84 bounding box
        output_path: Where to save the downloaded GeoTIFF
        api_key: OpenTopography API key. Falls back to OPENTOPOGRAPHY_API_KEY.

    Returns:
        Path to downloaded GeoTIFF file
    """
    api_key = api_key or os.getenv("OPENTOPOGRAPHY_API_KEY")
    if not api_key:
        raise ValueError("OpenTopography requires OPENTOPOGRAPHY_API_KEY")
    if not (-180 <= min_lon < max_lon <= 180 and -90 <= min_lat < max_lat <= 90):
        raise ValueError("Invalid WGS84 bounding box")

    params = {
        "demtype": OPENTOPO_DEM_TYPE,
        "south": min_lat,
        "north": max_lat,
        "west": min_lon,
        "east": max_lon,
        "outputFormat": "GTiff",
    }
    params["API_Key"] = api_key

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Downloading Copernicus GLO-30 DEM",
        bbox=f"[{min_lon},{min_lat},{max_lon},{max_lat}]",
        output=str(output_path),
    )

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.get(OPENTOPO_API_URL, params=params)
    except httpx.RequestError:
        # httpx exceptions may include the fully encoded request URL (including API_Key).
        raise RuntimeError("OpenTopography request failed; request details were withheld") from None

    if response.status_code != 200:
        # Avoid surfacing response bodies that can echo request details or account information.
        raise RuntimeError(
            f"OpenTopography returned HTTP {response.status_code}; response details were withheld"
        )
    content = response.content
    if len(content) < 8 or content[:4] not in (b"II*\x00", b"MM\x00*"):
        raise ValueError("OpenTopography response is not a GeoTIFF; response body was withheld")

    # Write atomically so a failed/interrupted transfer cannot masquerade as a complete DEM.
    temporary_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=output_path.parent, prefix=f".{output_path.name}.", delete=False
        ) as temp_file:
            temporary_path = Path(temp_file.name)
            temp_file.write(content)
        temporary_path.replace(output_path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info(
        "DEM downloaded",
        size_mb=round(file_size_mb, 2),
        path=str(output_path),
    )
    return output_path


def validate_dem(dem_path: Path) -> dict:
    """Validate a DEM GeoTIFF file.

    Checks:
    - File exists and is readable
    - Has valid CRS
    - Has reasonable resolution
    - Has valid nodata handling
    - Has non-empty data

    Returns:
        Validation report dict
    """
    import rasterio

    report = {
        "valid": False,
        "path": str(dem_path),
        "errors": [],
        "warnings": [],
    }

    if not dem_path.exists():
        report["errors"].append(f"File not found: {dem_path}")
        return report

    try:
        with rasterio.open(dem_path) as src:
            report["crs"] = str(src.crs)
            report["crs_epsg"] = src.crs.to_epsg() if src.crs else None
            report["width"] = src.width
            report["height"] = src.height
            report["bounds"] = {
                "left": src.bounds.left,
                "bottom": src.bounds.bottom,
                "right": src.bounds.right,
                "top": src.bounds.top,
            }
            report["resolution"] = src.res
            report["nodata"] = src.nodata
            report["dtype"] = str(src.dtypes[0])
            report["band_count"] = src.count

            # Check CRS
            if src.crs is None:
                report["errors"].append("No CRS defined")
            elif src.crs.to_epsg() not in [4326, 32643, 32644, 32645]:
                report["warnings"].append(f"Unexpected CRS: {src.crs}")

            # Check resolution (should be ~30m or ~0.00028° for GLO-30)
            res_x, res_y = src.res
            if src.crs and src.crs.is_geographic:
                # Geographic CRS: resolution in degrees
                approx_m = res_x * 111000  # rough deg→m at equator
                report["approx_resolution_m"] = round(approx_m, 1)
                if approx_m > 100:
                    report["warnings"].append(f"Resolution ~{approx_m:.0f}m is coarse")
            else:
                report["approx_resolution_m"] = round(res_x, 1)

            # Read data and check for valid values
            data = src.read(1)
            if src.nodata is not None and np.isnan(src.nodata):
                valid_mask = np.isfinite(data)
            elif src.nodata is not None:
                valid_mask = (data != src.nodata) & np.isfinite(data)
            else:
                valid_mask = np.isfinite(data)

            valid_count = int(np.sum(valid_mask))
            total_count = data.size
            report["valid_cells"] = valid_count
            report["total_cells"] = total_count
            report["valid_fraction"] = round(valid_count / max(total_count, 1), 4)

            if valid_count == 0:
                report["errors"].append("All cells are nodata — empty raster")
            else:
                valid_data = data[valid_mask]
                report["elevation_min_m"] = round(float(np.min(valid_data)), 2)
                report["elevation_max_m"] = round(float(np.max(valid_data)), 2)
                report["elevation_mean_m"] = round(float(np.mean(valid_data)), 2)

            # Compute fingerprint
            sha256 = hashlib.sha256()
            with open(dem_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
            report["sha256"] = sha256.hexdigest()

            if not report["errors"]:
                report["valid"] = True

    except Exception as e:
        report["errors"].append(f"Failed to open: {str(e)}")

    return report


def reproject_dem(
    input_path: Path,
    output_path: Path,
    target_epsg: int,
    target_resolution_m: float = 30.0,
) -> Path:
    """Reproject and resample DEM to city's projected CRS.

    Uses bilinear resampling for continuous elevation data
    (no stairstep artifacts of nearest, no overshoot of cubic).
    """
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import calculate_default_transform, reproject

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(input_path) as src:
        dst_crs = rasterio.crs.CRS.from_epsg(target_epsg)

        transform, width, height = calculate_default_transform(
            src.crs,
            dst_crs,
            src.width,
            src.height,
            *src.bounds,
            resolution=target_resolution_m,
        )

        kwargs = src.meta.copy()
        kwargs.update(
            {
                "crs": dst_crs,
                "transform": transform,
                "width": width,
                "height": height,
            }
        )

        with rasterio.open(output_path, "w", **kwargs) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=dst_crs,
                    resampling=Resampling.bilinear,
                )

    logger.info(
        "DEM reprojected",
        target_epsg=target_epsg,
        resolution_m=target_resolution_m,
        width=width,
        height=height,
        output=str(output_path),
    )
    return output_path
