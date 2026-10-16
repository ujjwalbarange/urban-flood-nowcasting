# Mumbai Urban Flood Platform — Data Gaps & Technical Debt (Phase 1)

**Audit Date:** September 25, 2026  
**Status:** Canonical Gap Analysis  
**Principle:** Transparency over assumptions. Explicitly cataloging what is missing, incomplete, or requires authentication/municipal access.

---

## 1. High-Priority Data Gaps

### Gap 1: High-Density Stormwater Drainage Engineering Data (Invert Levels & Pipe Diameters)
- **Description:** Mumbai has over 2,000 km of underground roadside drains, box culverts, arch drains, and minor nullahs. Currently, the database only possesses **35 trunk nodes** and **8 major open outfall channels** from the macro-level BRIMSTOWAD survey.
- **Missing Attributes:** Piped drain diameters, box culvert widths/heights, invert levels (bed elevation relative to MSL), flow slopes, pipe roughness, and locations of one-way non-return flap gates.
- **Impact on Flood Nowcasting:**
  - *Simulation Engine:* Piped drainage capacity cannot be resolved with 1D Saint-Venant hydraulic routing. The simulation must use a simplified infiltration/drainage loss rate (e.g., standard 25 mm/h or 50 mm/h drainage deduction) rather than true pipe-network pressurization and manhole surcharge.
  - *Decision Support:* Cannot pinpoint exact street-level manhole overflows or pipe blockages.
- **Current Fallback / Proxy:**
  - Macro-drainage loss model: 25 mm/h urban drainage capacity deduction applied across built-up areas.
  - 1,730 open waterways, rivers, streams, and major nullahs mapped from OpenStreetMap act as overland conveyance channels.
- **Authoritative Source:** Municipal Corporation of Greater Mumbai (MCGM) Storm Water Drains (SWD) Department internal GIS portal / as-built AutoCAD records.
- **Access Requirement:** **Proprietary Municipal Access Required**. Not publicly downloadable on open web portals.

---

### Gap 2: Comprehensive Building-Level Footprints & Occupancies
- **Description:** The database currently contains **no `buildings` table**, and the file system only has a sample extract of **20 building polygons** in `data/raw/buildings/buildings.geojson`.
- **Missing Attributes:** Full coverage of Greater Mumbai's ~1.5 million building footprints, ground floor elevations, plinth heights, building use (residential, commercial, industrial, critical), and estimated building occupancy.
- **Impact on Flood Nowcasting:**
  - *Simulation Engine:* Buildings act as flow obstructions (solid obstacles). Without full building footprints, 2D hydrodynamic flow must treat the urban landscape using an increased bulk Manning roughness coefficient ($n = 0.05 - 0.08$) rather than building-porosity modeling.
  - *Impact Assessment:* Cannot report "Building X on Road Y has 40 cm water above plinth level."
- **Current Fallback / Proxy:**
  - Ward-level aggregate exposure assessment based on 2011/projected census totals (12,445,443 persons across 24 wards).
  - 2,002 critical emergency infrastructure points (hospitals, clinics, police, fire, rail) are mapped and spatially joinable.
- **Authoritative Source:**
  - *Open Alternative:* Microsoft Global ML Building Footprints for India (GeoJSON / FlatGeobuf).
  - *Official Alternative:* MCGM Property Tax / Development Plan 2034 GIS Building Layer.
- **Access Requirement:** Open download (Microsoft ML Footprints); Proprietary (MCGM DP 2034).

---

### Gap 3: Real-Time Doppler Weather Radar (DWR) & Dense Automatic Weather Stations (AWS)
- **Description:** Open-Meteo provides 9 surface stations across Mumbai with hourly resolution. However, convective monsoon cloudbursts in Mumbai (such as the 2005 944 mm event or the 2021 Chembur cloudburst) occur at sub-hourly (15-minute) intervals and hyper-local spatial scales (<2 km).
- **Missing Attributes:** S-band / X-band Doppler Weather Radar reflectivity ($Z$), radial velocity, and Quantitative Precipitation Estimation (QPE) grids from IMD Colaba / Veravali radar, plus MCGM's 60-station Disaster Management AWS telemetry.
- **Impact on Flood Nowcasting:**
  - Cannot detect convective cloudburst cells 30–60 minutes before ground impact.
  - Rainfall forcing must rely on numerical weather prediction models (ECMWF IFS / DWD ICON) and hourly surface gauge reports.
