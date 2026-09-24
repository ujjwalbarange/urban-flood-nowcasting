#!/usr/bin/env bash
# Master runner. Run from inside the scripts/ directory, on a machine WITH internet access.
# Requires: curl, python3 (+ geopandas, pandas, requests), aws-cli v2, node (for osmtogeojson).
set -e
echo "=== P0 datasets ==="
./download_boundaries.sh
./download_dem.sh          # requires OPENTOPO_API_KEY env var
./download_landcover.sh    # requires aws-cli
./download_roads.sh        # requires npx/osmtogeojson
./download_rainfall.py
./download_flood_observations.sh
python3 filter_flood_inventory.py

echo "=== P1 datasets ==="
./download_buildings.sh
./download_population.sh
./download_coastline.sh
echo "IMERG and MOSDAC require personal credentials - fill in and run"
echo "  download_imerg.py and download_mosdac.py manually."

echo "=== Done. See ../DATA_CATALOG.md and ../MISSING_DATA.md for what remains manual. ==="
