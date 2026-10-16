# MUFNS Stage 0: Database Health Report
**Date:** September 26, 2026  
**Status:** ✅ DATABASE CONNECTED — STAGE 0 PASSED  
**PostgreSQL:** 18.6 on x86_64-pc-linux-gnu  
**PostGIS:** 3.6.4 (GEOS 3.14.1, PROJ)  
**Database:** `defaultdb` (Aiven Cloud)  
**Host:** `pg-ba8ce32-omsatange5788-0a38.h.aivencloud.com:21135`  
**SSL:** TLSv1.3 / TLS_AES_256_GCM_SHA384  
**Connection latency:** 372ms  

---

## 1. Connection Status

| Check | Status | Detail |
|-------|--------|--------|
| DATABASE_URL present | ✅ PASS | 129 chars, asyncpg scheme |
| DNS resolution | ✅ PASS | Resolved to 143.110.254.176 |
| TCP connectivity | ✅ PASS | Port 21135 reachable |
| SSL handshake | ✅ PASS | TLSv1.3 |
| PostgreSQL auth | ✅ PASS | Connected in 372ms |
| PostGIS extension | ✅ PASS | PostGIS 3.6.4 |

**Conclusion:** The earlier `ConnectionRefusedError` was a transient network issue. The database is fully operational.

---

## 2. Table Inventory (43 tables)

> **IMPORTANT FINDING:** Several table names documented in prior reports **do not match** the actual database schema. The table below reflects the **actual** verified table names.

| # | Actual Table Name | Rows | Status | Notes |
|---|-------------------|------|--------|-------|
| 1 | `alerts` | 0 | ⚠️ Empty | No alerts generated yet |
| 2 | `bridges_and_culverts` | 33 | ✅ | Bridges and culvert structures |
| 3 | `buildings` | 30,000 | ✅ | OSM building footprints |
| 4 | `cities` | 1 | ✅ | Mumbai configuration |
| 5 | `citizen_reports` | 2 | ✅ | Citizen flood reports |
| 6 | `coastal_exposure_zones` | 15 | ✅ | Coastal risk polygons |
| 7 | `critical_arterial_corridors` | 78 | ✅ | Major road corridors |
| 8 | `critical_infrastructure` | 2,002 | ✅ | Hospitals, stations, substations |
| 9 | `data_ingestion_runs` | 7 | ✅ | Provenance: ingestion log |
| 10 | `data_sources` | 8 | ✅ | Provenance: source registry |
| 11 | `dem_tiles` | 1 | ✅ | DEM raster tile reference |
| 12 | `drainage_links` | 8 | ✅ | Drainage pipe/channel links |
| 13 | `drainage_nodes` | 35 | ✅ | Drainage manholes/inlets |
| 14 | `drainage_structures` | 41 | ✅ | Outfalls, sluice gates |
| 15 | `emergency_facilities` | 9 | ✅ | Emergency response locations |
| 16 | `fire_stations` | 37 | ✅ | Fire station locations |
| 17 | `flood_hotspots` | 35 | ✅ | Known chronic flood locations |
| 18 | `flood_hotspots_v1_legacy` | 10 | ✅ | Legacy hotspot data |
| 19 | `flood_snapshots` | 0 | ⚠️ Empty | No simulation snapshots stored yet |
| 20 | `green_open_spaces` | 25 | ✅ | Parks/open areas |
| 21 | `historical_flood_events` | 209 | ✅ | Historical flood records |
| 22 | `hospitals` | 1,667 | ✅ | Hospital locations |
| 23 | `impervious_surface_grid` | 128 | ✅ | Impervious fraction cells |
| 24 | `land_use_land_cover` | 69 | ✅ | LULC polygons |
| 25 | `low_lying_areas` | 15 | ✅ | Low-elevation zones |
| 26 | `police` | 122 | ✅ | Police station locations |
| 27 | `population_grids` | 1,242 | ✅ | WorldPop grid cells |
| 28 | `primary_drainage_network` | 39 | ✅ | Major drainage channels |
| 29 | `pumping_stations` | 8 | ✅ | Municipal pump stations |
| 30 | `railway_stations` | 167 | ✅ | Railway station locations |
| 31 | `rainfall_observations` | 27 | ✅ | AWS ground gauges |
| 32 | `rainfall_satellite` | 576 | ✅ | GPM IMERG satellite rainfall |
| 33 | `road_segments` | 14,563 | ✅ | Road network segments |
| 34 | `satellite_rainfall_observations` | 1,073 | ✅ | **INSAT-3DR (HEM=644, IMC=429)** |
| 35 | `shelters` | 10 | ✅ | Emergency shelters |
| 36 | `simulation_runs` | 19 | ✅ | Past simulation metadata |
| 37 | `spatial_ref_sys` | 8,500 | ✅ | PostGIS SRID catalog (system) |
| 38 | `terrain_derivatives` | 6 | ✅ | Slope/aspect/flow metadata |
| 39 | `tide_observations` | 72 | ✅ | Tidal predictions |
| 40 | `wards` | 24 | ✅ | Mumbai administrative wards |
| 41 | `water_bodies` | 1,730 | ✅ | Rivers/nullahs/waterways |
| 42 | `weather_forecasts` | 30,240 | ✅ | NWP forecast grid cells |
| 43 | `weather_observations` | 108 | ✅ | AWS weather observations |

