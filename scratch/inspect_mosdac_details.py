import os
from pathlib import Path
from collections import defaultdict
import rasterio

base_dir = Path("e:/urban/sih/urban-flood-nowcasting/MOSDAC_INSAT_DATA")
tif_files = list(base_dir.rglob("*.tif"))
print(f"Total .tif files: {len(tif_files)}")

folder_counts = defaultdict(int)
product_counts = defaultdict(int)
year_counts = defaultdict(int)
product_year_counts = defaultdict(int)

sample_files = []

for f in tif_files:
    rel = f.relative_to(base_dir)
    folder_key = str(rel.parent)
    folder_counts[folder_key] += 1
    
    fname = f.name
    # Identify product
    if "HEM" in fname:
        prod = "HEM"
    elif "IMC" in fname:
        prod = "IMC"
    else:
        prod = "UNKNOWN"
    product_counts[prod] += 1
    
    # Identify year
    if "2024" in fname:
        yr = "2024"
    elif "2025" in fname:
        yr = "2025"
    else:
        yr = "OTHER"
    year_counts[yr] += 1
    product_year_counts[(prod, yr)] += 1
    
    if len(sample_files) < 5 or (prod == "IMC" and sum(1 for s in sample_files if "IMC" in s.name) < 2):
        sample_files.append(f)

print("\n--- Files per folder ---")
for k, v in sorted(folder_counts.items()):
    print(f"  {k}: {v} files")

print("\n--- Files per product ---")
for k, v in sorted(product_counts.items()):
    print(f"  {k}: {v} files")

print("\n--- Files per year ---")
for k, v in sorted(year_counts.items()):
    print(f"  {k}: {v} files")

print("\n--- Files per (product, year) ---")
for (p, y), v in sorted(product_year_counts.items()):
    print(f"  {p} ({y}): {v} files")

print("\n--- Sample Raster Properties (rasterio) ---")
for f in sample_files[:4]:
    with rasterio.open(f) as src:
        arr = src.read(1)
        valid = arr[arr != src.nodata] if src.nodata is not None else arr
        print(f"\nFile: {f.name}")
        print(f"  CRS: {src.crs}")
        print(f"  Bounds: {src.bounds}")
        print(f"  Dimensions: {src.width} x {src.height} (count: {src.count})")
        print(f"  Resolution: {src.res}")
        print(f"  Dtype: {src.dtypes[0]}")
        print(f"  NoData: {src.nodata}")
        if len(valid) > 0:
            print(f"  Min: {valid.min()}, Max: {valid.max()}, Mean: {valid.mean():.3f}, Valid pixels: {len(valid)} / {arr.size}")
        else:
            print(f"  All pixels NoData ({arr.size} pixels)")
