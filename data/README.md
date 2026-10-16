# Mumbai Urban Flood Data Platform (Phase 1)

This directory forms the verified **Data Foundation** for the Mumbai Urban Flood Nowcasting and Decision Support System (MUFNS).

All development in Phase 1 was strictly restricted to data auditing, structuring, ingestion, and validation. **No dashboard, UI, or dummy simulation data has been created or modified.**

---

## 1. Directory Structure

```text
data/
├── raw/                                # Immutable raw source files (NEVER overwritten)
│   ├── administrative_boundaries/     # MCGM ward polygons, municipal boundaries
│   ├── buildings/                     # Building footprint samples
│   ├── critical_infrastructure/       # OSM emergency facilities raw JSON
│   ├── dem/                           # Original CartoDEM & Copernicus DEM tiles
│   ├── drainage/                      # BRIMSTOWAD nodes, links, outfalls
│   ├── historical_floods/             # Ground-truth 2016-2025 flood observations, chronic spots
│   ├── landuse/                       # ESA WorldCover 10m raster subset
│   ├── population/                    # Census ward population GeoJSON
│   ├── rainfall/                      # 10-year gauge series (2015-2025), extreme storm hyetographs
│   ├── roads/                         # OSM arterial roads and railway raw extracts
│   ├── satellite/                     # NASA GPM IMERG 2005 grid, INSAT-3D sample
│   ├── shelters/                      # Municipal relief shelter points
│   ├── terrain/                       # Copernicus GLO-30 30m DEM GeoTIFF (OpenTopography)
│   ├── tides/                         # Apollo Bunder hourly tide observations (2005) & benchmarks
│   └── weather/                       # Open-Meteo raw multi-station JSON responses
│
├── processed/                          # Cleaned, standardized GeoJSON and CSV datasets
│   ├── critical_infrastructure/       # 1,817 emergency healthcare & disaster facilities
│   ├── rainfall/                      # Standardized rainfall observations and forecasts
│   ├── rivers/                        # 1,730 waterways, rivers, streams, and nullahs
│   ├── roads/                         # 165 suburban railway and metro transit stations
│   └── weather/                       # 108 observations & 30,240 hourly forecasts (+168h lead time)
│
├── derived/                            # Hydrological rasters derived from 30m Copernicus DEM
│   ├── catchments/                    # Depression sinks raster (morphological ponding)
│   ├── flow_direction/                # D8 steepest-descent flow direction raster
│   └── slope/                         # Horn 8-neighbor slope and aspect rasters
│
├── metadata/                           # Schemas, source catalog, data dictionaries, reports
│   ├── data_quality_report.json       # Structured audit findings
│   ├── data_quality_summary.md        # Quality summary matrix
│   ├── schemas/                       # postgis_schema.sql
│   └── source_catalog/                # sources.json & required_access.md
│
├── scripts/                            # Reusable ingestion, derivation, and validation scripts
│   ├── ingestion/                     # migrate_raw_package.py, ingest_openmeteo.py,
│   │                                  # ingest_osm_water_and_infrastructure.py,
│   │                                  # fetch_railways.py, load_postgis.py
│   ├── transformation/                # derive_terrain.py
│   └── validation/                    # run_data_quality_checks.py, deep_db_audit.py,
│                                      # deep_file_audit.py, dump_schema.py
│
├── manifests/                          # Cryptographic checksums (SHA-256) of all raw files
│   └── raw_datasets_manifest.json
│
├── schema.sql                         # Complete verified DDL dump from live PostgreSQL 18.6 DB
├── DATA_INVENTORY.md                  # Comprehensive dataset-by-dataset inventory
├── DATA_GAPS.md                       # Explicit catalog of missing engineering data & access
├── PHASE_1_VERIFICATION.md            # Evidence-based database & file verification report
└── README.md                          # This document
```

---

## 2. Core Data Principles

1. **Zero Data Fabrication:**
   - No synthetic rainfall observations, fake flood depths, fabricated drainage inverts, or artificial building populations are generated.
   - Where a field is unverified from official sources (such as `shelters.capacity_persons`), it is strictly preserved as **`NULL`**.
2. **Raw Immutability:**
   - Raw source files in `data/raw/` are immutable and never overwritten. SHA-256 hashes are recorded in `data/manifests/raw_datasets_manifest.json`.
