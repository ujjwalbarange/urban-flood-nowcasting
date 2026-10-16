import os
import json
import hashlib
from datetime import datetime
from pathlib import Path
import numpy as np
import tifffile
import csv

def get_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def audit_files():
    results = {}
    
    # 1. Rasters (DEM and derivatives)
    dem_path = Path("data/raw/terrain/opentopography_cop30_mumbai_bbox.tif")
    if dem_path.exists():
        tif = tifffile.TiffFile(dem_path)
        arr = tif.asarray()
        results["dem_cop30"] = {
            "path": str(dem_path),
            "size_bytes": dem_path.stat().st_size,
            "sha256": get_sha256(dem_path),
            "shape": list(arr.shape),
            "dtype": str(arr.dtype),
            "min_val": float(np.nanmin(arr)),
            "max_val": float(np.nanmax(arr)),
            "mean_val": float(np.nanmean(arr)),
            "nan_count": int(np.isnan(arr).sum()) if np.issubdtype(arr.dtype, np.floating) else 0
        }
    
    derivatives = {
        "slope": "data/derived/slope/slope_degrees.npy",
        "aspect": "data/derived/slope/aspect_degrees.npy",
        "depression_sinks": "data/derived/catchments/depression_sinks_m.npy",
        "d8_flow_dir": "data/derived/flow_direction/d8_flow_direction.npy"
    }
    results["derivatives"] = {}
    for name, p_str in derivatives.items():
        p = Path(p_str)
        if p.exists():
            arr = np.load(p)
            results["derivatives"][name] = {
                "path": p_str,
                "size_bytes": p.stat().st_size,
                "sha256": get_sha256(p),
                "shape": list(arr.shape),
                "dtype": str(arr.dtype),
                "min": float(np.min(arr)),
                "max": float(np.max(arr)),
                "mean": float(np.mean(arr))
            }
            if name == "d8_flow_dir":
                results["derivatives"][name]["unique_values"] = [int(x) for x in np.unique(arr)]

    # 2. GeoJSONs
    geojsons = {
        "wards_raw": "data/raw/administrative_boundaries/wards.geojson",
        "mumbai_boundary": "data/raw/administrative_boundaries/mumbai_boundary.geojson",
        "buildings_raw": "data/raw/buildings/buildings.geojson",
        "historical_events_raw": "data/raw/historical_floods/mumbai_urban_flood_2016_2025.geojson",
        "flood_points_raw": "data/raw/historical_floods/flood_points.geojson",
        "flood_polygons_raw": "data/raw/historical_floods/flood_polygons.geojson",
        "population_raw": "data/raw/population/population.geojson",
        "roads_raw": "data/raw/roads/roads.geojson",
        "shelters_raw": "data/raw/shelters/shelters.geojson",
        "coastline_raw": "data/raw/tides/coastline.geojson",
        "drainage_nodes_raw": "data/raw/drainage/nodes.geojson",
        "drainage_links_raw": "data/raw/drainage/links.geojson",
        "drainage_outfalls_raw": "data/raw/drainage/outfalls.geojson",
        "waterways_processed": "data/processed/rivers/mumbai_waterways.geojson",
        "railways_processed": "data/processed/roads/mumbai_railways.geojson",
        "emergency_infra_processed": "data/processed/critical_infrastructure/mumbai_emergency_facilities.geojson"
    }
    results["geojsons"] = {}
    for name, p_str in geojsons.items():
        p = Path(p_str)
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            feats = data.get("features", [])
            geom_types = {}
            for ft in feats:
                gt = ft.get("geometry", {}).get("type") if ft.get("geometry") else "None"
                geom_types[gt] = geom_types.get(gt, 0) + 1
            results["geojsons"][name] = {
                "path": p_str,
                "size_bytes": p.stat().st_size,
                "sha256": get_sha256(p),
                "feature_count": len(feats),
                "geom_types": geom_types,
                "properties_sample": list(feats[0].get("properties", {}).keys()) if feats else []
            }

    # 3. CSVs
    csvs = {
        "weather_observations": "data/processed/weather/observations.csv",
        "weather_forecasts": "data/processed/weather/forecasts.csv",
        "rainfall_observations": "data/processed/rainfall/rainfall_observations.csv",
        "rainfall_forecasts": "data/processed/rainfall/rainfall_forecasts.csv",
        "gauge_hourly_2015_2025": "data/raw/rainfall/hourly_gauge_data_2015_2025.csv",
        "event_2005_deluge": "data/raw/rainfall/event_2005_07_26_santacruz_colaba_15min.csv",
        "tide_apollo_bunder": "data/raw/tides/apollo_bunder_hourly_tide_20050725_20050727.csv",
        "bmc_chronic_spots": "data/raw/historical_floods/bmc_chronic_spots_inventory.csv",
        "imerg_20050726_grid": "data/raw/satellite/imerg_20050726_halfhourly_mumbai_grid.csv"
    }
    results["csvs"] = {}
    for name, p_str in csvs.items():
        p = Path(p_str)
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader, [])
                row_count = sum(1 for _ in reader)
            results["csvs"][name] = {
                "path": p_str,
                "size_bytes": p.stat().st_size,
                "sha256": get_sha256(p),
                "row_count": row_count,
                "columns": header
            }

    # 4. Ingestion Scripts & Reproductibility
    scripts = [
        "data/scripts/ingestion/migrate_raw_package.py",
        "data/scripts/ingestion/ingest_openmeteo.py",
        "data/scripts/ingestion/ingest_osm_water_and_infrastructure.py",
        "data/scripts/ingestion/fetch_railways.py",
        "data/scripts/ingestion/load_postgis.py",
        "data/scripts/transformation/derive_terrain.py",
        "data/scripts/validation/run_data_quality_checks.py"
    ]
    results["scripts"] = {}
    for s_str in scripts:
        p = Path(s_str)
        if p.exists():
            results["scripts"][s_str] = {
                "exists": True,
                "size_bytes": p.stat().st_size,
                "last_modified": str(datetime.fromtimestamp(p.stat().st_mtime))
            }
        else:
            results["scripts"][s_str] = { "exists": False }

    with open("data/scripts/validation/file_deep_audit_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("File deep audit complete! Results saved to data/scripts/validation/file_deep_audit_results.json")

if __name__ == "__main__":
    audit_files()
