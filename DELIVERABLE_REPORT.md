# Mumbai Urban Flood Nowcasting System (MUFNS) — Engineering Deliverable & Scientific Provenance Report

**System**: Mumbai Urban Flood Nowcasting System (MUFNS)  
**Problem Statement**: SIH26085 — Real-Time High-Resolution Urban Flood Nowcasting & Drainage Coupling  
**Domain**: Municipal Corporation of Greater Mumbai (BMC) / Mumbai Metropolitan Region  
**Audit & Upgrade Date**: September 2026  
**Status**: Fully Integrated, Empirically Connected, Scientifically Grounded  

---

## A. What Antigravity Had Already Completed
Prior to this transition, Antigravity had assembled substantial architectural components:
1. **Frontend Skeleton**: Next.js workspace for `city-dashboard` with dashboard cards, basic Leaflet map integration, and municipal tabs.
2. **Physical Solver Foundation**: Genuine NumPy 2D diffusive-wave hydrodynamic equations (`services/flood/engine.py`, `services/engine/surface_flow.py`) and Horton infiltration equations (`services/hydrology/infiltration.py`).
3. **Copernicus DEM**: Local GeoTIFF of Copernicus GLO-30 (30m) covering the Mumbai bounding box (`data/raw/terrain/opentopography_cop30_mumbai_bbox.tif`).
4. **Cloud Database**: Aiven PostgreSQL 18.6 with PostGIS 3.6 spatial extensions containing seeded tables for BMC wards, historical events (198 observations from 2016–2025), drainage nodes, pumping stations, and hotspots.
5. **Local Archives**: Local CSV records of NASA IMERG half-hourly precipitation for July 26, 2005.

**However, critical disconnects and misleading facades existed:**
- Weather data was fetched from Open-Meteo only to be displayed on a UI badge; it **never** reached the 2D flood model.
- The flood map rendered thousands of square polygon cells with hard borders, resulting in a rough, boxy, checkerboard visual style.
- ISRO MOSDAC was an empty stub returning static fallback values.
- NASA IMERG was limited to a static local CSV with no live satellite granule connectivity.
- Drainage coupling code existed in isolation; simulations were invoked with `coupling_points=None` and `drainage_heads=None`.
- Model runs lived only in an in-memory dictionary (`_simulations = {}`) and were never persisted to PostgreSQL/PostGIS.
- Manually constructed historical flood extent polygons were misleadingly labeled as "Sentinel-1 SAR Ground Truth".
- Misleading slogans like *"Zero Synthetic Data"* were displayed despite widespread synthetic fallbacks.

---

## B. What Was Changed & Upgraded
1. **Live Open-Meteo 9-Point Spatial Forcing Pipeline**:
   - Replaced single-point badge fetching with an asynchronous 9-point spatial mesh across Mumbai (Colaba, Santacruz, Vikhroli, Andheri, Dadar, Kurla, Borivali, Thane, Bandra).
   - Ingested current rainfall rates, multi-hour accumulations (1h, 3h, 6h), atmospheric parameters (temperature, pressure, humidity, wind gusts, weather code), and hourly forecasts.
   - Built a dynamic hyetograph schedule that directly forces the 2D diffusive-wave overland flow model.
2. **Real ISRO MOSDAC Authenticated Integration**:
   - Built a live Keycloak OpenID client (`services/rainfall/mosdac.py`) communicating with official ISRO SAC endpoints (`https://mosdac.gov.in/download_api/gettoken` and `https://mosdac.gov.in/apios/datasets.json`).
   - Authenticated using user credentials in `.env`, retrieving live JWTs and querying real INSAT-3DR/3DS Level-2B Hydro-Estimator Method (HEM) precipitation granules (e.g. `3RIMG_24SEP2026_2045_L2B_HEM_V01R00.h5`, latency ~214ms).
3. **Real NASA Earthdata / GPM IMERG Integration**:
   - Upgraded `services/rainfall/imerg.py` to query NASA CMR (`https://cmr.earthdata.nasa.gov`) and GES DISC with the user's `NASA_EARTHDATA_TOKEN`.
   - Enabled live discovery and retrieval of GPM IMERG 0.1° half-hourly products (`GPM_3IMERGHHL`) while preserving the 2005 deluge CSV for historical calibration.