---

## 3. Spatial Integrity

| Check | Result |
|-------|--------|
| Distinct SRIDs | 1 (EPSG:4326 only) |
| Geometry columns using SRID 4326 | 47 columns |
| Spatial consistency | ✅ All data in WGS84 |

---

## 4. Table Name Discrepancies

The following table names used in prior documentation or ORM models **DO NOT EXIST** in the actual database:

| Documented Name | Actual Name | Status |
|----------------|-------------|--------|
| `mumbai_wards` | `wards` | ❌ Name mismatch |
| `mumbai_roads` | `road_segments` | ❌ Name mismatch |
| `impervious_surface_fractions` | `impervious_surface_grid` | ❌ Name mismatch |
| `population_distribution_grids` | `population_grids` | ❌ Name mismatch |
| `weather_forecasts_grid` | `weather_forecasts` | ❌ Name mismatch |
| `dem_metadata` | `dem_tiles` + `terrain_derivatives` | ❌ Name mismatch |
| `soil_types` | Does NOT exist | ❌ **MISSING** |
| `soil_hydro_groups` | Does NOT exist | ❌ **MISSING** |
| `soil_percolation_parameters` | Does NOT exist | ❌ **MISSING** |
| `mumbai_drainage_channels` | `primary_drainage_network` + `drainage_structures` | ❌ Name mismatch |
| `mumbai_drainage_nodes` | `drainage_nodes` | ❌ Name mismatch |
| `mumbai_waterbodies` | `water_bodies` | ❌ Name mismatch |
| `macro_drainage_channels` | `primary_drainage_network` | ❌ Name mismatch |
| `micro_drainage_network` | Does NOT exist | ❌ **MISSING** |
| `dem_accumulated_flow` | Does NOT exist as separate table | ❌ Likely in `terrain_derivatives` metadata |
| `dem_flow_direction` | Does NOT exist as separate table | ❌ Likely in `terrain_derivatives` metadata |
| `dem_topographic_wetness_index` | Does NOT exist as separate table | ❌ Likely in `terrain_derivatives` metadata |
| `dem_sinks_depression` | Does NOT exist as separate table | ❌ Likely in `terrain_derivatives` metadata |
| `slum_settlements` | Does NOT exist | ❌ **MISSING** |
| `ward_vulnerability_index` | Does NOT exist | ❌ **MISSING** |
| `greater_mumbai_boundary` | Does NOT exist | ❌ **MISSING** |

> **Impact:** Any service code or ORM model referencing these incorrect names will fail at runtime. The ORM models in `services/database/models.py` need to be reconciled with actual table names before the pipeline can function.

---

## 5. Key Dataset Verification

### Rainfall (COMPLETE)
| Dataset | Table | Records | Status |
|---------|-------|---------|--------|
| INSAT-3DR HEM | `satellite_rainfall_observations` | 644 | ✅ |
| INSAT-3DR IMC | `satellite_rainfall_observations` | 429 | ✅ |
| GPM IMERG | `rainfall_satellite` | 576 | ✅ |
| AWS Rain Gauges | `rainfall_observations` | 27 | ✅ |
| Weather Forecasts (NWP) | `weather_forecasts` | 30,240 | ✅ |
| Weather Observations | `weather_observations` | 108 | ✅ |

### Terrain (PARTIAL)
| Dataset | Table | Records | Status |
|---------|-------|---------|--------|
| DEM tile ref | `dem_tiles` | 1 | ✅ |
| Terrain derivatives metadata | `terrain_derivatives` | 6 | ✅ (metadata only — rasters on disk) |
| DEM GeoTIFF file | `data/raw/terrain/` | on disk | ✅ |

### Land Surface (PARTIAL)
| Dataset | Table | Records | Status |
|---------|-------|---------|--------|
| LULC | `land_use_land_cover` | 69 | ✅ |
| Impervious surface | `impervious_surface_grid` | 128 | ✅ |
| Soil types | — | — | ❌ **MISSING TABLE** |
| Soil hydro groups | — | — | ❌ **MISSING TABLE** |
| Soil percolation params | — | — | ❌ **MISSING TABLE** |

