import numpy as np
import scipy.ndimage as ndimage
import tifffile
import heapq
from pathlib import Path

def priority_flood_sinks(dem, max_iterations=50):
    """
    Morphological reconstruction / Priority-Flood sink filling algorithm.
    Fills local depressions to their lowest pour point elevation.
    Returns:
      filled_dem: elevation after filling sinks
      sink_depth: filled_dem - dem (depression storage capacity in meters)
    """
    rows, cols = dem.shape
    # Initialize filled surface: boundary is fixed to dem, interior is initialized to infinity
    # Or iterative morphological reconstruction:
    # Marker is initialized to DEM everywhere, except interior where it is initialized to max
    # Then iterative geodesic dilation until convergence
    
    # Efficient morphological reconstruction using ndimage
    # We can downsample or use block-level / priority queue for large DEM
    print(f"Running sink detection on DEM shape {dem.shape}...")
    
    # Alternative robust morphological sink identification:
    # A local minimum is where all 8 neighbors are higher than the central cell.
    # In ndimage: minimum filter of dem in 3x3
    # If the central cell equals min_filter, it is a local pit.
    # The depth of the sink is the difference between the minimum neighbor on the rim and the pit.
    
    # Let's test morphological reconstruction by dilation:
    # Mask = dem
    # Marker = dem + epsilon, or boundary=dem, interior=high
    
    # For fast and accurate sink identification in 1800x1620:
    # Priority-Flood algorithm using heapq
    filled = np.copy(dem)
    visited = np.zeros((rows, cols), dtype=bool)
    pq = []
    
    # Push boundary cells into priority queue
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
        
    print(f"Initialized Priority-Queue with {len(pq)} boundary cells.")
    
    # 8-connected neighbors
    neighbors = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    
    # Process priority queue
    count = 0
    while pq:
        elev, r, c = heapq.heappop(pq)
        
        for dr, dc in neighbors:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and not visited[nr, nc]:
                visited[nr, nc] = True
                if dem[nr, nc] < elev:
                    # Cell is in a depression! Fill it to spill elevation
                    filled[nr, nc] = elev
                heapq.heappush(pq, (filled[nr, nc], nr, nc))
                
        count += 1
        if count % 500000 == 0:
            print(f"Processed {count:,} / {rows*cols:,} cells...")
            
    sink_depth = np.maximum(0.0, filled - dem)
    return filled, sink_depth

if __name__ == "__main__":
    dem = tifffile.imread("data/raw/terrain/opentopography_cop30_mumbai_bbox.tif")
    filled, sink_depth = priority_flood_sinks(dem)
    print("Sink Depth Stats:")
    print("Min:", np.min(sink_depth))
    print("Max:", np.max(sink_depth))
    print("Mean:", np.mean(sink_depth))
    p99 = np.percentile(sink_depth, 99.9)
    print("99.9th percentile:", p99)
    non_zero = np.count_nonzero(sink_depth > 0.05)
    print(f"Cells with > 5cm depression: {non_zero:,} ({non_zero/sink_depth.size*100:.2f}%)")
