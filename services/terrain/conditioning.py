"""DEM sink conditioning and flow analysis.

Before surface hydrology can work, the DEM needs:
1. Sink filling — remove artificial depressions that trap water
2. Slope calculation — for Manning's equation
3. Flow direction — D8/D-infinity algorithms
4. Flow accumulation — identifies drainage paths and catchment boundaries
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import structlog

logger = structlog.get_logger()


def fill_sinks(dem: np.ndarray, nodata: Optional[float] = None) -> np.ndarray:
    """Fill sinks (artificial depressions) in a DEM.

    Uses the Priority-Flood algorithm (Barnes et al., 2014).
    This is a simplified implementation; for production, use
    richdem or pysheds libraries.

    Args:
        dem: 2D elevation array
        nodata: Nodata value to preserve

    Returns:
        Sink-filled DEM
    """
    import heapq

    filled = dem.copy()
    rows, cols = dem.shape

    if nodata is not None:
        valid_mask = dem != nodata
    else:
        valid_mask = np.isfinite(dem)

    # Initialize: mark all cells as not processed
    processed = np.zeros_like(dem, dtype=bool)
    # Priority queue: (elevation, row, col)
    pq: list[Tuple[float, int, int]] = []

    # Seed the queue with boundary cells
    for r in range(rows):
        for c in range(cols):
            if not valid_mask[r, c]:
                processed[r, c] = True
                continue
            if r == 0 or r == rows - 1 or c == 0 or c == cols - 1:
                heapq.heappush(pq, (dem[r, c], r, c))
                processed[r, c] = True

    # D8 neighbors
    neighbors = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

    while pq:
        elev, r, c = heapq.heappop(pq)
        for dr, dc in neighbors:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and not processed[nr, nc]:
                processed[nr, nc] = True
                if filled[nr, nc] < elev:
                    filled[nr, nc] = elev
                heapq.heappush(pq, (filled[nr, nc], nr, nc))

    n_filled = int(np.sum(filled != dem))
    logger.info("DEM sinks filled", cells_modified=n_filled, total_cells=dem.size)
    return filled


def compute_slope(dem: np.ndarray, cell_size_m: float) -> np.ndarray:
    """Compute terrain slope in radians from DEM.

    Uses numpy.gradient for central-difference slope estimation.

    Args:
        dem: 2D elevation array (metres)
        cell_size_m: Cell size in metres

    Returns:
        2D slope array in radians
    """
    dy, dx = np.gradient(dem, cell_size_m)
    slope = np.arctan(np.sqrt(dx ** 2 + dy ** 2))
    return slope


def compute_aspect(dem: np.ndarray, cell_size_m: float) -> np.ndarray:
    """Compute terrain aspect (direction of steepest descent).

    Returns:
        2D aspect array in radians (0 = North, π/2 = East, π = South, 3π/2 = West)
    """
    dy, dx = np.gradient(dem, cell_size_m)
    aspect = np.arctan2(-dx, dy)  # Geographic convention
    aspect = np.mod(aspect, 2 * np.pi)
    return aspect


def compute_flow_direction_d8(dem: np.ndarray, cell_size_m: float) -> np.ndarray:
    """Compute D8 flow direction from a sink-filled DEM.

    Direction codes (following ESRI convention):
        32 | 64 | 128
        ---+----+---
        16 |  0 |   1
        ---+----+---
         8 |  4 |   2

    Args:
        dem: 2D sink-filled elevation array
        cell_size_m: Cell size in metres

    Returns:
        2D flow direction array
    """
    rows, cols = dem.shape
    flow_dir = np.zeros((rows, cols), dtype=np.int32)

    # D8 neighbor offsets and their direction codes
    d8 = [
        (0, 1, 1),     # E
        (1, 1, 2),     # SE
        (1, 0, 4),     # S
        (1, -1, 8),    # SW
        (0, -1, 16),   # W
        (-1, -1, 32),  # NW
        (-1, 0, 64),   # N
        (-1, 1, 128),  # NE
    ]
    diag_dist = cell_size_m * np.sqrt(2)

    for r in range(1, rows - 1):
        for c in range(1, cols - 1):
            max_slope = 0.0
            best_dir = 0
            for dr, dc, code in d8:
                nr, nc = r + dr, c + dc
                dist = diag_dist if (dr != 0 and dc != 0) else cell_size_m
                slope = (dem[r, c] - dem[nr, nc]) / dist
                if slope > max_slope:
                    max_slope = slope
                    best_dir = code
            flow_dir[r, c] = best_dir

    return flow_dir


def compute_flow_accumulation(flow_dir: np.ndarray) -> np.ndarray:
    """Compute flow accumulation from D8 flow direction.

    Each cell's value = number of upstream cells that drain through it.

    Args:
        flow_dir: D8 flow direction array

    Returns:
        2D flow accumulation array (cell counts)
    """
    rows, cols = flow_dir.shape
    accumulation = np.ones((rows, cols), dtype=np.int64)

    # D8 neighbor offsets indexed by direction code
    d8_target = {
        1: (0, 1),
        2: (1, 1),
        4: (1, 0),
        8: (1, -1),
        16: (0, -1),
        32: (-1, -1),
        64: (-1, 0),
        128: (-1, 1),
    }

    # Count incoming flow for each cell to determine processing order
    incoming = np.zeros((rows, cols), dtype=np.int32)
    for r in range(rows):
        for c in range(cols):
            code = flow_dir[r, c]
            if code in d8_target:
                dr, dc = d8_target[code]
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    incoming[nr, nc] += 1

    # Process cells with no incoming flow first (topological sort)
    from collections import deque

    queue = deque()
    for r in range(rows):
        for c in range(cols):
            if incoming[r, c] == 0:
                queue.append((r, c))

    while queue:
        r, c = queue.popleft()
        code = flow_dir[r, c]
        if code in d8_target:
            dr, dc = d8_target[code]
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                accumulation[nr, nc] += accumulation[r, c]
                incoming[nr, nc] -= 1
                if incoming[nr, nc] == 0:
                    queue.append((nr, nc))

    logger.info(
        "Flow accumulation computed",
        max_accumulation=int(np.max(accumulation)),
        shape=flow_dir.shape,
    )
    return accumulation
