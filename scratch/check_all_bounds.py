import rasterio
from pathlib import Path
from collections import Counter

base_dir = Path("e:/urban/sih/urban-flood-nowcasting/MOSDAC_INSAT_DATA")
tif_files = list(base_dir.rglob("*.tif"))

bounds_counter = Counter()
dims_counter = Counter()
crs_counter = Counter()
res_counter = Counter()
nodata_counter = Counter()

for f in tif_files:
    with rasterio.open(f) as src:
        bounds_counter[tuple(round(b, 4) for b in src.bounds)] += 1
        dims_counter[(src.width, src.height)] += 1
        crs_counter[str(src.crs)] += 1
        res_counter[tuple(round(r, 6) for r in src.res)] += 1
        nodata_counter[src.nodata] += 1

print(f"Total files: {len(tif_files)}")
print(f"\nCRSs: {dict(crs_counter)}")
print(f"Dimensions: {dict(dims_counter)}")
print(f"Resolutions: {dict(res_counter)}")
print(f"NoData values: {dict(nodata_counter)}")
print(f"\nBounds:")
for b, count in bounds_counter.items():
    print(f"  {b}: {count} files")
