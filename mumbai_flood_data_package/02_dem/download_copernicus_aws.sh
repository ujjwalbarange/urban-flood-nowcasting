#!/usr/bin/env bash
# Script to download Copernicus GLO-30 DEM tiles directly from AWS Open Data (Free, no login required)
set -euo pipefail

TILES=(
  "Copernicus_DSM_COG_10_N18_00_E072_00_DEM"
  "Copernicus_DSM_COG_10_N19_00_E072_00_DEM"
)

OUT_DIR="$(dirname "$0")/copernicus_glo30"
mkdir -p "$OUT_DIR"

for TILE in "${TILES[@]}"; do
  URL="https://copernicus-dem-30m.s3.amazonaws.com/${TILE}/${TILE}.tif"
  echo "Downloading ${TILE} from AWS S3..."
  curl -L -o "${OUT_DIR}/${TILE}.tif" "$URL"
done

echo "Copernicus GLO-30 download complete."
