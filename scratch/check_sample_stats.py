import rasterio
from pathlib import Path
import numpy as np

base_dir = Path("e:/urban/sih/urban-flood-nowcasting/MOSDAC_INSAT_DATA")

# Sample HEM files from 2024 and 2025
hem_samples = [
    base_dir / "mosdac_data2/Sep26_191242/3RIMG_08JUL2024_0815_L2B_HEM_V01R00_HEM.tif",
    base_dir / "mosdac_data2/Sep26_191242/3RIMG_09JUL2024_1415_L2B_HEM_V01R00_HEM.tif",
    base_dir / "Mosdac_data/Sep26_191236/3RIMG_17AUG2025_1145_L2B_HEM_V01R00_HEM.tif"
]

# Sample IMC files from 2024
imc_samples = [
    base_dir / "mosdac_data2/Sep26_191244/3RIMG_08JUL2024_0815_L2B_IMC_V01R00_IMC.tif",
    base_dir / "Mosdac_data/Sep26_191238/3RIMG_25JUL2024_1215_L2B_IMC_V01R00_IMC.tif"
]

for p in hem_samples + imc_samples:
    if p.exists():
        with rasterio.open(p) as src:
            arr = src.read(1)
            nodata = src.nodata
            valid = arr[arr != nodata]
            print(f"\n=======================================================")
            print(f"File: {p.name}")
            print(f"Tags: {src.tags()}")
            print(f"Meta: {src.meta}")
            print(f"Shape: {arr.shape}, Dtype: {arr.dtype}, NoData: {nodata}")
            if len(valid) > 0:
                print(f"Valid pixels: {len(valid)} / {arr.size} ({len(valid)/arr.size*100:.1f}%)")
                print(f"Min: {valid.min():.4f}, Max: {valid.max():.4f}, Mean: {valid.mean():.4f}, Std: {valid.std():.4f}")
                print(f"Percentiles (50th, 90th, 99th): {np.percentile(valid, 50):.2f}, {np.percentile(valid, 90):.2f}, {np.percentile(valid, 99):.2f}")
            else:
                print("All pixels NoData")
