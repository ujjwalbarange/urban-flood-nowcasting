#!/usr/bin/env bash
set -e
OUT=../11_coastal
mkdir -p "$OUT"
curl -s -X POST "https://overpass-api.de/api/interpreter" --data-urlencode data@- << 'QUERY' -o "$OUT/coastline_raw.json"
[out:json][timeout:120];
(
  way["natural"="coastline"](18.80,72.70,19.35,73.05);
);
out body;
>;
out skel qt;
QUERY
npx osmtogeojson "$OUT/coastline_raw.json" > "$OUT/coastline.geojson"
echo "Done."
