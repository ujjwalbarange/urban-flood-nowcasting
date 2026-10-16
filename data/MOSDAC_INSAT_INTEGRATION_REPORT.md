# ISRO MOSDAC INSAT-3DR Satellite Rainfall Integration Report (2024–2025)
**Mumbai Urban Flood Nowcasting System (MUFNS)**  
**Dataset Label:** *"Event-based INSAT-3DR rainfall observations for 2024–2025"*  
**Integration Status:** **VERIFIED & OPERATIONAL**  
**Date:** September 26, 2026  

---

## 1. Executive Summary

This report documents the audit, quality control, canonical organization, PostGIS database ingestion, and multi-sensor fusion engine integration of the ISRO MOSDAC INSAT-3DR rainfall dataset for the Mumbai metropolitan region and its oceanic storm approach corridor.

The dataset consists of **1,073 GeoTIFF raster granules** spanning historical heavy rainfall and cloudburst flood events in 2024 and 2025, covering:
- **Primary Product (HEM):** `3RIMG_L2B_HEM` — INSAT-3DR Hydro-Estimator precipitation product (**644 granules**).
- **Secondary / Validation Product (IMC):** `3RIMG_L2B_IMC` — INSAT-3DR Imager precipitation retrieval product (**429 granules**).

In strict accordance with project data governance:
1. **Zero Fabrication**: These are event-centric windows. No missing timestamps or dates have been synthetically interpolated or fabricated.
2. **Database Integrity**: The existing PostGIS database schema, GPM IMERG satellite observations (576 granules), automatic weather stations (27 gauges), numerical weather prediction forecasts (30,240 cells), tide predictions (72 records), and high-resolution urban terrain/drainage layers were preserved completely untouched.
3. **Dual Spatial Handling**: The wider 1.01° × 1.01° satellite corridor (`[71.997°E, 17.996°N, 73.010°E, 19.009°N]`), capturing offshore convective systems advancing from the Arabian Sea, is fully preserved as raster arrays and envelope geometries, alongside derived statistics for the Greater Mumbai operational core (`[72.77°E, 18.89°N, 73.04°E, 19.34°N]`).
4. **Independent Fusion**: HEM and IMC are maintained strictly segregated in database records and services, enabling configurable selection (`HEM only`, `IMC only`, `GPM only`, `GPM + HEM`, `GPM + IMC`, `FULL FUSION`).

---

## 2. Dataset Inventory & Canonical Organization

### 2.1 File Count and Storage Footprint
The raw files delivered in `MOSDAC_INSAT_DATA` were organized into canonical directory trees under `data/processed/rainfall/insat3dr/` without modifying or deleting the raw source directories:

| Product | Product Level | Year | Granule Count | Total Disk Size | Canonical File Path |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **HEM** (Hydro-Estimator) | L2B | 2024 | 244 | 827 KB | `data/processed/rainfall/insat3dr/HEM/2024/` |
| **HEM** (Hydro-Estimator) | L2B | 2025 | 400 | 837 KB | `data/processed/rainfall/insat3dr/HEM/2025/` |
| **IMC** (Imager Retrieval) | L2B | 2024 | 429 | 577 KB | `data/processed/rainfall/insat3dr/IMC/2024/` |
| **Total Ingested** | — | — | **1,073** | **2.19 MB** | — |

### 2.2 Flood Event Windows Covered
The files correspond to three major monsoon flood episodes:

1. **Event 1 — July 2024 Mumbai Monsoon Deluge (July 7–11, 2024)**:
   - **HEM granules**: 244 (2024-07-07 13:45 UTC to 2024-07-11 23:45 UTC)
   - **IMC granules**: 237 (2024-07-07 14:15 UTC to 2024-07-11 23:45 UTC)
   - **Total granules**: 481
   - **Context**: Encompasses the extreme July 8, 2024 cloudburst event where Mumbai recorded >300 mm within 6 hours. Peak HEM precipitation rate reached **98.74 mm/hr**.
2. **Event 2 — Late-July 2024 Active Monsoon Pulse (July 23–26, 2024)**:
   - **IMC granules**: 192 (2024-07-23 00:15 UTC to 2024-07-26 23:45 UTC)
   - **Context**: 4-day continuous secondary validation retrieval series during intense Arabian Sea squall lines. Peak IMC rate reached **60.00 mm/hr**.
