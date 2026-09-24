"""Geospatial artifact registration with an immutable provenance sidecar."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from packages.contracts.datasets import DatasetKind, DatasetManifest, SpatialMetadata
from packages.contracts.provenance import DataOrigin, DataSource, VerificationStatus


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_raster(path: Path) -> SpatialMetadata:
    """Read only raster structural facts; no source claim is inferred."""
    import rasterio

    with rasterio.open(path) as raster:
        return SpatialMetadata(
            crs=str(raster.crs) if raster.crs else None,
            bounds=(raster.bounds.left, raster.bounds.bottom, raster.bounds.right, raster.bounds.top),
            resolution=(float(raster.res[0]), float(raster.res[1])),
            width=raster.width,
            height=raster.height,
            nodata=float(raster.nodata) if raster.nodata is not None else None,
        )


def register_raster(
    path: Path,
    *,
    dataset_id: str,
    kind: DatasetKind,
    source: DataSource,
    origin: DataOrigin,
    source_uri: Optional[str] = None,
    source_product: Optional[str] = None,
    source_version: Optional[str] = None,
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED,
    processing_steps: Optional[list[str]] = None,
    limitations: Optional[list[str]] = None,
) -> DatasetManifest:
    """Register a raster and write ``<file>.manifest.json`` beside it.

    Registration is non-destructive: it cannot turn a candidate input into a
    verified source product. The caller must explicitly supply the review state.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    manifest = DatasetManifest(
        dataset_id=dataset_id,
        kind=kind,
        source=source,
        origin=origin,
        verification_status=verification_status,
        source_uri=source_uri,
        source_product=source_product,
        source_version=source_version,
        acquired_at=datetime.now(timezone.utc),
        local_uri=str(path),
        sha256=sha256_file(path),
        spatial=inspect_raster(path),
        processing_steps=processing_steps or [],
        limitations=limitations or [],
    )
    sidecar = path.with_suffix(path.suffix + ".manifest.json")
    sidecar.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return manifest


def read_manifest(path: Path) -> DatasetManifest:
    return DatasetManifest.model_validate_json(Path(path).read_text(encoding="utf-8"))
