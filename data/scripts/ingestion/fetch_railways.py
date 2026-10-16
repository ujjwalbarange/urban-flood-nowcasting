import json
import urllib.request
import urllib.parse
from pathlib import Path

def main():
    bbox = "18.89,72.77,19.30,73.00"
    query = f"""[out:json][timeout:25];
(
  node["railway"="station"]({bbox});
  node["station"="subway"]({bbox});
  node["railway"="halt"]({bbox});
);
out tags geom;
"""
    endpoints = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
    ]
    data = None
    for ep in endpoints:
        try:
            print(f"Querying {ep}...")
            req = urllib.request.Request(
                ep,
                data=urllib.parse.urlencode({"data": query}).encode("utf-8"),
                headers={"User-Agent": "MUFNS-Railway/1.0"}
            )
            with urllib.request.urlopen(req, timeout=40) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                break
        except Exception as e:
            print(f"Error from {ep}: {e}")
            
    if data:
        raw_path = Path("data/raw/roads/osm_railways_raw.json")
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"Saved {len(data.get('elements', []))} raw elements to {raw_path}")
        
        # Convert to GeoJSON
        features = []
        for el in data.get("elements", []):
            tags = el.get("tags", {})
            if el["type"] == "node":
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [el["lon"], el["lat"]]},
                    "properties": {"osm_id": el["id"], "type": "station", **tags}
                })
            elif el["type"] == "way" and "geometry" in el:
                coords = [[pt["lon"], pt["lat"]] for pt in el["geometry"]]
                if len(coords) >= 2:
                    features.append({
                        "type": "Feature",
                        "geometry": {"type": "LineString", "coordinates": coords},
                        "properties": {"osm_id": el["id"], "type": "railway_track", **tags}
                    })
        
        proc_path = Path("data/processed/roads/mumbai_railways.geojson")
        with open(proc_path, "w", encoding="utf-8") as f:
            json.dump({"type": "FeatureCollection", "features": features}, f, indent=2)
        print(f"Saved {len(features)} railway features to {proc_path}")

if __name__ == "__main__":
    main()