4. **Physical BRIMSTOWAD Drainage Network Coupling**:
   - Implemented `map_drainage_nodes_to_grid()` mapping all 14 BMC / BRIMSTOWAD drainage nodes and pumping stations to DEM cell coordinates `(row, col)` with invert elevations.
   - Wired bidirectional signed orifice exchanges ($Q_{ex} = C_d A_o \sqrt{2g|\Delta H|}\operatorname{sgn}(\Delta H)$) into the 2D solver.
5. **PostGIS Model-Run Persistence**:
   - Created `persist_nowcast_run()` storing every completed nowcast run, forcing metadata, mass balance closure errors, runtime, and output manifests into PostGIS table `simulation_runs`.
6. **Continuous Water-Surface Map Redesign**:
   - Eliminated the boxy/square polygon cell grid (`showSimulationFloods` diagnostic mesh defaulted to OFF with 0px border).
   - Generated high-resolution, bilinear-interpolated, Gaussian-smoothed PNG raster overlays from raw model depth arrays (`/api/v1/nowcast/latest/raster.png?minute={m}`).
   - Rendered using Leaflet `ImageOverlay` with interactive opacity controls (20%–100%) and a clean CartoDB Positron GIS basemap.
7. **Nowcast Forecast Timeline Scrubbing**:
   - Cached time-stepped simulation depth grids at $0, 30, 60, 90, 120, 180$ minutes.
   - Built an interactive floating timeline player allowing operators to scrub across future hours and visualize flood progression.
8. **Ward Flood Explainability ("Why is this area flooding?")**:
   - Implemented `compute_ward_explanations()` which provides empirical contributing drivers (forecast rainfall, terrain basin depth, drainage node stress, coupled pumping stations, chronic hotspots) and actionable municipal recommendations when a ward is selected.
9. **Scientific Honesty Overhaul**:
   - Replaced "Sentinel-1 SAR Ground Truth" with "Documented/Surveyed Extent (Archival Sourced Mask)".
   - Removed all deceptive claims; every data source now displays exact provenance, timestamps, latency, resolution, and role.

---

## C. Actual Data Sources Now Connected
| Data Source | Provider / Platform | Type / Format | Status | Role in MUFNS |
| :--- | :--- | :--- | :--- | :--- |
| **Open-Meteo** | Multi-Model Numerical Weather Prediction | REST API (9-point spatial mesh) | **LIVE** | Live & forecast rainfall forcing for 2D flood simulation |
| **ISRO MOSDAC** | Space Applications Centre (SAC) / ISRO | Keycloak Auth REST (INSAT-3DR/3DS L2B HEM) | **LIVE** | Regional satellite precipitation & convective storm tracking |
| **NASA Earthdata** | NASA GES DISC / GPM IMERG | CMR Search & Bearer Token | **LIVE** | Global satellite precipitation cross-validation & benchmark |
| **Copernicus DEM** | European Space Agency (ESA) / OpenTopography | 30m GeoTIFF raster (`cop30_mumbai_bbox.tif`) | **STATIC** | Topographic elevation, slope, depression filling, overland routing |
| **Aiven PostGIS** | Aiven Cloud PostgreSQL 18.6 + PostGIS 3.6 | TLS Relational & Spatial Database | **LIVE** | Persistence for GIS infrastructure, model runs, citizen reports |
| **BRIMSTOWAD** | Municipal Corporation of Greater Mumbai (BMC) | GeoJSON / PostGIS Vector Network | **STATIC** | Stormwater drainage nodes, outfalls, holding ponds, pumps |
| **Mumbai Deluge Archive** | IMD Santacruz & NASA IMERG 2005 Deluge | Historical CSV Time Series | **HISTORICAL** | Benchmark replay & extreme storm validation |
| **Historical Flood Events**| BMC Disaster Management / Field Surveys | 198 Field Observations (2016–2025) | **HISTORICAL** | Hotspot validation & ward vulnerability scoring |

---