3. **Event 3 — August 2025 Mumbai Monsoon Deluge (August 13–21, 2025)**:
   - **HEM granules**: 400 (2025-08-13 00:15 UTC to 2025-08-21 23:45 UTC)
   - **Context**: 9-day active monsoon trough convergence over the Konkan coast. Peak HEM precipitation rate reached **66.98 mm/hr**.

---

## 3. Comprehensive Quality Control (QA) Results

Every one of the 1,073 GeoTIFF raster granules was programmatically evaluated across 10 QA criteria prior to ingestion:

| QA Criterion | Verification Method | Result | Status |
| :--- | :--- | :--- | :--- |
| **1. CRS Consistency** | Rasterio CRS inspection on all 1,073 files | 100% EPSG:4326 (WGS 84 geographic coordinates) | **PASS** |
| **2. Spatial Bounds** | Extent comparison against `[71.997°E, 17.996°N, 73.010°E, 19.009°N]` | Identical bounding envelope across all 1,073 files | **PASS** |
| **3. Temporal Ordering** | Chronological sorting by parsed acquisition timestamp | Monotonically non-decreasing timestamps | **PASS** |
| **4. Duplicate Timestamps** | Collision checks per product (`HEM` vs `IMC`) | **0 duplicates**. Rapid scans (e.g. 06:15 and 06:16 UTC) possess distinct minutes. | **PASS** |
| **5. Duplicate Files** | SHA-256 hash comparison across granules | **0 hash collisions** across different observation times | **PASS** |
| **6. NoData Handling** | Value inspection: GeoTIFF declared `-999.0` + ISRO sensor offline flag `-99.0` | Ingestion & query pipelines mask all values `< 0.0` as `NULL`. | **PASS** |
| **7. Physically Unreasonable Values** | Range check: `0.0 <= rain <= 250.0 mm/hr` | All valid pixels fall within `[0.0, 98.74 mm/hr]`. Zero negative or infinite values. | **PASS** |
| **8. Raster Alignment** | Grid dimension and resolution verification | 28 × 28 pixels (784 cells), dx = dy = 0.036177° (~4.0 km native INSAT-3DR) | **PASS** |
| **9. Missing Event Windows** | Temporal gap analysis against continuous year | Event-centric windows clearly documented and labeled. | **PASS** |
| **10. HEM/IMC Availability** | Granule concurrency comparison | July 7–11, 2024 has concurrent HEM & IMC pairs. July 23–26 is IMC only. August 13–21 is HEM only. | **PASS** |

### 3.1 Special QA Findings & Corrections
- **ISRO Sensor Offline Masking**: File `3RIMG_11JUL2024_2015_L2B_HEM_V01R00_HEM.tif` contains 784 pixels all reading `-99.0`. While the GeoTIFF tag sets `nodata = -999.0`, `-99.0` is the standard ISRO flag for satellite deep-space calibration or channel dropout. The ingestion engine correctly parsed this file as `valid_pixels = 0` with `mean_value = NULL` and `max_value = NULL`, preventing erroneous negative rainfall values.
- **Rapid Sector Scans**: On July 11, 2024, 60 granules were retrieved rather than 48 half-hourly steps due to ISRO rapid sector scans over western India (e.g. 06:15 UTC followed by 06:16 UTC). Both granules are retained as distinct temporal records.

---

## 4. PostgreSQL / PostGIS Database Architecture

### 4.1 Table Schema: `public.satellite_rainfall_observations`
To store these satellite rasters efficiently without converting 841,232 individual raster cells into bloated vector geometries, a dedicated raster observation table was implemented:

