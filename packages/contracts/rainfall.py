"""Rainfall observation and nowcast contracts."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from packages.contracts.provenance import DataQuality, DataSource, Provenance


class RainfallSpatialType(str, Enum):
    """How rainfall data is spatially represented."""

    POINT = "point"     # Single gauge / station
    GRID = "grid"       # Gridded raster (satellite, NWP, radar)


class NowcastMethod(str, Enum):
    """Rainfall nowcasting method."""

    PERSISTENCE = "persistence"
    OPTICAL_FLOW = "optical_flow"
    NWP_BLEND = "nwp_blend"
    NWP_ONLY = "nwp_only"
    ML_PREDICTION = "ml_prediction"


class RainfallObservation(BaseModel):
    """A rainfall observation from any provider."""

    source: DataSource
    observed_at: datetime
    rate_mmh: float = Field(..., ge=0, description="Rainfall rate in mm/h")
    spatial_type: RainfallSpatialType
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    grid_storage_uri: Optional[str] = None
    quality: DataQuality = DataQuality.UNKNOWN
    provenance: Optional[Provenance] = None


class RainfallNowcast(BaseModel):
    """A rainfall nowcast/forecast for a future time."""

    method: NowcastMethod
    initialization_time: datetime
    valid_time: datetime
    lead_minutes: int = Field(..., ge=0)
    mean_rate_mmh: float = Field(..., ge=0)
    confidence: Optional[float] = Field(None, ge=0, le=1)
    grid_storage_uri: Optional[str] = None
    quality_flags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