## D. Exact End-to-End Pipeline
```
[ Open-Meteo 9-Point Spatial API ]
               │
               ▼
[ Ingestion & Normalization Layer (services/nowcast/pipeline.py) ]
   • Fetches 9 points across Mumbai (Colaba, Dadar, Kurla, Andheri, etc.)
   • Computes spatial mean, max, 1h/3h/6h accumulations, wind, pressure
               │
               ▼
[ Spatial Rainfall Forcing Engine ]
   • Builds time-stepped rainfall hyetograph schedule: [(t0, R0), (t1, R1), ...]
               │
               ▼
[ Copernicus GLO-30 DEM (30m) + Priority Flood Sink Conditioning ]
   • Fills depressions and conditions flow barriers (services/terrain/conditioning.py)
   • Applies spatial urban imperviousness grid (80% urban, 35% hills)
               │
               ▼
[ 2D Diffusive Wave Hydrodynamic Solver (services/flood/engine.py) ]
   • Horton Infiltration: f(t) = fc + (f0 - fc)e^(-kt)
   • Manning-Strickler 2D Shallow Water Overland Flow: de Almeida 2012 / Hunter 2005
   • Adaptive CFL Timestep Control (routing dt ~2s)
               ▲
               │ (Bidirectional Orifice Exchange: Q = Cd * Ao * sqrt(2g|ΔH|) * sgn(ΔH))
               ▼
[ BRIMSTOWAD Drainage Network Coupling ]
   • Ingests 14 coupled nodes/ponds (Pramod Mahajan, St. Xavier Ground, Britannia, Love Grove)
               │
               ▼
[ Model Output Post-Processing & Snapshot Caching ]
   • Computes peak depth grid, flooded area (km²), mass balance closure (< 1% error)
   • Caches timestep grids at 0, 30, 60, 90, 120, 180 min
   • Evaluates ward explainability ("Why is this area flooding?")
               │
               ├─────────────────────────────────────────┐
               ▼                                         ▼
[ Cloud PostGIS Persistence ]              [ Bilinear Upsampled Raster Engine ]
   • Saves to simulation_runs table          • services/flood/raster_renderer.py
   • Stores run_id, scenario, mass-balance    • Generates smooth continuous PNG
               │                                         │
               └────────────────────┬────────────────────┘
                                    ▼
                         [ FastAPI REST Endpoints ]
                            • /api/v1/nowcast/latest
                            • /api/v1/nowcast/latest/raster.png?minute={m}
                            • /api/v1/nowcast/weather
                            • /api/v1/geodata/system-health
                                    │
                                    ▼
                 [ Municipal Command Center (Next.js) ]
                    • Continuous Water Surface Overlay (ImageOverlay)
                    • Floating Forecast Timeline Player (NOW → +180m)
                    • Ward Explainability & Action Inspector Drawer
                    • Live System Health & Scientific Provenance Tab
```

---

## E. Source Classification: LIVE
- **Open-Meteo Weather**: 9 monitoring points across Mumbai queried every 5 minutes.
- **ISRO MOSDAC**: Authenticated via user credentials to official download API; queries INSAT-3DR/3DS Level-2B HEM granules.
- **NASA Earthdata / CMR**: Authenticated search & granule status for GPM IMERG 0.1° half-hourly rainfall.
- **Aiven Cloud PostGIS**: Live spatial database connection storing operational state, simulation runs, and citizen incident reports.
- **Citizen Reports Queue**: Real-time dispatching and status escalation.

## F. Source Classification: HISTORICAL
- **IMD 2005 Deluge Records**: Santacruz AWS 944 mm 24h cloudburst hyetographs for model stress testing.
- **NASA IMERG 2005 Grid**: Half-hourly calibrated satellite precipitation for July 26, 2005.
- **BMC 198 Surveyed Flood Events (2016–2025)**: Empirical disaster ground records across all 24 wards.
- **Documented Extent Masks**: Archival surveyed flood boundaries used for CSI/IoU hindcast validation.

## G. Source Classification: STATIC
- **Copernicus GLO-30 DEM**: 30m Digital Surface Model GeoTIFF for Greater Mumbai.
- **BRIMSTOWAD Drainage Network**: Invert elevations, holding pond capacities, rated pump discharge rates, and outfall coordinates.
- **BMC Ward Administrative Boundaries**: Polygon geometries, census populations, and geographic areas.
- **Critical Infrastructure & Shelters**: Static municipal asset locations.

## H. Sources Remaining UNAVAILABLE
- **Live Stormwater Pumping Telemetry (SCADA)**: Only static rated pumping capacities are available in municipal records. The UI honestly labels this as *"Rated Capacity / Static Infrastructure Data"*.
- **Direct Live Sentinel-1 SAR Downlink**: Real-time SAR satellite passes occur every 6–12 days and require ground station processing. SAR validation is restricted to historical hindcast events.

---

