#!/usr/bin/env bash
# Run this on a machine with internet access (this chat sandbox has none).
# Downloads verified, license-clear boundary files for Mumbai.
set -e
OUT=../01_city
mkdir -p "$OUT"

echo "Mumbai (BMC) 24 wards - ODbL-1.0 - OpenCity/Oorvani Foundation via bharatlas"
curl -L -o "$OUT/wards.geojson" \
  "https://bharatlas.com/api/dl/admin/wards-mumbai/wards_mumbai.geojson"

echo "Mumbai Electoral Wards 2017 (227 wards, supplementary) - ODbL-1.0"
curl -L -o "$OUT/electoral_wards_2017.geojson" \
  "https://bharatlas.com/api/dl/electoral/wards-mumbai-2017/electoral_wards_mumbai_2017.geojson"

echo "Deriving a single dissolved municipal boundary from the wards layer..."
python3 - << 'PY'
import geopandas as gpd
gdf = gpd.read_file("../01_city/wards.geojson")
boundary = gdf.dissolve()
boundary.to_file("../01_city/mumbai_boundary.geojson", driver="GeoJSON")
print("Wrote mumbai_boundary.geojson (dissolved from wards)")
PY

echo "Done. Validate with: python3 -c \"import geopandas as gpd; print(gpd.read_file('../01_city/wards.geojson').shape)\""
