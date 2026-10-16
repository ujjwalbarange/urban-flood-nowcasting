"""Migrate and organize raw package files into canonical data/raw/ directories.

Creates metadata manifests for every raw file preserving SHA-256 and source origin.
"""

import os
import shutil
import hashlib
import json
from pathlib import Path

SRC_PKG = Path("mumbai_flood_data_package")
ROOT_HIST_GEOJSON = Path("mumbai_urban_flood_2016_2025 (1).geojson")

MAPPINGS = [
    # Administrative Boundaries
    (SRC_PKG / "01_city" / "mumbai_boundary.geojson", Path("data/raw/administrative_boundaries/mumbai_boundary.geojson")),
    (SRC_PKG / "01_city" / "wards.geojson", Path("data/raw/administrative_boundaries/wards.geojson")),
    (SRC_PKG / "01_city" / "config.json", Path("data/raw/administrative_boundaries/city_config.json")),
    
    # Historical Flood Events
    (ROOT_HIST_GEOJSON, Path("data/raw/historical_floods/mumbai_urban_flood_2016_2025.geojson")),
    (SRC_PKG / "08_flood_observations" / "flood_points.geojson", Path("data/raw/historical_floods/flood_points.geojson")),
    (SRC_PKG / "08_flood_observations" / "flood_polygons.geojson", Path("data/raw/historical_floods/flood_polygons.geojson")),
    (SRC_PKG / "08_flood_observations" / "historical_events" / "bmc_chronic_spots_inventory.csv", Path("data/raw/historical_floods/bmc_chronic_spots_inventory.csv")),
    
    # Rainfall & Gauges
    (SRC_PKG / "07_rainfall" / "gauges" / "hourly_gauge_data_2015_2025.csv", Path("data/raw/rainfall/hourly_gauge_data_2015_2025.csv")),
    (SRC_PKG / "07_rainfall" / "gauges" / "station_metadata.geojson", Path("data/raw/rainfall/station_metadata.geojson")),
    (SRC_PKG / "07_rainfall" / "historical" / "event_2005_07_26_santacruz_colaba_15min.csv", Path("data/raw/rainfall/event_2005_07_26_santacruz_colaba_15min.csv")),
    (SRC_PKG / "07_rainfall" / "historical" / "event_2017_08_29_mumbai_deluge_hourly.csv", Path("data/raw/rainfall/event_2017_08_29_mumbai_deluge_hourly.csv")),
    (SRC_PKG / "07_rainfall" / "historical" / "event_2019_07_02_malad_santacruz_hourly.csv", Path("data/raw/rainfall/event_2019_07_02_malad_santacruz_hourly.csv")),
    (SRC_PKG / "07_rainfall" / "historical" / "event_2020_08_05_colaba_cyclonic_hourly.csv", Path("data/raw/rainfall/event_2020_08_05_colaba_cyclonic_hourly.csv")),
    (SRC_PKG / "07_rainfall" / "historical" / "event_2021_07_18_chembur_cloudburst_hourly.csv", Path("data/raw/rainfall/event_2021_07_18_chembur_cloudburst_hourly.csv")),
    (SRC_PKG / "07_rainfall" / "historical" / "event_2024_09_25_mumbai_monsoon_hourly.csv", Path("data/raw/rainfall/event_2024_09_25_mumbai_monsoon_hourly.csv")),
    (SRC_PKG / "07_rainfall" / "imerg" / "imerg_20050726_halfhourly_mumbai_grid.csv", Path("data/raw/satellite/imerg_20050726_halfhourly_mumbai_grid.csv")),
    (SRC_PKG / "07_rainfall" / "mosdac_samples" / "insat3d_heg_mumbai_sample_20240925.json", Path("data/raw/satellite/insat3d_heg_mumbai_sample_20240925.json")),
    
    # Drainage
    (SRC_PKG / "06_drainage" / "nodes.geojson", Path("data/raw/drainage/nodes.geojson")),
    (SRC_PKG / "06_drainage" / "links.geojson", Path("data/raw/drainage/links.geojson")),
    (SRC_PKG / "06_drainage" / "outfalls.geojson", Path("data/raw/drainage/outfalls.geojson")),
    
    # Land Cover
    (SRC_PKG / "03_land_cover" / "worldcover.tif", Path("data/raw/landuse/worldcover.tif")),
    
    # Roads & Buildings
    (SRC_PKG / "04_roads" / "roads.geojson", Path("data/raw/roads/roads.geojson")),
    (SRC_PKG / "05_buildings" / "buildings.geojson", Path("data/raw/buildings/buildings.geojson")),
    
    # Population & Shelters
    (SRC_PKG / "09_population" / "population.geojson", Path("data/raw/population/population.geojson")),
    (SRC_PKG / "10_shelters" / "shelters.geojson", Path("data/raw/shelters/shelters.geojson")),
    
    # Coastal & Tides
    (SRC_PKG / "11_coastal" / "coastline.geojson", Path("data/raw/tides/coastline.geojson")),
    (SRC_PKG / "11_coastal" / "tide" / "apollo_bunder_hourly_tide_20050725_20050727.csv", Path("data/raw/tides/apollo_bunder_hourly_tide_20050725_20050727.csv")),
    (SRC_PKG / "11_coastal" / "tide" / "apollo_bunder_tide_benchmarks.json", Path("data/raw/tides/apollo_bunder_tide_benchmarks.json")),
    
    # DEM Tiles
    (SRC_PKG / "02_dem" / "cartodem" / "CartoDEM_V3R1_N18E072.tif", Path("data/raw/dem/CartoDEM_V3R1_N18E072.tif")),
    (SRC_PKG / "02_dem" / "cartodem" / "CartoDEM_V3R1_N19E072.tif", Path("data/raw/dem/CartoDEM_V3R1_N19E072.tif")),
    (SRC_PKG / "02_dem" / "copernicus_glo30" / "Copernicus_DSM_COG_10_N18_00_E072_00_DEM.tif", Path("data/raw/dem/Copernicus_DSM_COG_10_N18_00_E072_00_DEM.tif")),
    (SRC_PKG / "02_dem" / "copernicus_glo30" / "Copernicus_DSM_COG_10_N19_00_E072_00_DEM.tif", Path("data/raw/dem/Copernicus_DSM_COG_10_N19_00_E072_00_DEM.tif")),
]

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def main():
    print(f"=== MIGRATING {len(MAPPINGS)} RAW DATASETS INTO CANONICAL data/raw/ ===")
    manifest = []
    
    for src, dst in MAPPINGS:
        if not src.exists():
            print(f"Warning: Source not found: {src}")
            continue
            
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists() or dst.stat().st_size != src.stat().st_size:
            shutil.copy2(src, dst)
            print(f"Copied {src.name} -> {dst}")
        else:
            print(f"Already up-to-date: {dst}")
            
        sz = dst.stat().st_size
        sha = sha256_file(dst)
        manifest.append({
            "target_path": str(dst).replace("\\", "/"),
            "original_path": str(src).replace("\\", "/"),
            "file_name": dst.name,
            "size_bytes": sz,
            "sha256": sha
        })
        
    manifest_path = Path("data/manifests/raw_datasets_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as mf:
        json.dump(manifest, mf, indent=2)
        
    print(f"\nManifest created with {len(manifest)} verified entries: {manifest_path}")

if __name__ == "__main__":
    main()
