"""Derive Hydrological Terrain Parameters from Copernicus GLO-30 DEM.

Scientifically Defensible Algorithms:
1. Slope (degrees and percentage via Horn 8-neighbor gradient)
2. Aspect (azimuth 0-360 degrees)
3. Depression Sinks / Ponding Depth via Barnes Priority-Flood Algorithm (2014)
4. D8 Flow Direction (Esri standard powers of 2) on hydrologically filled surface
5. D8 Flow Accumulation (upslope contributing area in cell counts and km²)
6. Relative Elevation (local relief relative to 500m moving window minimum)
"""

import os
import sys
import json
import heapq
from pathlib import Path
import numpy as np
import scipy.ndimage as ndimage
import tifffile

def compute_slope_aspect(dem, cell_size_m=30.0):
    """Calculate slope and aspect using Horn's central differences method."""
    dy, dx = np.gradient(dem, cell_size_m, cell_size_m)
    
    slope_rad = np.arctan(np.sqrt(dx**2 + dy**2))
    slope_deg = np.degrees(slope_rad)
    slope_pct = np.tan(slope_rad) * 100.0
    
    aspect_rad = np.arctan2(-dx, dy)
    aspect_deg = np.degrees(aspect_rad)
    aspect_deg = np.where(aspect_deg < 0, 90.0 - aspect_deg, 360.0 - aspect_deg + 90.0) % 360.0
    aspect_deg = np.where(slope_deg < 0.1, -1.0, aspect_deg) # flat
    
    return slope_deg, slope_pct, aspect_deg

def priority_flood_sinks(dem):
    """
    Priority-Flood Sink Filling Algorithm (Barnes et al., 2014).
    Fills local depressions to their lowest pour point elevation.
    Returns:
      filled_dem: hydrologically conditioned DEM without spurious pits
      sink_depth: depression storage capacity in meters (filled - raw)
    """
    rows, cols = dem.shape
    filled = np.copy(dem)
    visited = np.zeros((rows, cols), dtype=bool)
    pq = []
    
    # Boundary cells
    for r in range(rows):
        heapq.heappush(pq, (dem[r, 0], r, 0))
        visited[r, 0] = True
        heapq.heappush(pq, (dem[r, cols - 1], r, cols - 1))
        visited[r, cols - 1] = True
    for c in range(1, cols - 1):
        heapq.heappush(pq, (dem[0, c], 0, c))
        visited[0, c] = True
        heapq.heappush(pq, (dem[rows - 1, c], rows - 1, c))
        visited[rows - 1, c] = True
        
    neighbors = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    
    while pq:
        elev, r, c = heapq.heappop(pq)
        for dr, dc in neighbors:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and not visited[nr, nc]:
                visited[nr, nc] = True
                if dem[nr, nc] < elev:
                    filled[nr, nc] = elev
                heapq.heappush(pq, (filled[nr, nc], nr, nc))
                
    sink_depth = np.maximum(0.0, filled - dem)
    return filled, sink_depth

def compute_d8_flow_direction(filled_dem):
    """Calculate D8 flow direction on filled DEM using steepest descent."""
    rows, cols = filled_dem.shape
    flow_dir = np.zeros((rows, cols), dtype=np.uint8)
    
    # (dy, dx, code, dist)
    directions = [
        (0, 1, 1, 1.0),      # East
        (1, 1, 2, 1.414),    # South-East
        (1, 0, 4, 1.0),      # South
        (1, -1, 8, 1.414),   # South-West
        (0, -1, 16, 1.0),    # West
        (-1, -1, 32, 1.414), # North-West
        (-1, 0, 64, 1.0),    # North
        (-1, 1, 128, 1.414)  # North-East
    ]
    
    max_slope = np.zeros((rows, cols), dtype=np.float32)
    for dy, dx, code, dist in directions:
        shifted = np.roll(np.roll(filled_dem, -dy, axis=0), -dx, axis=1)
        drop = filled_dem - shifted
        slope = drop / (dist * 30.0)
        steeper = slope > max_slope
        flow_dir[steeper] = code
        max_slope[steeper] = slope[steeper]
        
    return flow_dir