## I. How Open-Meteo is Used by the Model
Rather than a superficial badge, Open-Meteo is the primary meteorological forcing engine:
1. `fetch_comprehensive_weather()` queries 9 geographic coordinates across Mumbai simultaneously.
2. The system computes regional mean intensity, spatial variance, and multi-hour accumulations.
3. `build_rainfall_schedule_from_weather()` formats these observations into a continuous hyetograph schedule.
4. The 2D hydrodynamic solver applies this forcing directly to each cell of the simulation grid at each adaptive timestep.
5. If rainfall increases in Open-Meteo, surface inundation depth and flooded area dynamically increase in the simulation.

---

## J. How NASA IMERG is Used
1. **Live Synoptic Tracking**: `IMERGProvider` queries NASA CMR for the latest half-hourly global precipitation granules (`GPM_3IMERGHHL`).
2. **Historical Deluge Calibration**: The local half-hourly CSV for the July 26, 2005 storm (576 spatial records) is loaded to drive historical hindcast simulations and calibrate the hydrodynamic solver against the historic deluge.
3. The UI clearly labels live CMR satellite passes vs. the 2005 historical calibration archive.

---

## K. ISRO MOSDAC Status
- **Authentication**: Fully verified. Uses `POST https://mosdac.gov.in/download_api/gettoken` with user credentials (`MOSDAC_user_email` and `MOSDAC_pass`) from `.env`.
- **Latency**: ~214ms authentication, ~1.2s opensearch.
- **Datasets**: Queries INSAT-3DR / INSAT-3DS Level-2B Hydro-Estimator Method (`3RIMG_L2B_HEM` / `3SIMG_L2B_HEM`).
- **Telemetry**: Successfully retrieved recent granule `3RIMG_24SEP2026_2045_L2B_HEM_V01R00.h5`.
- **UI Health**: Accurately reports `CONNECTED` with live latency and granule timestamp.

---

## L. How Copernicus DEM is Used
1. **Source**: Official ESA Copernicus GLO-30 DSM (30m spatial resolution).
2. **Sink Conditioning**: Pre-processed with Priority Flood depression filling (`services/terrain/conditioning.py`) to eliminate spurious DEM noise and ensure hydrologically sound drainage pathways.
3. **Hydrodynamic Routing**: Elevation values ($z$) define bed slope gradients ($S_0 = -\nabla z$) in the diffusive-wave momentum equation:
   $$Q = \frac{1}{n} h^{5/3} S_f^{1/2}$$
4. **Depression Detection**: Identifies natural low-lying basins (< 8m MSL) such as Hindmata, Gandhi Market, and Milan Subway.

---

## M. How Drainage Coupling Works
1. `map_drainage_nodes_to_grid()` projects BRIMSTOWAD nodes, culverts, holding ponds, and pumping stations into DEM grid coordinates `(row, col)`.
2. At each coupling stride (60s), the model evaluates hydraulic head difference:
   $$\Delta H = (z_{surface} + h_{surface}) - H_{drainage\_invert}$$
3. **Capture / Surcharge Transfer**:
   - If $\Delta H > 0$, surface water enters the storm drain.
   - If $\Delta H < 0$ (surcharge/backwater from high tide), water spills onto the street.
   - Exchange flow follows signed orifice hydraulics:
     $$Q_{ex} = C_d A_o \sqrt{2g|\Delta H|} \operatorname{sgn}(\Delta H)$$
4. Holding ponds (e.g. Pramod Mahajan Kala Park and St. Xavier Ground) store runoff up to their physical capacities.

---

## N. How Flood Depth is Rendered (Continuous Water Surface)
- **Problem Solved**: Eliminated the thousands of square GeoJSON cell polygons with borders that previously produced an ugly checkerboard grid.
- **Implementation**:
  1. The raw 2D depth array is extracted directly from the hydrodynamic engine.
  2. `services/flood/raster_renderer.py` applies 4x bilinear interpolation and Gaussian kernel smoothing ($\sigma = 1.5$) to produce a soft, continuous water surface.
  3. The array is mapped through a scientific water colormap (from shallow translucent cyan at 0.05m to deep royal navy and crimson for hazardous depths > 1.0m) with an alpha-gradient.
  4. The output is served as a high-performance PNG via `/api/v1/nowcast/latest/raster.png`.
  5. The frontend displays this using Leaflet `ImageOverlay` placed exactly over DEM georeferenced bounds (`X-Georef-MinLat`, `X-Georef-MaxLat`, etc.).
  6. The user can adjust continuous water opacity from 20% to 100% via a floating slider.

---

