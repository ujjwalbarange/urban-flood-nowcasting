"""Contracts for reproducible raster and historical-evidence ingestion.

These contracts preserve what an artifact is, where it came from and what
claim may be made about it. They intentionally do not contain flood depth or
other inferred values.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from packages.contracts.provenance import DataOrigin, DataSource, VerificationStatus


class DatasetKind(str, Enum):
    TERRAIN_DEM = "terrain_dem"
    LAND_COVER = "land_cover"
    RAINFALL_GRID = "rainfall_grid"
    FLOOD_EXTENT = "flood_extent"
    FLOOD_INCIDENT = "flood_incident"


class EvidenceMethod(str, Enum):
    SENTINEL_1_CHANGE_DETECTION = "sentinel_1_change_detection"
    INCIDENT_LOG = "incident_log"
    EVENT_MAP = "event_map"


class SpatialMetadata(BaseModel):
    """Minimal spatial facts extracted from an opened raster."""

    crs: Optional[str] = None
    bounds: Optional[tuple[float, float, float, float]] = None
    resolution: Optional[tuple[float, float]] = None
    width: Optional[int] = Field(default=None, ge=1)
    height: Optional[int] = Field(default=None, ge=1)
    nodata: Optional[float] = None


class DatasetManifest(BaseModel):
    """Sidecar manifest for an immutable, local geospatial artifact."""

    dataset_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{2,127}$")
    kind: DatasetKind
    source: DataSource
    origin: DataOrigin
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    source_uri: Optional[str] = None
    source_product: Optional[str] = None
    source_version: Optional[str] = None
    acquired_at: datetime
    local_uri: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    spatial: SpatialMetadata = Field(default_factory=SpatialMetadata)
    processing_steps: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class HistoricalFloodEvidence(BaseModel):
    """A validation candidate, never an implicit water-depth observation."""

    evidence_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{2,127}$")
    method: EvidenceMethod
    event_start: datetime
    event_end: datetime
    source: DataSource
    origin: DataOrigin
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    source_uri: Optional[str] = None
    scene_or_record_id: Optional[str] = None
    extent_uri: Optional[str] = None
    has_depth_observations: bool = False
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_evidence_claims(self) -> "HistoricalFloodEvidence":
        if self.event_end < self.event_start:
            raise ValueError("event_end must not precede event_start")
        if self.method == EvidenceMethod.SENTINEL_1_CHANGE_DETECTION:
            if self.has_depth_observations:
                raise ValueError("Sentinel-1 extent evidence cannot be labelled as water depth")
            if not self.scene_or_record_id:
                raise ValueError("Sentinel-1 evidence requires a scene identifier")
        return self
