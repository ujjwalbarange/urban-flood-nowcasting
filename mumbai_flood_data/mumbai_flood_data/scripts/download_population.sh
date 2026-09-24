#!/usr/bin/env bash
set -e
OUT=../09_population
mkdir -p "$OUT"
curl -L -o "$OUT/ward_level_census2011.csv" \
  "https://raw.githubusercontent.com/mickeykedia/Mumbai-Population-Map/master/Ward_Level_Data.csv"
echo "Done. Attribute: Census of India 2011, collated by github.com/mickeykedia/Mumbai-Population-Map"
