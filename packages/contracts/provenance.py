"""Provenance and data quality contracts.

Every piece of data in the system carries provenance:
who produced it, when, from what source, with what quality.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class DataQuality(str, Enum):
    """Quality classification for ingested data."""

    MEASURED = "measured"        # From calibrated instrument / validated source
    DERIVED = "derived"         # Computed from measured inputs
    ASSUMED = "assumed"         # Default / literature value (flagged)
    ESTIMATED = "estimated"     # Model output / interpolation
    UNKNOWN = "unknown"         # Quality not assessed
    REJECTED = "rejected"       # Failed validation


class DataOrigin(str, Enum):
    """The origin class required for every dataset release.

    This deliberately does not infer that a downloaded public product is a
    local instrument measurement. ``DERIVED`` and ``SYNTHETIC`` must remain
    visible all the way to API clients and model runs.
    """

    MEASURED_REAL = "measured_real"
    PUBLIC_DATA = "public_data"
    DERIVED = "derived"
    ASSUMED = "assumed"
    SYNTHETIC = "synthetic"


class VerificationStatus(str, Enum):
    """Review state, separate from the dataset's origin."""

    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    REJECTED = "rejected"


class DataSource(str, Enum):
    """Known data source categories."""

    COPERNICUS_DEM = "copernicus_glo30"
    CARTODEM = "cartodem_isro"
    SRTM = "srtm_30m"
    OPEN_METEO = "open_meteo"
    MOSDAC = "mosdac_isro"
    NASA_IMERG = "nasa_gpm_imerg"
    CWPRS_GAUGE = "cwprs_telemetry"
    MAHARAIN = "maharain_aws"
    OSM = "openstreetmap"
    MCGM_GIS = "mcgm_arcgis"
    WB_AMRUT = "wb_amrut"
    CITIZEN_REPORT = "citizen_report"
    SYNTHETIC = "synthetic"
    MANUAL = "manual"


class Provenance(BaseModel):
    """Provenance record for any data artifact.

    Tracks the complete lineage: source → processing → output.
    """

    source: DataSource
    source_uri: Optional[str] = None
    source_timestamp: Optional[datetime] = None
    ingested_at: datetime = Field(default_factory=lambda: datetime.now())
    processing_method: Optional[str] = None
    quality: DataQuality = DataQuality.UNKNOWN
    origin: Optional[DataOrigin] = None
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    sha256: Optional[str] = None
    notes: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