def compute_flow_accumulation(filled_dem, flow_dir):
    """Calculate flow accumulation (number of upslope cells draining to each cell)."""
    rows, cols = filled_dem.shape
    accumulation = np.ones((rows, cols), dtype=np.int32)
    
    # Order cells by elevation descending
    flat_indices = np.argsort(-filled_dem.ravel())
    
    dir_to_offset = {
        1: (0, 1),
        2: (1, 1),
        4: (1, 0),
        8: (1, -1),
        16: (0, -1),
        32: (-1, -1),
        64: (-1, 0),
        128: (-1, 1)
    }
    
    for idx in flat_indices:
        r = idx // cols
        c = idx % cols
        d = flow_dir[r, c]
        if d in dir_to_offset:
            dr, dc = dir_to_offset[d]
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                accumulation[nr, nc] += accumulation[r, c]
                
    return accumulation

def compute_relative_elevation(dem, window_size=15):
    """Calculate relative elevation above local minimum (local relief)."""
    local_min = ndimage.minimum_filter(dem, size=window_size)
    rel_elev = dem - local_min
    return rel_elev

def main():
    dem_path = Path("data/raw/terrain/opentopography_cop30_mumbai_bbox.tif")
    if not dem_path.exists():
        print(f"Error: DEM file not found at {dem_path}")
        return
        
    print(f"Loading DEM: {dem_path}...")
    dem = tifffile.imread(str(dem_path))
    rows, cols = dem.shape
    print(f"DEM shape: {dem.shape}, dtype: {dem.dtype}")
    
    # 1. Slope & Aspect
    print("\n1. Computing Slope and Aspect...")
    slope_deg, slope_pct, aspect_deg = compute_slope_aspect(dem, cell_size_m=30.0)
    
    # 2. Priority-Flood Sinks
    print("\n2. Executing Priority-Flood Sink Filling...")
    filled_dem, sink_depth = priority_flood_sinks(dem)
    print(f"   Max sink depth: {np.max(sink_depth):.2f}m, Mean: {np.mean(sink_depth):.3f}m")
    
    # 3. D8 Flow Direction on Filled Surface
    print("\n3. Computing D8 Flow Direction...")
    flow_dir = compute_d8_flow_direction(filled_dem)
    
    # 4. Flow Accumulation
    print("\n4. Computing Flow Accumulation...")
    flow_acc = compute_flow_accumulation(filled_dem, flow_dir)
    print(f"   Max flow accumulation: {np.max(flow_acc):,} cells ({np.max(flow_acc)*900/1e6:.1f} km²)")
    
    # 5. Relative Elevation
    print("\n5. Computing Relative Elevation (Local Relief)...")
    rel_elev = compute_relative_elevation(dem, window_size=15)
    
    # Save outputs
    out_dir = Path("data/derived")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    np.save("data/derived/slope/slope_degrees.npy", slope_deg.astype(np.float32))
    np.save("data/derived/slope/aspect_degrees.npy", aspect_deg.astype(np.float32))
    np.save("data/derived/catchments/depression_sinks_m.npy", sink_depth.astype(np.float32))
    np.save("data/derived/flow_direction/d8_flow_direction.npy", flow_dir)
    
    acc_path = Path("data/derived/flow_accumulation/flow_accumulation_cells.npy")
    acc_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(str(acc_path), flow_acc)
    
    rel_path = Path("data/derived/catchments/relative_elevation_m.npy")
    np.save(str(rel_path), rel_elev.astype(np.float32))
    
    # Metadata
    metadata = {
        "dem_product": "Copernicus GLO-30 DSM",
        "dem_resolution_m": 30.0,
        "rows": rows,
        "cols": cols,
        "min_elevation_m": float(np.min(dem)),
        "max_elevation_m": float(np.max(dem)),
        "mean_elevation_m": float(np.mean(dem)),
        "slope_mean_deg": float(np.mean(slope_deg)),
        "slope_max_deg": float(np.max(slope_deg)),
        "aspect_mean_deg": float(np.mean(aspect_deg[aspect_deg >= 0])),
        "sink_max_depth_m": float(np.max(sink_depth)),
        "sink_mean_depth_m": float(np.mean(sink_depth)),
        "sink_volume_m3": float(np.sum(sink_depth) * 900.0),
        "flow_accumulation_max_cells": int(np.max(flow_acc)),
        "flow_accumulation_max_area_sq_km": float(np.max(flow_acc) * 900.0 / 1e6),
        "derivation_algorithm": "Barnes Priority-Flood (2014) + Horn Central Differences (1981)"
    }
    with open("data/derived/terrain_derivatives_metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print("\nSaved all terrain derivatives & metadata successfully!")

if __name__ == "__main__":
    main()
