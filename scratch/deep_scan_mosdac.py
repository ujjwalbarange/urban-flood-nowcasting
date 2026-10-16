import os
import re
from pathlib import Path
from collections import defaultdict
import rasterio
import hashlib

base_dir = Path("e:/urban/sih/urban-flood-nowcasting/MOSDAC_INSAT_DATA")
tif_files = list(base_dir.rglob("*.tif"))

print(f"Total files: {len(tif_files)}")

# Parse filename pattern:
# Example: 3RIMG_13AUG2025_0015_L2B_HEM_V01R00_HEM.tif
# or 3RIMG_..._IMC...
pattern = re.compile(r"3RIMG_(\d{2}[A-Z]{3}\d{4})_(\d{4})_L2B_(HEM|IMC)_(V\d+R\d+)_(.*)\.tif", re.IGNORECASE)

records = []
filename_map = defaultdict(list)
timestamp_map = defaultdict(list)
dimensions = set()
bounds_set = set()
nodatas = set()
dtypes = set()

for f in tif_files:
    fname = f.name
    filename_map[fname].append(f)
    match = pattern.match(fname)
    if match:
        date_str, time_str, prod, ver, suffix = match.groups()
        ts_key = (prod.upper(), date_str.upper(), time_str)
        timestamp_map[ts_key].append(f)
        records.append({
            "path": f,
            "filename": fname,
            "product": prod.upper(),
            "date_str": date_str.upper(),
            "time_str": time_str,
            "version": ver,
            "suffix": suffix,
            "matched": True
        })
    else:
        records.append({
            "path": f,
            "filename": fname,
            "matched": False
        })

print(f"Matched filename regex: {sum(1 for r in records if r.get('matched'))} / {len(records)}")

# Duplicate filenames check
dup_filenames = {k: v for k, v in filename_map.items() if len(v) > 1}
print(f"Duplicate filenames across folders: {len(dup_filenames)}")
for k, v in list(dup_filenames.items())[:5]:
    paths = [str(p.relative_to(base_dir)) for p in v]
    print(f"  {k} -> {paths}")

# Duplicate timestamps check per product
dup_timestamps = {k: v for k, v in timestamp_map.items() if len(v) > 1}
print(f"Duplicate timestamps per product: {len(dup_timestamps)}")

# Dates covered per product
product_dates = defaultdict(lambda: defaultdict(int))
for r in records:
    if r.get("matched"):
        product_dates[r["product"]][r["date_str"]] += 1

print("\n--- Dates covered by product ---")
for prod, dates in sorted(product_dates.items()):
    print(f"\nProduct {prod} ({sum(dates.values())} files across {len(dates)} dates):")
    for d, cnt in sorted(dates.items()):
        print(f"  {d}: {cnt} half-hourly files")

# Inspect sample IMC file
imc_files = [r["path"] for r in records if r.get("product") == "IMC"]
if imc_files:
    sample_imc = imc_files[0]
    with rasterio.open(sample_imc) as src:
        arr = src.read(1)
        valid = arr[arr != src.nodata] if src.nodata is not None else arr
        print(f"\n--- Sample IMC Raster Properties ({sample_imc.name}) ---")
        print(f"  CRS: {src.crs}")
        print(f"  Bounds: {src.bounds}")
        print(f"  Dimensions: {src.width} x {src.height}")
        print(f"  Resolution: {src.res}")
        print(f"  NoData: {src.nodata}")
        print(f"  Dtype: {src.dtypes[0]}")
        if len(valid) > 0:
            print(f"  Min: {valid.min()}, Max: {valid.max()}, Mean: {valid.mean():.3f}, Valid pixels: {len(valid)} / {arr.size}")
        else:
            print(f"  All pixels NoData")
