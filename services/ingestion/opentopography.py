"""Authenticated, clipped OpenTopography terrain acquisition.

The returned raster is a source artifact, not a validated hydrodynamic input.
It must be registered and reviewed before a model can consume it.
"""

from __future__ import annotations

from pathlib import Path

from packages.contracts.city import BoundingBox
from services.config.providers import ProviderSettings
from services.ingestion.dem import download_copernicus_dem


async def download_cop30_baseline(
    bbox: BoundingBox,
    output_path: Path,
    settings: ProviderSettings,
) -> Path:
    """Download a clipped COP30 baseline only when an API key is configured."""
    if not settings.opentopography_api_key:
        raise RuntimeError("OpenTopography API key is not configured")

    output_path = Path(output_path)
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing terrain artifact: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".part")
    if temporary_path.exists():
        temporary_path.unlink()

    try:
        await download_copernicus_dem(
            bbox.min_lon,
            bbox.min_lat,
            bbox.max_lon,
            bbox.max_lat,
            temporary_path,
            api_key=settings.opentopography_api_key,
        )
        if temporary_path.stat().st_size == 0:
            raise RuntimeError("OpenTopography returned an empty terrain file")
        temporary_path.replace(output_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    return output_path