3. **Data Provenance:**
   - Every database record preserves its source provider, ingestion timestamp, and quality flag.
4. **PostGIS Standardization:**
   - All spatial layers are standardized in `EPSG:4326` (WGS84) with GIST spatial indexes.
   - Projected metric analysis (area, slope gradient, distance) utilizes UTM Zone 43N (`EPSG:32643`).

---

## 3. Live Database Summary (`defaultdb`)

Verified against Aiven Cloud PostgreSQL 18.6 + PostGIS 3.6.4:

- **Total Base Tables:** 25 base tables (+ 2 PostGIS catalog views = 27 total relations).
- **Total Application Data Rows:** **34,506 authentic rows**.
  - `weather_forecasts`: **30,240 rows** (9 stations × 20 variables × 168 hours lead time)
  - `critical_infrastructure`: **2,002 rows** (Hospitals, clinics, railway stations, police, fire)
  - `water_bodies`: **1,730 rows** (81 rivers, 724 drainage nullahs, 236 streams, 680 water bodies)
  - `historical_flood_events`: **209 rows** (2016–2025 ground truth with measured depth in cm)
  - `weather_observations`: **108 rows** (9 surface monitoring stations × 12 variables)
  - `tide_observations`: **72 rows** (Apollo Bunder hourly water levels during 2005 deluge)
  - `drainage_nodes` & `links`: **43 rows** (BRIMSTOWAD trunk network)
  - `wards`: **24 rows** (Greater Mumbai A through T municipal wards; 12.4M population)
  - `shelters`: **10 rows** (Designated municipal emergency relief centers)
  - `pumping_stations`: **8 rows** (4,680 MLD total rated discharge capacity)
  - `dem_tiles` & `terrain_derivatives`: **5 rows** (Copernicus GLO-30 DSM baseline + 4 derivatives)

---

## 4. How to Reproduce Ingestion & Validation

Ensure Python 3.11 is active and dependencies are installed (`shapely`, `numpy`, `scipy`, `pandas`, `tifffile`, `asyncpg`, `python-dotenv`).

### Step 1: Migrate Canonical Raw Datasets & Verify Checksums
```bash
python data/scripts/ingestion/migrate_raw_package.py
```

### Step 2: Compute Physical Terrain Derivatives from 30m Copernicus DEM
```bash
python data/scripts/transformation/derive_terrain.py
```

### Step 3: Ingest Multi-Station Live Weather & 168h Forecasts
```bash
python data/scripts/ingestion/ingest_openmeteo.py
```

### Step 4: Ingest OpenStreetMap Hydrography & Emergency Assets
```bash
python data/scripts/ingestion/ingest_osm_water_and_infrastructure.py
python data/scripts/ingestion/fetch_railways.py
```

### Step 5: Execute Resilient Batch Ingestion into PostgreSQL / PostGIS
```bash
python data/scripts/ingestion/load_postgis.py
```

### Step 6: Execute Automated Data Quality & Integrity Checks
```bash
python data/scripts/validation/run_data_quality_checks.py
```

### Step 7: Perform Deep Programmatic Verification Against Database
```bash
python data/scripts/validation/deep_db_audit.py
python data/scripts/validation/deep_file_audit.py
python data/scripts/validation/dump_schema.py
```

---

## 5. Key Documentation Files

- **[PHASE_1_VERIFICATION.md](file:///e:/urban/sih/urban-flood-nowcasting/data/PHASE_1_VERIFICATION.md)**: Evidence-based verification report covering every specific claim, column definitions, table counts, and discrepancies.
- **[DATA_INVENTORY.md](file:///e:/urban/sih/urban-flood-nowcasting/data/DATA_INVENTORY.md)**: Dataset-by-dataset technical specifications (provenance, resolution, CRS, format, hash).
- **[DATA_GAPS.md](file:///e:/urban/sih/urban-flood-nowcasting/data/DATA_GAPS.md)**: Explicit catalog of unobtained engineering layers (drainage inverts, radar, full building coverage).
- **[schema.sql](file:///e:/urban/sih/urban-flood-nowcasting/data/schema.sql)**: DDL schema dump of the 25 base tables in PostgreSQL 18.6.
