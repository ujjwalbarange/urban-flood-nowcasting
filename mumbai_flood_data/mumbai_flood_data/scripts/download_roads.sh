#!/usr/bin/env bash
# Mumbai road network from OSM via Overpass API. No auth needed.
set -e
OUT=../04_roads
mkdir -p "$OUT"

curl -s -X POST "https://overpass-api.de/api/interpreter" --data-urlencode data@- << 'QUERY' -o "$OUT/roads_raw.json"
[out:json][timeout:180];
(
  way["highway"](18.85,72.75,19.30,72.98);
);
out body;
>;
out skel qt;
QUERY

# Convert to GeoJSON (requires: npm install -g osmtogeojson, or pip install osm2geojson)
npx osmtogeojson "$OUT/roads_raw.json" > "$OUT/roads.geojson"
echo "Done. Validate with: python3 -c \"import json; d=json.load(open('$OUT/roads.geojson')); print(len(d['features']), 'road features')\""
