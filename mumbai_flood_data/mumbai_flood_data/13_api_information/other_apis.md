# Other APIs / Access Methods Documented (DEM, Land Cover, OSM)

## OpenTopography Global DEM API (Copernicus GLO-30)
- **Endpoint:** `https://portal.opentopography.org/API/globaldem`
- **Auth:** free personal API key (instant, self-service signup) at https://portal.opentopography.org/myopentopo
- **Example request:**
  `https://portal.opentopography.org/API/globaldem?demtype=COP30&south=18.85&north=19.30&west=72.75&east=72.98&outputFormat=GTiff&API_Key=YOUR_API_KEY`
- **No-auth alternative (AWS CLI, bulk):**
  ```
  aws s3 ls s3://raster/COP30/ --recursive --endpoint-url https://opentopography.s3.sdsc.edu --no-sign-request
  aws s3 cp s3://raster/COP30/<tile>.tif . --endpoint-url https://opentopography.s3.sdsc.edu --no-sign-request
  ```
- Docs: https://portal.opentopography.org/raster?opentopoID=OTSDEM.032021.4326.3

## ESA WorldCover (AWS Open Data, no auth)
- **Bucket:** `s3://esa-worldcover/v200/2021/map/` (2021 edition) or `s3://esa-worldcover/v100/2020/map/` (2020 edition)
- **No auth needed:** `--no-sign-request`
- **Example:**
  ```
  aws s3 sync s3://esa-worldcover/v200/2021/map /local/path --no-sign-request --exclude "*" --include "*N18E072*"
  ```
- **Grid reference file** (to confirm exact Mumbai tile name): https://esa-worldcover.s3.eu-central-1.amazonaws.com/esa_worldcover_grid.geojson
- Docs: https://esa-worldcover.org/en/data-access

## OpenStreetMap Overpass API (roads, buildings, coastline)
- **Endpoint:** `https://overpass-api.de/api/interpreter` (mirrors: `https://lz4.overpass-api.de/api/interpreter`, `https://overpass.kumi.systems/api/interpreter`)
- **Auth:** none
- **Example Overpass QL** (roads within Mumbai+5km bbox):
  ```
  [out:json][timeout:180];
  (
    way["highway"](18.85,72.75,19.30,72.98);
  );
  out body;
  >;
  out skel qt;
  ```
- Convert the JSON response to GeoJSON with `osmtogeojson` (Node.js CLI/library) or `osm2geojson` (Python).
- **Rate limiting:** be considerate - one bbox query per dataset (roads, buildings, coastline), not per-ward, to avoid hammering the free public instance. For buildings (likely 100k+ features), consider splitting into ward-sized sub-queries if a single query times out (>180s).
- License: ODbL 1.0, attribution "\u00a9 OpenStreetMap contributors" required.

## bharatlas.com (aggregator used for boundaries, flood inventory, rivers, dams, etc.)
- **No auth, direct file downloads**, e.g.:
  `https://bharatlas.com/api/dl/admin/wards-mumbai/wards_mumbai.geojson`
- Each dataset's license is stated per-layer on https://bharatlas.com (mix of ODbL-1.0, CC-BY-4.0, CC0-1.0, GODL-India depending on the underlying original source - always check the specific layer's license before redistribution, not just this file's summary)
- Underlying original sources credited by bharatlas: OpenCity/Oorvani Foundation, DataMeet India, CWC WRIS (indiawris.gov.in), Bharatmaps (NIC), Local Government Directory (LGD), NDEM/NRSC/ISRO