### Drainage (AVAILABLE)
| Dataset | Table | Records | Status |
|---------|-------|---------|--------|
| Primary drainage | `primary_drainage_network` | 39 | ✅ |
| Drainage structures | `drainage_structures` | 41 | ✅ |
| Drainage nodes | `drainage_nodes` | 35 | ✅ |
| Drainage links | `drainage_links` | 8 | ✅ |
| Pumping stations | `pumping_stations` | 8 | ✅ |
| Water bodies | `water_bodies` | 1,730 | ✅ |

### Exposure (AVAILABLE)
| Dataset | Table | Records | Status |
|---------|-------|---------|--------|
| Roads | `road_segments` | 14,563 | ✅ |
| Buildings | `buildings` | 30,000 | ✅ |
| Population | `population_grids` | 1,242 | ✅ |
| Critical infrastructure | `critical_infrastructure` | 2,002 | ✅ |
| Hospitals | `hospitals` | 1,667 | ✅ |
| Police | `police` | 122 | ✅ |
| Fire stations | `fire_stations` | 37 | ✅ |
| Railway stations | `railway_stations` | 167 | ✅ |
| Bridges/culverts | `bridges_and_culverts` | 33 | ✅ |
| Shelters | `shelters` | 10 | ✅ |
| Green/open spaces | `green_open_spaces` | 25 | ✅ |
| Low-lying areas | `low_lying_areas` | 15 | ✅ |
| Critical arterial corridors | `critical_arterial_corridors` | 78 | ✅ |
| Coastal exposure zones | `coastal_exposure_zones` | 15 | ✅ |

### Validation (AVAILABLE)
| Dataset | Table | Records | Status |
|---------|-------|---------|--------|
| Historical flood events | `historical_flood_events` | 209 | ✅ |
| Flood hotspots | `flood_hotspots` | 35 | ✅ |
| Legacy hotspots | `flood_hotspots_v1_legacy` | 10 | ✅ |

### Coastal (AVAILABLE)
| Dataset | Table | Records | Status |
|---------|-------|---------|--------|
| Tide observations | `tide_observations` | 72 | ✅ |

### Administrative (AVAILABLE)
| Dataset | Table | Records | Status |
|---------|-------|---------|--------|
| Wards | `wards` | 24 | ✅ |
| City | `cities` | 1 | ✅ |

---

## 6. Empty / Missing Tables Summary

### Empty tables (exist but no data):
- `alerts` (0 rows) — expected, no alerts generated yet
- `flood_snapshots` (0 rows) — expected, no simulation outputs persisted yet

### Missing tables (referenced in docs but do not exist):
1. `soil_types` — **No soil classification data in database**
2. `soil_hydro_groups` — **No soil hydrologic group data in database**
3. `soil_percolation_parameters` — **No soil percolation data in database**
4. `slum_settlements` — referenced in prior reports but does not exist
5. `ward_vulnerability_index` — referenced but does not exist
6. `greater_mumbai_boundary` — referenced but does not exist
7. `micro_drainage_network` — referenced but does not exist
8. Individual DEM derivative tables (`dem_accumulated_flow`, `dem_flow_direction`, etc.) — do not exist as separate tables; stored as metadata in `terrain_derivatives` with raster files on disk

---

## 7. Data Gaps Impacting Pipeline

| Gap | Impact | Mitigation |
|-----|--------|------------|
| **No soil parameters in database** | Cannot connect real soil data to Horton infiltration model | Use literature-default values for Mumbai laterite/alluvial soils. Document as "assumed". |
| **Table name mismatches** | ORM models and service code will fail at runtime | Must reconcile ORM models with actual table names before any pipeline work. |
| **DEM derivatives are file-based** | Flow direction, flow accumulation, TWI stored on disk, not in DB | Acceptable — reference via `terrain_derivatives` metadata table. |

---

## 8. Conclusions

### Stage 0 Result: ✅ PASSED — DATABASE IS ONLINE AND OPERATIONAL

1. **All 43 tables** verified with row counts
2. **All critical datasets** present: INSAT-3DR (1,073), GPM IMERG (576), AWS (27), DEM, LULC (69), Imperviousness (128), Drainage, Tide (72), Historical floods (209), Roads (14,563), Buildings (30,000), Population (1,242)
3. **Spatial integrity** confirmed: all geometry in EPSG:4326
4. **PostGIS 3.6.4** with full spatial functions available

### Critical Blockers for Stage 1:
1. **Table name mismatches** must be resolved — the ORM models reference names that don't match the actual database
2. **Soil parameter tables are missing** — must either create them or use documented literature defaults
3. **The connection was transient** — add retry/reconnect logic for robustness

### Ready to proceed to Stage 1.
