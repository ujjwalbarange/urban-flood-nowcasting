# Mumbai Urban Flood Nowcasting — Data Catalog

**Compiled:** 2026-09-23
**Important caveat on "downloaded" status:** This package was assembled inside a sandboxed research
session with no live network access for bulk file transfer. Every source below was verified live
(via web search / page fetch) to confirm it exists, is free, is publicly accessible, and to capture
its exact URL, license, and format. Small text files were saved directly into this package where
possible. Large or binary files (DEM tiles, WorldCover rasters, OSM extracts, national GeoJSONs) were
**not** pulled through this session, to avoid silently truncating/corrupting geometry data — instead,
`scripts/*.sh` and `scripts/*.py` contain the exact, ready-to-run commands to fetch them for real on
any machine with internet access. Run `scripts/download_all.sh` (P0 items) after filling in the two
required API keys (OpenTopography, free; NASA Earthdata, free).

| # | Dataset | Status | Source | Format | Resolution | Coverage | File/API | License | Quality | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Mumbai 24 wards | Verified, script ready | OpenCity/Oorvani via bharatlas | GeoJSON | ward polygons | 24 wards | File | ODbL-1.0 | High | `scripts/download_boundaries.sh` |
| 2 | Mumbai electoral wards (2017) | Verified, script ready | OpenCity via bharatlas | GeoJSON | 227 wards | Mumbai | File | ODbL-1.0 | High | Supplementary |
| 3 | Municipal boundary | Derived (dissolve of wards) | — | GeoJSON | — | Mumbai | File (derived) | ODbL-1.0 | Medium | No standalone official file found |
| 4 | Copernicus DEM GLO-30 | Verified, script ready | ESA/OpenTopography | GeoTIFF | ~30m | Mumbai bbox | API (free key) or AWS S3 (no auth) | Copernicus DEM license | High | DSM, not DTM |
| 5 | CartoDEM (India DEM) | NOT VERIFIED | ISRO Bhuvan | — | — | — | Requires Bhuvan account | — | — | See MISSING_DATA.md |
| 6 | ESA WorldCover 10m | Verified, script ready | ESA/VITO via AWS | COG GeoTIFF | 10m | 1 tile (N18E072) | AWS S3 (no auth) | CC-BY 4.0 | High | 2021 v200 |
| 7 | OSM roads | Verified, script ready | OpenStreetMap | GeoJSON | vector | Mumbai+5km | Overpass API | ODbL 1.0 | High | |
| 8 | OSM buildings | Verified, script ready | OpenStreetMap | GeoJSON | vector | Mumbai+2-5km | Overpass API | ODbL 1.0 | Medium-High | Informal-settlement under-coverage |
| 9 | Storm-water drainage | **NOT PUBLICLY AVAILABLE / NOT VERIFIED** | — | — | — | — | — | — | — | See `06_drainage/metadata.json` and MISSING_DATA.md |
| 10 | Historical rainfall (ERA5) | Verified, script ready | Open-Meteo Archive API | JSON→CSV | ~9-25km | 5 sample points, 2015-2025 | API (keyless) | CC-BY 4.0 | Medium (reanalysis) | |
| 11 | IMD gauge data (Santacruz/Colaba) | **NOT PUBLICLY AVAILABLE as bulk file** | IMD | — | — | — | — | — | — | See `07_rainfall/gauges/metadata.json` |
| 12 | GPM IMERG | Verified, template script | NASA GES DISC | NetCDF/JSON | 0.1° | Mumbai subset | API (free Earthdata login) | Open/free | High | |
| 13 | MOSDAC products | Investigated, access documented | ISRO MOSDAC | varies | varies | India | API (user's own login) | Govt of India | — | See `13_api_information/mosdac.md` |
| 14 | 26 July 2005 flood | Narrative sources only | Wikipedia, NIDM, academic PDFs | text/PDF figures | — | Mumbai | Web pages | varies | Low as GIS | Not machine-readable geometry |
| 15 | India Flood Inventory v3 | Verified, script ready | github via bharatlas | GeoJSON (national) | event polygons | filter to Mumbai | File | CC-BY-4.0 | Medium-High | Includes 2005 event (verify after filter) |
| 16 | NDEM flood inundation 1998-2022 | Verified, script ready | NRSC/ISRO via bharatlas | GeoJSON (national) | satellite-derived | filter to Mumbai | File | CC0-1.0 | High | |
| 17 | Ward population (Census 2011) | Verified, script ready | Census of India via GitHub | CSV | ward-level | 24 wards | File | Public/Open Govt data | High | 2011 is most recent full census |
| 18 | Gridded population (WorldPop) | NOT DOWNLOADED (documented) | WorldPop | GeoTIFF | ~100m | national, clip locally | File | CC-BY 4.0 | High | Optional enhancement |
| 19 | Emergency/flood shelters | **NOT PUBLICLY AVAILABLE** | — | — | — | — | — | — | — | See `10_shelters/metadata.json` |
| 20 | Coastline | Verified, script ready | OpenStreetMap | GeoJSON | vector | Mumbai coast | Overpass API | ODbL 1.0 | Medium-High | |
| 21 | Tide data | Live source, documented | INCOIS | portal/tables | — | Mumbai station | Portal (no stable bulk API confirmed) | Govt of India | High | Treat as live per API-vs-file rule |
| 22 | Synthetic rainfall scenarios | **Generated** (included in this package) | — | CSV | 15-min | N/A | File | N/A | N/A (synthetic) | light/moderate/heavy/extreme |

## Bonus context layers found (not explicitly requested, but useful for hydrology context)
All verified live via bharatlas.com, same license-per-layer caveat as above — check each layer's
license before use:
- Rivers + streams (national, CWC WRIS, CC0-1.0) — clip to Mumbai for the Mithi River and creeks
- Waterbodies (national, CWC WRIS, CC0-1.0)
- Reservoirs and dams (national, CWC WRIS / Bharatmaps, CC0-1.0)
- Seismic hazard zones (national, BIS IS 1893:2016, GODL-India)
- SRA slum boundaries (Mumbai-specific, via `github.com/sanjanakrishnan/mumbai_spatial_data`) — useful
  for flagging likely OSM-building under-coverage areas

## How to actually get the files
```bash
cd mumbai_flood_data/scripts
export OPENTOPO_API_KEY=your_free_opentopography_key
./download_all.sh
```
See each script for the exact commands/URLs if you'd rather run them individually or adapt them.