- **Current Fallback / Proxy:**
  - Open-Meteo 9-station monitoring network delivering 20 atmospheric variables with +168 hour hourly forecast horizons.
- **Authoritative Source:** India Meteorological Department (IMD) / BMC Disaster Management Cell.
- **Access Requirement:** **Government / Departmental API Authentication Required**.

---

### Gap 4: Automated ISRO MOSDAC Satellite Ingestion Pipeline
- **Description:** User credentials for MOSDAC (`ujjwall.barange@gmail.com`) are present in `.env`, and sample data exists. However, MOSDAC lacks a standardized REST API with permanent API tokens; it uses browser-session cookies or direct FTP/HTTPS downloads.
- **Missing Attributes:** Automated ingestion cron job that logs in, discovers latest INSAT-3DR half-hourly QPE/HEG granules, downloads them, extracts the Mumbai bounding box, and stores the values into PostGIS.
- **Impact on Flood Nowcasting:**
  - Satellite-derived rainfall validation is currently offline/manual rather than automated near-real-time.
- **Current Fallback / Proxy:**
  - Historical IMERG 2005 grid CSV (`imerg_20050726_halfhourly_mumbai_grid.csv`) and Open-Meteo operational telemetry.
- **Authoritative Source:** Space Applications Centre (SAC) / ISRO MOSDAC portal.
- **Access Requirement:** Programmatic session scraper or user-provided manual granule uploads.

---

### Gap 5: Ingestion of NASA GPM IMERG Grid into PostGIS
- **Description:** Environment variables for NASA Earthdata are present in `.env`. A historical half-hourly IMERG grid for 2005-07-26 exists on disk (`data/raw/satellite/imerg_20050726_halfhourly_mumbai_grid.csv`), but the PostGIS table `rainfall_satellite` currently has **0 rows**.
- **Missing Action:** Executing an ingestion job to parse the 576 IMERG records and insert them into `rainfall_satellite`.
- **Impact on Flood Nowcasting:** Low for immediate nowcasting, but needed for satellite vs gauge historical validation.
- **Resolution Plan:** Create and run `data/scripts/ingestion/load_imerg_satellite.py` to populate `rainfall_satellite`.

---

### Gap 6: Re-Derivation of Depression Sinks Raster
- **Description:** As discovered during verification, `data/derived/catchments/depression_sinks_m.npy` contains an array of flat zeros due to a fill-depth residual computation issue in `derive_terrain.py`.
- **Missing Calculation:** True depression storage depth ($Z_{\text{filled}} - Z_{\text{raw}}$) where pluvial water naturally ponds before overflowing.
- **Impact on Flood Nowcasting:**
  - Low-lying depressions (e.g., Hindmata, Milan Subway, Kurla-Kamani) will not have pre-computed static ponding capacities.
- **Resolution Plan:** Update `data/scripts/transformation/derive_terrain.py` with an iterative Wang-Liu or Priority-Flood sink-filling algorithm and regenerate the sink depth raster.

---

### Gap 7: High-Resolution Spatial Population Grids
- **Description:** Population is currently represented at the **ward level** (24 polygons with 2011 census totals and 2024 projections).
- **Missing Attributes:** 100m grid cell population distribution, differentiating high-density informal slum settlements (e.g., Dharavi, Shivaji Nagar) from commercial business districts (BKC, Nariman Point).
- **Impact on Flood Nowcasting:**
  - Exposure assessment cannot distinguish between flooding in a low-density open rail yard versus an adjacent high-density informal settlement.
- **Current Fallback / Proxy:** Uniform ward population density ($D = \text{Population} / \text{Area}$).
- **Authoritative Source:** WorldPop India 100m Population Raster (Open Access, CC-BY 4.0).
- **Access Requirement:** Public download.

---

## 2. Summary Matrix of Data Gaps & Resolution Status

