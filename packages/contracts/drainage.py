"""Drainage network contracts."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from packages.contracts.provenance import DataQuality


class DrainageNodeType(str, Enum):
    """Type of drainage network node."""

    MANHOLE = "manhole"
    INLET = "inlet"
    OUTFALL = "outfall"
    JUNCTION = "junction"
    PUMP = "pump"
    UNKNOWN = "unknown"


class DrainageLinkType(str, Enum):
    """Type of drainage network link."""

    PIPE = "pipe"
    CHANNEL = "channel"
    CULVERT = "culvert"
    WEIR = "weir"
    UNKNOWN = "unknown"


class DrainageNode(BaseModel):
    """A node (junction/manhole/inlet/outfall) in the drainage network."""

    node_id: str
    city_id: str
    node_type: DrainageNodeType = DrainageNodeType.UNKNOWN
    latitude: float
    longitude: float
    invert_elevation_m: Optional[float] = None
    ground_elevation_m: Optional[float] = None
    max_depth_m: Optional[float] = None
    data_quality: DataQuality = DataQuality.ASSUMED
    attributes: dict[str, Any] = Field(default_factory=dict)


class DrainageLink(BaseModel):
    """A link (pipe/channel/culvert) connecting two drainage nodes."""

    link_id: str
    city_id: str
    from_node: str
    to_node: str
    link_type: DrainageLinkType = DrainageLinkType.UNKNOWN
    diameter_m: Optional[float] = None
    length_m: Optional[float] = None
    manning_n: Optional[float] = None
    slope: Optional[float] = None
    data_quality: DataQuality = DataQuality.ASSUMED
    attributes: dict[str, Any] = Field(default_factory=dict)
