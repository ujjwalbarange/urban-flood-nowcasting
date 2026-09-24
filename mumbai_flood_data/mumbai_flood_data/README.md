# Mumbai Urban Flood Nowcasting — Data Collection Package

## Start here
1. Read `DATA_CATALOG.md` — status of every requested dataset (verified/scripted vs. genuinely
   unavailable).
2. Read `MISSING_DATA.md` — the honest gaps, why, and their downstream impact.
3. Run `scripts/download_all.sh` (or the individual scripts) on a machine with internet access to
   actually pull the P0/P1 files — see below for why that step couldn't run inside this session.

## Why this package is scripts + verified sources, not fully-downloaded binaries
This was assembled in a sandboxed environment with:
- **No live network access** for bulk downloads (no `wget`/`curl`/`aws s3` to real servers), and
- **No ability to call parameterized APIs** (Overpass queries, DEM-by-bbox requests, dated rainfall
  queries) — only URLs that already appeared in a web search result could be re-fetched, and even
  then, pulling a 700KB+ GeoJSON through the chat context risks silently truncating geometries, which
  the task explicitly forbids ("do NOT silently modify original datasets").

So every dataset below was **verified live** — confirmed to exist, be free, be publicly accessible,
and its exact URL/license/format captured — and small text files (population CSV, synthetic rainfall)
were generated/saved directly. Everything else has a ready-to-run script with the exact real command.

## Folder structure
```
01_city/            Mumbai boundary + 24 wards (scripted, ODbL-1.0)
02_dem/              Copernicus GLO-30 DEM (scripted, needs free OpenTopography API key)
03_land_cover/       ESA WorldCover 10m (scripted, no auth, AWS S3)
04_roads/            OSM road network (scripted, Overpass API)
05_buildings/        OSM building footprints (scripted, Overpass API)
06_drainage/         NOT PUBLICLY AVAILABLE - see metadata.json for full investigation
07_rainfall/         Open-Meteo historical (scripted) + IMERG (template, needs Earthdata login)
                      + MOSDAC (template, needs YOUR MOSDAC login) + gauges (documented gap)
08_flood_observations/  India Flood Inventory v3 + NDEM inundation (scripted, national -> filter)
09_population/       Ward-level Census 2011 (scripted)
10_shelters/         NOT PUBLICLY AVAILABLE - see metadata.json
11_coastal/          OSM coastline (scripted) + INCOIS tide (documented as live source)
12_synthetic/        4 synthetic rainfall test scenarios - ALREADY GENERATED in this package
13_api_information/  Full API/access docs for Open-Meteo, MOSDAC, IMERG, gauges, DEM/WorldCover/OSM
scripts/             Every download command as a ready-to-run .sh/.py file
DATA_CATALOG.md       Master status table
MISSING_DATA.md       Honest gap report
```

## Two things only you can complete (need your own free accounts)
- **OpenTopography API key** (free, instant): https://portal.opentopography.org/myopentopo — needed
  for `scripts/download_dem.sh`
- **NASA Earthdata login** (free, instant): https://urs.earthdata.nasa.gov/users/new — needed for
  `scripts/download_imerg.py`
- **MOSDAC** — you said you already have this; fill in `scripts/download_mosdac.py` with your own
  credentials (never share these with an AI assistant).

## Requirements to run the scripts
`pip install geopandas pandas requests`, `aws-cli` v2, Node.js (for `osmtogeojson`, or swap in Python's
`osm2geojson`), `curl`.
