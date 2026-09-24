#!/usr/bin/env bash
set -e
OUT=../08_flood_observations/historical_events
mkdir -p "$OUT"
curl -L -o "$OUT/INDIA_FLOOD_INVENTORY_V3.geojson" \
  "https://bharatlas.com/api/dl/environment/flood-inventory/INDIA_FLOOD_INVENTORY_V3.geojson"
curl -L -o "$OUT/NDEM_All_India_Flood_Innundation_1998_to_2022.geojson" \
  "https://bharatlas.com/api/dl/environment/ndem-floods-1998-2022/NDEM_All_India_Flood_Innundation_1998_to_2022.geojson"
echo "Downloaded national files - now run: python3 ../scripts/filter_flood_inventory.py"