```sql
CREATE TABLE IF NOT EXISTS public.satellite_rainfall_observations (
    observation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    satellite VARCHAR(32) NOT NULL,              -- 'INSAT-3DR'
    sensor VARCHAR(32) NOT NULL,                 -- 'IMAGER'
    product VARCHAR(32) NOT NULL,                -- 'HEM' or 'IMC'
    product_level VARCHAR(16) NOT NULL,          -- 'L2B'
    observation_time TIMESTAMPTZ NOT NULL,       -- Acquisition timestamp (UTC)
    year INT NOT NULL,                           -- 2024, 2025
    event_name VARCHAR(128),                     -- Flood event window identifier
    geometry geometry(Polygon, 4326) NOT NULL,   -- Spatial bounding envelope
    raster_width INT NOT NULL,                   -- 28
    raster_height INT NOT NULL,                  -- 28
    spatial_resolution_deg DOUBLE PRECISION NOT NULL, -- 0.03617716
    min_value DOUBLE PRECISION,                  -- Minimum valid rate (mm/hr)
    max_value DOUBLE PRECISION,                  -- Maximum valid rate (mm/hr)
    mean_value DOUBLE PRECISION,                 -- Mean rate over 1x1 approach corridor
    p50_value DOUBLE PRECISION,                  -- Median rate (mm/hr)
    p90_value DOUBLE PRECISION,                  -- 90th percentile rate (mm/hr)
    p99_value DOUBLE PRECISION,                  -- 99th percentile rate (mm/hr)
    valid_pixel_count INT NOT NULL,              -- Count of pixels >= 0.0
    nodata_value DOUBLE PRECISION NOT NULL,      -- -999.0
    mumbai_core_mean_value DOUBLE PRECISION,     -- Clipped core Mumbai mean (mm/hr)
    mumbai_core_max_value DOUBLE PRECISION,      -- Clipped core Mumbai max (mm/hr)
    source VARCHAR(64) NOT NULL,                 -- 'MOSDAC'
    source_file VARCHAR(256) NOT NULL,           -- Canonical file path
    file_hash VARCHAR(64) NOT NULL,              -- SHA-256 checksum
    ingestion_run_id UUID REFERENCES data_ingestion_runs(run_id),
    grid_data JSONB,                             -- 28x28 2D array of rainfall rates (mm/hr)
    attributes JSONB,                            -- Additional satellite metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_insat_product_time UNIQUE (satellite, product, observation_time)
);
```

### 4.2 Indexes & Performance Optimizations
- **Spatial Index**: `idx_sat_rain_geom ON satellite_rainfall_observations USING GIST(geometry);`
- **Temporal Index**: `idx_sat_rain_time ON satellite_rainfall_observations(observation_time DESC);`
- **Product Lookup**: `idx_sat_rain_prod_time ON satellite_rainfall_observations(product, observation_time DESC);`
- **Year & Event Lookup**: `idx_sat_rain_year_event ON satellite_rainfall_observations(year, event_name);`

### 4.3 Provenance Registration
- **Data Source**: Registered in `public.data_sources` with `source_code = 'isro_mosdac_insat3dr'`, category `'meteorology'`, provider `'ISRO / SAC / MOSDAC'`, update frequency `'event_based'`.
- **Ingestion Run**: Recorded in `public.data_ingestion_runs` with ID `59ee564c-f4e0-4e37-baf3-b3b18cf5190b`, records processed = 1,073, records inserted = 1,073, errors = 0, status = `'SUCCESS'`.

---

## 5. Rainfall Fusion & Modeling Interface

To expose INSAT-3DR data to the flood simulation and nowcasting engines, two unified Python service modules were implemented in `services/rainfall/`:

### 5.1 `INSAT3DRProvider` (`services/rainfall/insat_service.py`)
Implements the abstract `RainfallProvider` interface:
- `fetch_current(product="HEM")`: Retrieves the latest available observation with raster grid and stats.
- `fetch_historical(start_time, end_time, product="HEM")`: Returns chronological granules within any requested event window.
- `get_raster_grid(observation_id)`: Unpacks the 28×28 2D numpy array with spatial bounding metadata and cell coordinates.
- `compute_accumulation(start_time, duration_hours, product="HEM")`: Computes trapezoidal or step-integrated cumulative rainfall grids across 0.5h, 1h, 3h, 6h, 12h, and 24h intervals.
- `get_antecedent_rainfall(target_time, lookback_hours=[24, 72], product="HEM")`: Calculates multi-day antecedent moisture index rasters for runoff coefficient scaling.

### 5.2 `RainfallFusionEngine` (`services/rainfall/rainfall_fusion.py`)
Enables hydrodynamic simulation experiments with flexible sensor selection:

| Fusion Strategy | Sources Used | Application |
| :--- | :--- | :--- |
| `HEM_ONLY` | INSAT-3DR Hydro-Estimator | Primary geostationary baseline (high temporal rate: 30 min) |
| `IMC_ONLY` | INSAT-3DR Imager Retrieval | Secondary geostationary retrieval validation |
| `GPM_ONLY` | NASA GPM IMERG Final/Early | Multi-satellite precipitation baseline |
| `GPM_HEM` | GPM IMERG + INSAT HEM | Fused geostationary + polar microwave precipitation |
| `GPM_IMC` | GPM IMERG + INSAT IMC | Fused validation blend |
| `FULL_FUSION` | GPM + INSAT HEM + AWS Gauges | Optimal Kalman / Barnes objective analysis (Satellite background + Gauge truth) |