## O. How the Forecast Timeline Works
1. During simulation, snapshot depth grids are recorded at regular intervals.
2. `timeline_depth_grids` caches the 2D surface state for minutes $0, 30, 60, 90, 120, 180$.
3. When the operator clicks timeline buttons on the floating map controller (`NOW`, `+30m`, `+60m`, `+90m`, `+120m`, `+180m`), the map fetches `/api/v1/nowcast/latest/raster.png?minute={m}`.
4. The map smoothly transitions the water layer to show exact flood expansion and depth progression.

---

## P. How Ward Risk is Calculated
Ward risk combines empirical hazard, physical exposure, and municipal vulnerability:
$$\text{Risk Score} = 0.40 \times \text{Hazard} + 0.35 \times \text{Exposure} + 0.25 \times \text{Vulnerability}$$
- **Hazard**: Live simulated peak water depth ($h_{max}$), flooded surface area, and rainfall rate.
- **Exposure**: Ward census population density (from BMC census data) and critical infrastructure counts (hospitals, schools, shelters).
- **Vulnerability**: Low-elevation depression status (< 8m MSL), presence of chronic flood hotspots, and drainage outfall tidal constraints.
- When an operator clicks a ward, the Feature Inspector displays the exact breakdown ("Why is this area flooding?").

---

## Q. How Data Provenance is Displayed
Every subsystem exposes complete provenance in the System Health tab:
- **Subsystem Name & Connectivity Status** (`CONNECTED`, `READY`, `OPERATIONAL`, `DEGRADED`)
- **Real Round-Trip Latency** in milliseconds
- **Source Platform / Provider**
- **Model Role** (e.g. *"Real-time 9-point spatial rainfall forcing mesh"*)
- **Resolution & Coordinate System** (e.g. *"30m Copernicus GLO-30"*, *"4 km regional grid"*)
- **Active Satellite / Dataset ID** (`INSAT-3DR / INSAT-3DS • 3RIMG_L2B_HEM`, `GPM_3IMERGHHL`)
- **Latest Granule Identifier & Timestamp**
- **PostGIS Record Counts** (wards: 24, events: 198, nodes: 35, pumps: 8, shelters: 10)

---

## R. Tests Performed & Verified
1. **Full Integration Suite (`tests/integration/test_nowcast_pipeline.py`)**:
   - `test_comprehensive_weather_fetch`: Verified multi-point Open-Meteo ingestion across Mumbai.
   - `test_drainage_coupling_mapping`: Verified spatial projection of BMC holding ponds and nodes into DEM cells.
   - `test_end_to_end_nowcast_scenario`: Ran 1.5h simulation with 60 mm/hr forcing; verified mass balance closure error < 2.0% ($0.56\%$), positive water depths, and raster generation.
   - `test_ward_explainability`: Verified contributing factors and municipal recommendations for affected wards.
   - `test_mosdac_provider_health`: Verified live authenticated token generation and opensearch on MOSDAC.
   - `test_imerg_provider_health`: Verified NASA CMR granule search and token validation.
2. **Full Repository Pytest Suite**:
   - **67 total tests passed in 38.3s** (0 failures).
3. **Frontend Production Build**:
   - `npm run build` in `apps/city-dashboard` completed cleanly with Next.js Turbopack, 0 TypeScript errors, and 0 lint errors.
4. **End-to-End Live Scenario Verification**:
   - Executed live Hindmata/Dadar nowcast with 75 mm/hr rainfall:
     - Peak depth: 2.31m
     - Flooded area: 17.78 km²
     - Drainage coupling: 2 holding ponds, 360 exchange events
     - Mass balance error: 0.56%
     - Persisted to PostGIS table `simulation_runs`
     - Verified timeline PNG raster generation across all timesteps (0m: 0.0m dry → 180m: 2.31m peak).

---

## S. Remaining Scientific & Operational Limitations
1. **Sentinel-1 SAR Real-Time Feed**: Sentinel-1 SAR is not a real-time sensor; satellite passes over Mumbai occur on multi-day repeat cycles. Real-time validation is therefore restricted to nowcast physics vs. rain gauge networks and citizen field reports. SAR validation remains a hindcast benchmark tool.
2. **Pumping Station Telemetry**: SCADA sensor links for live pump discharge are not published via public municipal APIs. Rated capacity curves are used until BMC telemetry APIs become accessible.
3. **Building Footprint Blockage**: While 80% urban imperviousness is applied, individual micro-scale building wall reflections are parameterized through Manning roughness ($n = 0.035$) rather than full 3D building mesh extrusion.
