"""City and spatial configuration contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    """Axis-aligned bounding box in WGS84 (EPSG:4326)."""

    min_lon: float = Field(..., description="Western longitude bound")
    min_lat: float = Field(..., description="Southern latitude bound")
    max_lon: float = Field(..., description="Eastern longitude bound")
    max_lat: float = Field(..., description="Northern latitude bound")

    def to_wkt_polygon(self) -> str:
        """Convert to WKT POLYGON for PostGIS."""
        return (
            f"POLYGON(({self.min_lon} {self.min_lat}, {self.max_lon} {self.min_lat}, "
            f"{self.max_lon} {self.max_lat}, {self.min_lon} {self.max_lat}, "
            f"{self.min_lon} {self.min_lat}))"
        )


class CityConfig(BaseModel):
    """Configuration for a city in the multi-city system.

    The system is MULTI-CITY from the start. Each city has its own
    CRS, DEM, drainage network, and simulation parameters.
    Mumbai is city_id='mumbai', but nothing is hardcoded.
    """

    city_id: str = Field(..., min_length=2, max_length=32, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(..., min_length=1, max_length=255)
    state: str = Field(default="", max_length=128)
    country: str = Field(default="IN", max_length=4)
    crs_epsg: int = Field(
        ...,
        description="Projected CRS EPSG code for simulation grid (e.g. 32643 for Mumbai UTM 43N)",
    )
    cell_size_m: float = Field(default=30.0, gt=0, description="Simulation grid cell size in metres")
    bbox: BoundingBox = Field(..., description="Geographic bounding box in WGS84")
    timezone: str = Field(default="Asia/Kolkata")
    config: dict[str, Any] = Field(default_factory=dict, description="Additional city-specific config")


class CityCreate(BaseModel):
    """Request body for creating a city."""

    city_id: str = Field(..., min_length=2, max_length=32, pattern=r"^[a-z][a-z0-9_]*$")
    name: str
    state: str = ""
    country: str = "IN"
    crs_epsg: int
    cell_size_m: float = 30.0
    bbox: BoundingBox
    timezone: str = "Asia/Kolkata"
    config: dict[str, Any] = Field(default_factory=dict)


class CityResponse(BaseModel):
    """Response body for city queries."""

    city_id: str
    name: str
    state: str
    country: str
    crs_epsg: int
    cell_size_m: float
    bbox: BoundingBox
    timezone: str
    config: dict[str, Any]
    created_at: Optional[datetime] = None


class WardResponse(BaseModel):
    """Response body for ward queries."""

    ward_id: str
    city_id: str
    name: str
    area_sq_km: Optional[float] = None
    population: Optional[int] = None
    geometry_geojson: Optional[dict[str, Any]] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