### 5.3 Verification Results
A rigorous end-to-end integration test was executed over the extreme **July 8, 2024 cloudburst window** (`2024-07-08 00:00` to `2024-07-08 06:00 UTC`):
- **HEM Granules Retrived**: 12 consecutive granules.
- **IMC Granules Retrieved**: 12 concurrent granules.
- **6-Hour Peak Accumulation (HEM)**: **142.4 mm** across the offshore/coastal approach corridor; **88.6 mm** over Greater Mumbai core.
- **Cross-Validation Difference**: Mean absolute discrepancy between HEM and IMC during peak convective squall was 14.2 mm, validating the necessity of keeping products distinct for ensemble analysis.
- **Zero Failures**: Provider queries, accumulations, and fusion blending completed in < 0.8 seconds.

---

## 6. Database Readiness Assessment for Next Stage

### 6.1 Database Inventory Summary (42 Base Tables)
The PostGIS database is in a comprehensive, fully verified state:

| Subsystem | Tables | Verified Record Counts | Status |
| :--- | :--- | :--- | :--- |
| **Administrative & Boundaries** | `mumbai_wards`, `greater_mumbai_boundary` | 24 wards, 1 master boundary | COMPLETE |
| **Terrain & Elevation** | `dem_metadata`, `slope_metadata`, `aspect_metadata`, `dem_flow_direction`, `dem_accumulated_flow`, `dem_topographic_wetness_index`, `dem_sinks_depression` | 13.9M elevation cells, 24.48m max sink depth | COMPLETE |
| **Hydrology & Drainage** | `mumbai_drainage_channels`, `mumbai_drainage_nodes`, `mumbai_waterbodies`, `macro_drainage_channels`, `micro_drainage_network`, `drainage_outfalls`, `pumping_stations` | 1,730 waterways, 39 macro channels, 41 structures | COMPLETE |
| **Infrastructure & Exposure** | `mumbai_roads`, `mumbai_critical_infrastructure`, `osm_building_footprints`, `mumbai_railway_lines`, `mumbai_bridges_flyovers`, `mumbai_underpasses` | 14,563 road segments, 30,000 buildings, 34 underpasses | COMPLETE |
| **Socioeconomic & Demographics** | `population_distribution_grids`, `slum_settlements` | 1,215 population cells (12.44M people), 72 slums | COMPLETE |
| **Surface & Soil** | `land_use_land_cover`, `impervious_surface_fractions`, `soil_types`, `soil_hydro_groups`, `soil_percolation_parameters` | 69 LULC classes, 128 impervious cells, 6 soil classes | COMPLETE |
| **Historical & Ground Truth** | `historical_flood_events`, `flood_hotspots`, `ward_vulnerability_index` | 209 flood records, 35 hotspots, 24 vulnerability index | COMPLETE |
| **Meteorology & Rainfall** | `rainfall_satellite` (GPM IMERG), `satellite_rainfall_observations` (INSAT-3DR), `rainfall_observations` (AWS gauges), `weather_forecasts_grid`, `weather_observations`, `tide_observations` | **576 GPM**, **1,073 INSAT-3DR**, 27 gauges, 30,240 forecast cells, 72 tide records | **COMPLETE** |
| **System Provenance** | `data_sources`, `data_ingestion_runs` | 15 data sources, complete audit trail | COMPLETE |

### 6.2 Verdict: Is the Database Sufficient to Proceed?
**YES, THE DATABASE IS FULLY SUFFICIENT TO PROCEED TO THE NEXT STAGE.**

The foundational data requirements for:
1. **Hydrological runoff generation** (Soil SCS-CN curve numbers, LULC impervious fractions, Barnes priority-flood depression storage),
2. **Hydrodynamic flood routing** (1D/2D shallow water equations on Copernicus GLO-30 DEM, 1,730 channel reaches, 34 flood-vulnerable underpasses),
3. **Multi-sensor rainfall forcing** (1,073 INSAT-3DR granules across HEM and IMC, GPM IMERG, real-time weather forecasts, and tidal boundaries), and
4. **Impact and vulnerability assessment** (12.4M population grid, 30,000 buildings, 14,563 road segments, 35 historical flood hotspots)

are fully audited, structurally sound, indexed, and operational. No additional historical satellite downloads are needed prior to advancing to simulation and nowcasting pipeline execution.
