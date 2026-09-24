#!/usr/bin/env bash
# Copernicus GLO-30 DEM for Mumbai + buffer bbox.
# Option A: OpenTopography API (needs free API key from https://portal.opentopography.org/myopentopo)
set -e
OUT=../02_dem/copernicus_glo30
mkdir -p "$OUT"
API_KEY="${OPENTOPO_API_KEY:?Set OPENTOPO_API_KEY env var (free key from opentopography.org)}"

curl -L -o "$OUT/mumbai_glo30.tif" \
  "https://portal.opentopography.org/API/globaldem?demtype=COP30&south=18.85&north=19.30&west=72.75&east=72.98&outputFormat=GTiff&API_Key=${API_KEY}"

echo "Downloaded. Validate with: gdalinfo $OUT/mumbai_glo30.tif"

# --- Option B: no-auth AWS bulk (uncomment to use instead) ---
# aws s3 ls s3://raster/COP30/ --recursive --endpoint-url https://opentopography.s3.sdsc.edu --no-sign-request | grep -i "N18\|N19"
# aws s3 cp s3://raster/COP30/<tile-name>.tif "$OUT/" --endpoint-url https://opentopography.s3.sdsc.edu --no-sign-request
