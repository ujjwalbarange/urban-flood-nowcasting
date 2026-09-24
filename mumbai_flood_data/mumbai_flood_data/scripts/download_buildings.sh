#!/usr/bin/env bash
# Mumbai building footprints from OSM via Overpass API.
# Buildings are numerous (100k+) - this queries a tighter 2-5km buffer bbox and may need
# splitting by ward if the public Overpass instance times out.
set -e
OUT=../05_buildings
mkdir -p "$OUT"

curl -s -X POST "https://overpass-api.de/api/interpreter" --data-urlencode data@- << 'QUERY' -o "$OUT/buildings_raw.json"
[out:json][timeout:300][maxsize:1073741824];
(
  way["building"](18.87,72.77,19.28,72.96);
  relation["building"](18.87,72.77,19.28,72.96);
);
out body;
>;
out skel qt;
QUERY

npx osmtogeojson "$OUT/buildings_raw.json" > "$OUT/buildings.geojson"
echo "Done."
