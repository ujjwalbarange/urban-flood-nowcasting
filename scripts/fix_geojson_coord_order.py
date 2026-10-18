"""Ensure all GeoJSON administrative boundary files use standard RFC 7946 [longitude, latitude] coordinate order."""

import json
from pathlib import Path
from shapely.geometry import shape, mapping

def flip_coords(coords):
    if isinstance(coords[0], (int, float)):
        # If first value is latitude (~18-20) and second is longitude (~72-73), flip them!
        if 18.0 <= coords[0] <= 20.0 and 72.0 <= coords[1] <= 74.0:
            return [round(coords[1], 7), round(coords[0], 7)]
        return [round(coords[0], 7), round(coords[1], 7)]
    return [flip_coords(c) for c in coords]

def fix_file(filepath: Path):
    if not filepath.exists():
        print(f"Skipping {filepath} (does not exist)")
        return
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    modified = False
    for feat in data.get("features", []):
        geom = feat.get("geometry", {})
        if geom and "coordinates" in geom:
            coords = geom["coordinates"]
            # Check first point
            first_pt = coords
            while isinstance(first_pt, list) and isinstance(first_pt[0], list):
                first_pt = first_pt[0]
            if isinstance(first_pt, list) and len(first_pt) >= 2:
                if 18.0 <= first_pt[0] <= 20.0 and 72.0 <= first_pt[1] <= 74.0:
                    geom["coordinates"] = flip_coords(coords)
                    modified = True

    if modified:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"Fixed coordinate order [lon, lat] in {filepath}")
    else:
        print(f"Already in [lon, lat] order: {filepath}")

def main():
    root = Path(__file__).resolve().parent.parent
    files = [
        root / "data" / "cities" / "mumbai" / "wards.geojson",
        root / "mumbai_flood_data_package" / "01_city" / "wards.geojson",
        root / "data" / "raw" / "administrative_boundaries" / "wards.geojson",
        root / "mumbai_flood_data_package" / "01_city" / "mumbai_boundary.geojson",
        root / "data" / "raw" / "administrative_boundaries" / "mumbai_boundary.geojson",
    ]
    for p in files:
        fix_file(p)

if __name__ == "__main__":
    main()
