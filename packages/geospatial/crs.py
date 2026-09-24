"""CRS normalization and geospatial coordinate utilities.

All data in the system goes through CRS normalization:
- Storage: WGS84 (EPSG:4326) for database/exchange
- Simulation: City-specific projected CRS (e.g. EPSG:32643 for Mumbai UTM 43N)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np
from pyproj import CRS, Transformer


def get_utm_epsg(longitude: float, latitude: float) -> int:
    """Determine the UTM EPSG code for a given WGS84 coordinate.

    Args:
        longitude: WGS84 longitude (-180 to 180)
        latitude: WGS84 latitude (-90 to 90)

    Returns:
        EPSG code for the appropriate UTM zone
    """
    zone_number = int((longitude + 180) / 6) + 1
    if latitude >= 0:
        return 32600 + zone_number  # Northern hemisphere
    else:
        return 32700 + zone_number  # Southern hemisphere


def create_transformer(from_epsg: int, to_epsg: int) -> Transformer:
    """Create a pyproj Transformer for CRS conversion.

    Uses 'always_xy=True' so coordinates are always (lon, lat) / (x, y),
    not the CRS-native axis order.
    """
    return Transformer.from_crs(
        CRS.from_epsg(from_epsg),
        CRS.from_epsg(to_epsg),
        always_xy=True,
    )


def wgs84_to_projected(
    lon: float, lat: float, target_epsg: int
) -> Tuple[float, float]:
    """Convert WGS84 (lon, lat) to projected coordinates (x, y) in metres."""
    transformer = create_transformer(4326, target_epsg)
    x, y = transformer.transform(lon, lat)
    return x, y


def projected_to_wgs84(
    x: float, y: float, source_epsg: int
) -> Tuple[float, float]:
    """Convert projected coordinates (x, y) to WGS84 (lon, lat)."""
    transformer = create_transformer(source_epsg, 4326)
    lon, lat = transformer.transform(x, y)
    return lon, lat


@dataclass
class GridSpec:
    """Specification for a uniform simulation grid.

    Origin is at the TOP-LEFT corner (north-up convention).
    x increases eastward, y increases southward in cell indices.
    """

    origin_x: float       # Top-left x in projected CRS (metres)
    origin_y: float       # Top-left y in projected CRS (metres)
    cell_size_m: float    # Cell size in metres
    width: int            # Number of columns
    height: int           # Number of rows
    crs_epsg: int         # Projected CRS EPSG code

    @property
    def extent_x(self) -> float:
        """Total width in metres."""
        return self.width * self.cell_size_m

    @property
    def extent_y(self) -> float:
        """Total height in metres."""
        return self.height * self.cell_size_m

    @property
    def total_cells(self) -> int:
        return self.width * self.height

    @property
    def cell_area_m2(self) -> float:
        return self.cell_size_m ** 2

    def cell_center(self, row: int, col: int) -> Tuple[float, float]:
        """Get the projected (x, y) coordinates of a cell center."""
        x = self.origin_x + (col + 0.5) * self.cell_size_m
        y = self.origin_y - (row + 0.5) * self.cell_size_m  # y decreases southward
        return x, y

    def cell_from_coord(self, x: float, y: float) -> Tuple[int, int]:
        """Get (row, col) indices from projected coordinates."""
        col = int((x - self.origin_x) / self.cell_size_m)
        row = int((self.origin_y - y) / self.cell_size_m)
        return row, col

    def contains(self, x: float, y: float) -> bool:
        """Check if projected coordinates fall within the grid."""
        row, col = self.cell_from_coord(x, y)
        return 0 <= row < self.height and 0 <= col < self.width

    @classmethod
    def from_bounds(
        cls,
        min_x: float,
        min_y: float,
        max_x: float,
        max_y: float,
        cell_size_m: float,
        crs_epsg: int,
    ) -> "GridSpec":
        """Create a GridSpec from projected bounds, aligned to cell_size_m."""
        origin_x = np.floor(min_x / cell_size_m) * cell_size_m
        origin_y = np.ceil(max_y / cell_size_m) * cell_size_m
        width = int(np.ceil((max_x - origin_x) / cell_size_m))
        height = int(np.ceil((origin_y - min_y) / cell_size_m))
        return cls(
            origin_x=origin_x,
            origin_y=origin_y,
            cell_size_m=cell_size_m,
            width=width,
            height=height,
            crs_epsg=crs_epsg,
        )
