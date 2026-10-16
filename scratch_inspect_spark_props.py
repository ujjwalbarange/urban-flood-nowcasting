"""Inspect property fields and sample features from each Spark GeoJSON file."""

import json
from pathlib import Path

SPARK_DIR = Path("mumbai_flood_spatial_data")
DATASETS = [
    "01_roads/mumbai_full_road_network.geojson",
    "02_drainage/mumbai_public_drainage_network.geojson",
    "02_drainage/mumbai_drainage_structures.geojson",
    "03_land_cover/mumbai_land_use_land_cover.geojson",
    "03_land_cover/mumbai_impervious_surface.geojson",
    "04_flood_risk/mumbai_flood_hotspots.geojson",
    "04_flood_risk/mumbai_low_lying_areas.geojson",
    "04_flood_risk/mumbai_coastal_exposure.geojson",
    "05_structures/mumbai_bridges_culverts.geojson",
    "06_green_infrastructure/mumbai_green_open_spaces.geojson"
]

for d in DATASETS:
    p = SPARK_DIR / d
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    feats = data.get("features", [])
    print(f"\n==========================================")
    print(f"FILE: {d} ({len(feats)} features)")
    if feats:
        f0 = feats[0]
        print(f"Properties ({len(f0['properties'])} keys):", list(f0["properties"].keys()))
        print("Sample Properties:")
        for k, v in f0["properties"].items():
            print(f"  {k}: {repr(v)}")
        # Check if there are other unique properties in remaining features
        all_keys = set()
        for f in feats:
            all_keys.update(f.get("properties", {}).keys())
        if len(all_keys) > len(f0["properties"]):
            print("Additional keys in other features:", all_keys - set(f0["properties"].keys()))
