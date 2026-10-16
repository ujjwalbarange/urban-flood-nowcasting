import rasterio
import numpy as np
from pathlib import Path

base_dir = Path("e:/urban/sih/urban-flood-nowcasting/MOSDAC_INSAT_DATA")
tif_files = list(base_dir.rglob("*.tif"))

unreasonable_values = []
nodata_stats = []
max_rains = []
negative_valid_values = []

for idx, f in enumerate(tif_files):
    with rasterio.open(f) as src:
        arr = src.read(1)
        nodata = src.nodata
        valid = arr[arr != nodata]
        
        # Check negative valid values
        neg = valid[valid < 0]
        if len(neg) > 0:
            negative_valid_values.append((f.name, len(neg), neg.min()))
            
        # Check excessive values (> 300 mm/hr)
        excess = valid[valid > 300.0]
        if len(excess) > 0:
            unreasonable_values.append((f.name, len(excess), excess.max()))
            
        nodata_count = (arr == nodata).sum()
        nodata_stats.append((f.name, nodata_count, arr.size))
        
        if len(valid) > 0:
            max_rains.append((valid.max(), f.name))

print(f"Scanned {len(tif_files)} files:")
print(f"Negative valid values (< 0): {len(negative_valid_values)}")
print(f"Unreasonably high values (> 300 mm/hr): {len(unreasonable_values)}")

max_rains.sort(reverse=True)
print(f"\nTop 10 highest rain rate observations across all files:")
for max_v, fname in max_rains[:10]:
    print(f"  {max_v:.2f} mm/hr in {fname}")

nodata_pcts = [cnt / total * 100.0 for _, cnt, total in nodata_stats]
print(f"\nNoData Statistics:")
print(f"  Min NoData %: {min(nodata_pcts):.2f}%")
print(f"  Max NoData %: {max(nodata_pcts):.2f}%")
print(f"  Avg NoData %: {sum(nodata_pcts)/len(nodata_pcts):.2f}%")
files_with_nodata = sum(1 for p in nodata_pcts if p > 0)
print(f"  Files with some NoData pixels: {files_with_nodata} / {len(tif_files)}")
