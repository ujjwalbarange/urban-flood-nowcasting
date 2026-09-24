#!/usr/bin/env bash
# ESA WorldCover 10m, Mumbai tile (N18E072), no auth needed.
set -e
OUT=../03_land_cover
mkdir -p "$OUT"

# Confirm exact tile name first (grid is 3x3deg, SW-corner named):
curl -sL "https://esa-worldcover.s3.eu-central-1.amazonaws.com/esa_worldcover_grid.geojson" -o /tmp/wc_grid.geojson
python3 -c "
import json
g = json.load(open('/tmp/wc_grid.geojson'))
for f in g['features']:
    props = f['properties']
    name = props.get('ll_tile') or props.get('tile') or str(props)
    if 'N18E072' in str(props):
        print(props)
"

aws s3 sync s3://esa-worldcover/v200/2021/map "$OUT" --no-sign-request \
  --exclude "*" --include "*N18E072*"

mv "$OUT"/*.tif "$OUT/worldcover.tif" 2>/dev/null || true
echo "Done. Validate with: gdalinfo $OUT/worldcover.tif"