| Gap ID | Dataset Name | Priority Rank | Status | Primary Impact | Fallback Mechanism | Resolution Path |
|---|---|---|---|---|---|---|
| **GAP-01** | Street-level Drainage Inverts & Pipe Sizes | **P0** (Essential) | **OPEN** (Proprietary) | Hydraulic pipe surcharge unmodeled | Infiltration deduction + 1,730 surface channels + 39 macro channels | Request BMC SWD GIS CAD layers from authorities |
| **GAP-02** | IMD Doppler Weather Radar (DWR) | **P0** (Essential) | **OPEN** (Government) | Cloudburst nowcasting limited to gauges | 9-station Open-Meteo telemetry + IMERG half-hourly grid | Request IMD DWR access / API key from authorities |
| **GAP-03** | MCGM 60-AWS Rain Gauge Telemetry | **P1** (High Value) | **OPEN** (Departmental) | Ward-level rain resolution limited to 9 stations | 9-station Open-Meteo surface observations | Request BMC Disaster Management live AWS stream |
| **GAP-04** | River & Nullah Real-Time Stage Sensors | **P1** (High Value) | **OPEN** (Hardware Sensor) | Dynamic backwater flood feedback unmeasured | Apollo Bunder tidal series + hydrodynamic routing | Deploy ultrasonic stage sensors along Mithi / nullahs |
| **GAP-05** | High-Resolution LiDAR DTM (1m–5m) | **P2** (Valuable) | **OPEN** (Publicly Unavail)| Micro-topography (curbs, road crowns) unmodeled | Copernicus GLO-30 DSM + Priority-Flood depression sinks | Acquire MMRDA / Survey of India urban LiDAR survey |
| **GAP-06** | Building Plinth & Structural Heights | **P2** (Valuable) | **OPEN** (Zero Fabrication) | Inundation above plinth uncalculated | Point-in-polygon building footprint intersection | BMC Property Tax / DP 2034 GIS building attributes |
| **GAP-07** | MOSDAC INSAT-3DR Satellite Rainfall | **RESOLVED** | **CLOSED** (Verified) | High-frequency satellite rain previously missing | Ingested **1,073 INSAT-3DR granules** (644 HEM, 429 IMC) into `satellite_rainfall_observations` | ISRO MOSDAC INSAT-3DR 2024–2025 Event Packages |
| **GAP-08** | Full Building Footprints | **RESOLVED** | **CLOSED** (Verified) | Building obstruction & exposure unmodeled | Ingested **30,000 Microsoft Global ML Footprints** into `buildings` | Microsoft Global ML Footprints (2026-02-03) |
| **GAP-09** | Gridded Population (100m) | **RESOLVED** | **CLOSED** (Verified) | Slum vs commercial density undifferentiated | Ingested **1,242 WorldPop grid cells** into `population_grids` | WorldPop 2020 Constrained (5.93M residents) |
| **GAP-10** | `rainfall_satellite` PostGIS Table | **RESOLVED** | **CLOSED** (Verified) | IMERG data was uningested on disk | Ingested **576 NASA GPM IMERG records** into `rainfall_satellite` | NASA Earthdata GES DISC Deluge Grid |
| **GAP-11** | Depression Sinks Raster | **RESOLVED** | **CLOSED** (Verified) | Sinks array was flat zeros | Re-derived via **Barnes Priority-Flood** (max sink depth 24.48m) | `derive_terrain.py` Priority-Flood execution |
| **GAP-12** | Land Use / Land Cover & Impervious Grid| **RESOLVED** | **CLOSED** (Verified) | Runoff coefficients unmodeled | Ingested **69 LULC polygons** and **128 impervious grid cells** | Spark Spatial Data Package (ESA WorldCover) |
| **GAP-13** | Municipal Flood Hotspots & Depressions | **RESOLVED** | **CLOSED** (Verified) | Hotspots limited to 10 rows | Upgraded to **35 official hotspots** and **15 low-lying basins** | Spark Spatial Data Package (MCGM Action Plan) |

---
*Document certified as ground truth gap analysis for MUFNS Phase 1 + Phase 2 Spark Spatial & MOSDAC Integration.*


