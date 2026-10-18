# Mumbai Urban Flood Nowcasting System (MUFNS) — Comprehensive Project Status Report

**Document Title:** Current State, Verified Data Foundation, Mock/Static Components, and Engineering Roadmap  
**System Name:** Mumbai Urban Flood Nowcasting System (MUFNS)  
**Problem Statement Reference:** SIH26085 — High-Resolution Urban Flood Nowcasting & Drainage Coupling  
**Audit & Generation Date:** October 2026  
**Status:** Operational (Zero-Docker / Standalone Mode)  

---

## 1. Executive Summary

The **Mumbai Urban Flood Nowcasting System (MUFNS)** is an end-to-end operational platform designed for the Municipal Corporation of Greater Mumbai (BMC / MCGM). It bridges live meteorological observations, numerical weather predictions, satellite rainfall granules, 30m digital surface terrain, and stormwater drainage infrastructure to provide **sub-hourly overland flood depth predictions, continuous raster inundation overlays, and actionable municipal impact directives**.

The platform is partitioned into two distinct, purpose-built interfaces:
1. **Municipal Command Dashboard (`apps/city-dashboard` — Port 3001)**: For municipal disaster managers, emergency dispatchers, and ward officers.
2. **Citizen Emergency Portal (`apps/citizen-web` — Port 3000)**: For the public, daily commuters, and vulnerable communities.
3. **Core Hydrodynamic & GIS Backend (`services/api` — Port 8000)**: Powered by FastAPI, NumPy 2D diffusive wave shallow-water equations, and PostGIS spatial structures.

---

## 2. Inventory of Data Currently in the Project

The project adheres to a strict **Zero Data Fabrication** policy. All datasets currently residing in the filesystem and database schema are categorized below:

### 2.1 Terrain, Topography & Physical Derivatives
| Dataset | Canonical Path | Format / Resolution | Source Provider | Role in MUFNS |
| :--- | :--- | :--- | :--- | :--- |
| **Copernicus GLO-30 DEM** | `data/raw/terrain/opentopography_cop30_mumbai_bbox.tif` | GeoTIFF (30m, $1800 \times 1620$) | ESA Copernicus / OpenTopography | Core 2D elevation surface, slope gradient, and depression sink delineation |
| **Slope & Aspect Rasters** | `data/derived/slope/*.npy` | NumPy binary Float32 (30m) | Derived via Horn 8-neighbor gradient | Gravity acceleration and overland flow direction |
| **D8 Flow Direction** | `data/derived/flow_direction/d8_flow_direction.npy` | NumPy binary Uint8 (30m) | Derived steepest-descent D8 | Topographic runoff accumulation pathways |
| **Depression Sinks** | `data/derived/catchments/depression_sinks_m.npy` | NumPy binary Float32 (30m) | Barnes Priority-Flood algorithm | Identifies natural water-trapping depressions (< 8m MSL) |

### 2.2 Meteorology, Satellite & Hydrological Forcing
| Dataset | Canonical Path / Endpoint | Dimensions / Count | Source Provider | Status / Provenance |
| :--- | :--- | :--- | :--- | :--- |
| **Live 9-Point Spatial Mesh** | REST API (`api.open-meteo.com`) | 9 spatial nodes across Mumbai | Open-Meteo (ECMWF IFS / DWD ICON) | **LIVE**: Colaba, Dadar, Kurla, Andheri, Borivali, Vikhroli, Thane, Bandra, Santacruz |
| **Weather Forecasts (7-Day)** | `data/processed/weather/forecasts.csv` | 30,240 rows (168h lead time) | Open-Meteo Archive | **STATIC/HISTORICAL**: 20 physical variables (rain, temp, wind, pressure, soil) |
| **ISRO MOSDAC INSAT-3DR** | `data/processed/rainfall/insat3dr/` | 1,073 GeoTIFF granules (2.19 MB) | ISRO Space Applications Centre | **AUTHENTIC**: Event windows for July 2024, late-July 2024, and August 2025 |
| **NASA GPM IMERG 2005 Grid**| `data/raw/satellite/imerg_20050726_halfhourly_mumbai_grid.csv` | 576 rows (0.1° half-hourly) | NASA Earthdata GES DISC | **HISTORICAL**: Benchmark satellite precipitation for July 26, 2005 deluge |
| **10-Year Rain Gauge Series**| `data/raw/rainfall/hourly_gauge_data_2015_2025.csv` | 25,000 hourly rows | IMD / MCGM Rain Gauge Network | **HISTORICAL**: 8 gauge stations (Santacruz, Colaba, Dadar, etc.) |
| **2005 Deluge 15-Min Series** | `data/raw/rainfall/event_2005_07_26_santacruz_colaba_15min.csv`| 192 rows (15-min intervals) | IMD Santacruz & Colaba | **BENCHMARK**: 944 mm 24h cloudburst hyetograph for model stress testing |

### 2.3 Municipal Infrastructure & Administrative Boundaries
| Dataset | Canonical Path | Feature Count / Size | Source Provider | Role in MUFNS |
| :--- | :--- | :--- | :--- | :--- |
| **BMC Administrative Wards**| `data/cities/mumbai/wards.geojson` | 24 municipal ward polygons | MCGM / OpenCity | Ward boundary delineation, census population, risk scoring |
| **Critical Infrastructure** | `data/processed/critical_infrastructure/` | 2,002 facilities | OpenStreetMap Emergency & Transit | Hospitals (1,151), clinics (507), railway stations (165), police, fire |
| **Road Network Graph** | `data/processed/roads/` | 14,563 segments (3,310 km) | OpenStreetMap Road Network | Evacuation routing and transport network waterlogging severance |
| **Critical Arterial Corridors** | `mumbai_flood_spatial_data/01_roads/` | 78 arterial segments (248.7 km) | MCGM CMP / MMRDA | Lifeline transport corridors (WEH, EEH, SV Road, LBS Marg) |
| **Waterways & Nullahs** | `data/processed/rivers/mumbai_waterways.geojson` | 1,730 features (81 rivers, 724 drains) | OpenStreetMap Hydrography | Natural rivers (Mithi, Dahisar, Poisar, Oshiwara) and open nullahs |
| **BRIMSTOWAD Drainage Assets**| `data/raw/drainage/` | 35 nodes, 8 trunk channels, 8 pumps | MCGM SWD Department | Surface-drainage 1D-2D coupled orifice exchange locations |
| **Building Footprints** | `data/raw/buildings/` | 30,000 building polygons | Microsoft Global ML Footprints | Structural inundation exposure calculations |
| **Emergency Relief Shelters**| `data/raw/shelters/shelters.geojson` | 10 designated municipal shelters | MCGM Disaster Management | Evacuation destinations (capacity figures preserved as NULL) |
| **Chronic Flood Hotspots** | `mumbai_flood_spatial_data/04_flood_risk/` | 35 official municipal spots | MCGM Disaster Management | Hindmata, Milan Subway, King's Circle, Gandhi Market, Sion Circle |
| **Historical Flood Events** | `mumbai_urban_flood_2016_2025 (1).geojson` | 209 ground-truth events (2016–2025) | BMC Disaster Management Records | Ground-truth flood depths (in cm), duration, and rainfall totals |
| **Apollo Bunder Tide Series** | `data/raw/tides/` | 72 hourly records (2005) | Mumbai Port Trust / Survey of India | Coastal tidal level boundary and flap gate closure threshold (3.0m CD) |

---

## 3. How Everything Is Currently Operating

```
[ Open-Meteo 9-Point Mesh / Scenario Slider ] ──► [ Spatial Hyetograph Schedule ]
                                                              │
                                                              ▼
[ Copernicus 30m DEM + Priority-Flood Sinks ] ──► [ 2D Diffusive Wave Solver ]
                                                              │
                                            ┌─────────────────┴─────────────────┐
                                            ▼                                   ▼
                             [ BRIMSTOWAD 1D-2D Coupling ]           [ Bilinear Gaussian Smoothing ]
                             (14 Nodes, Pumps & Ponds)                          │
                                            │                                   ▼
                                            ▼                     [ Continuous Depth Raster PNG ]
                              [ PostGIS Persistence & ]          (/api/v1/nowcast/latest/raster.png)
                              [ Ward Explainability Engine ]                    │
                                            │                                   ▼
                                            ├───────────────────────────────────┤
                                            ▼                                   ▼
                             [ Municipal Command Center ]          [ Citizen Emergency Portal ]
                              (http://localhost:3001)               (http://localhost:3000)
```

1. **Backend Service (`services.api.main:app`)**:
   * Running on `http://127.0.0.1:8000` via Uvicorn.
   * Exposes **17 active API routers** (`geodata`, `rainfall`, `simulations`, `nowcast`, `validation`, `alerts`, `ai`, `cities`, `replay`, `scheduler`, `decision`, `tide`, `drainage`, `impact`, `field_ops`, `auth`, `ml`).
   * Automatically executes a 5,400-step 2D diffusive wave simulation on startup across the Hindmata/Dadar catchment.
2. **Municipal Command Dashboard (`apps/city-dashboard`)**:
   * Running on `http://localhost:3001` via Next.js 16 (Turbopack).
   * Clean white municipal interface with Esri World Light Gray Canvas basemap.
   * 5-Step simulation-to-impact workflow: Catchment Selection $\rightarrow$ 2D Overland Physics $\rightarrow$ Continuous Raster Overlay $\rightarrow$ Multi-Sector Exposure $\rightarrow$ CAP v1.2 Directives.
   * Interactive floating timeline player (`NOW`, `+30m`, `+60m`, `+90m`, `+120m`, `+180m`).
   * Ward Explainability Drawer answering *"Why is this area flooding?"* with physical drivers and recommendations.
3. **Citizen Emergency Portal (`apps/citizen-web`)**:
   * Running on `http://localhost:3000` via Next.js 16 (Turbopack).
   * Clean public interface offering current advisories, shelter directions, localized waterlogging submission form, and JalDrishti conversational emergency AI.

---

## 4. What Is Currently Dummy, Static, or Fallback (Honest Engineering Audit)

While the hydrodynamic equations, DEM routing, and spatial datasets are authentic, several components currently operate as **static proxies, simulated mocks, or fallbacks**:

> [!WARNING]
> ### Transparent Technical Debt Matrix

| Component / Subsystem | Current Implementation | Real-World / Target State | Why It Is Currently Static or Mocked |
| :--- | :--- | :--- | :--- |
| **PostGIS Database Connection** | **Local In-Memory / GeoJSON Fallback**: When the remote Aiven cloud host cannot be resolved (`[Errno 11001] getaddrinfo failed`), the backend automatically falls back to local memory and disk GeoJSON files. | Local containerized PostGIS instance with persistent connection pooling. | Remote cloud database dependency is susceptible to local DNS/network drops. |
| **ML Surrogate Model (`SkipConvGRU`)** | **Untrained Architecture**: Code structure for PyTorch Skip-ConvGRU, FloodPredictionHead, and CurriculumLoss exists, but model weights are **untrained**. ML router returns heuristic fallback. | Checkpoint trained on 500+ physical simulation runs for sub-second (<50ms) inference. | Requires running a batch physics simulation dataset generator and training loop on GPU/CPU. |
| **Stormwater Pumping Telemetry** | **Static Rated Capacities**: Pumping stations (Love Grove, Cleveland Bunder, Britannia) display rated pump volumes (e.g. 120 MLD, 6 pumps at 100% capacity). | Live SCADA telemetry with real-time operational status (active pumps, power availability, gate closure). | MCGM / BMC does not publish open public SCADA API feeds for pumping stations. |
| **Underground Drainage Network (1D)** | **Macro-Coupling Proxy**: Only 14 macro holding ponds and outfalls are coupled. Local roadside piped gutters are represented by a flat 25 mm/h urban drainage deduction. | Full 1D EPA-SWMM pipe network modeling barrel diameters, pipe invert levels, and manhole surcharge. | Complete AutoCAD/GIS municipal pipe drainage inventories are proprietary to MCGM SWD. |
| **Building Flow Blockage** | **Bulk Roughness & Imperviousness**: Buildings are parameterized through Manning roughness ($n=0.035$) and 70% imperviousness rather than solid extruded flow barriers. | High-resolution 2D porosity or building wall reflection mesh. | Hydrodynamic solver uses a 30m grid cell size, which cannot resolve individual 5m building walls. |
| **Emergency Alert Broadcast (CAP)** | **In-Memory XML Generator**: Generates valid OASIS CAP v1.2 XML strings and JSON directives, but does not push to public telecommunication towers. | Live gateway integration with NDMA / C-DOT Integrated Alert System (SACHET) and BMC SMS gateway. | Access to national emergency broadcast APIs requires government department authorization. |
| **Citizen Report Verification** | **Rule-Based Prototype**: Incident review queue allows operators to click `Verify` or `Reject` based on coordinate checks. | Automated multi-sensor cross-validation (comparing reported cm depth with radar & 2D simulated depth). | Full spatial-temporal clustering algorithm is partially implemented. |
| **Live Doppler Radar (DWR)** | **Open-Meteo Hourly Proxy**: Relies on ECMWF/DWD NWP models and surface gauge feeds. | Real-time S-band / X-band Doppler Radar reflectivity ($Z$) from IMD Colaba / Veravali. | Real-time IMD Doppler Radar QPE API access is restricted to official government channels. |

---

## 5. Prioritized Engineering Roadmap & Things to Improve

To transition MUFNS from a competitive hackathon prototype to an enterprise municipal system, work should proceed in the following prioritized phases:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 1: Zero-Internet Pitch Mode (Deterministic Replay Engine)             │
│ • Bundle July 26, 2005 & July 8, 2024 deluges into 1-click replay toggles  │
│ • Containerize local PostGIS via docker-compose to eliminate DNS timeouts   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
┌──────────────────────────────────────▼──────────────────────────────────────┐
│ PHASE 2: Train the ConvGRU ML Surrogate                                     │
│ • Generate 300 synthetic physics simulation tensor pairs                    │
│ • Train model weights to enable instant (<50ms) depth raster generation     │
│ • Provide side-by-side "Physics vs. ML Surrogate" comparison in UI         │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
┌──────────────────────────────────────▼──────────────────────────────────────┐
│ PHASE 3: Municipal Operational Intelligence                                 │
│ • Flood-Aware Emergency Routing: Sever roads >30cm water depth              │
│ • Micro-DEM Patching: 5m synthetic elevation grid for Hindmata/Milan Subway  │
│ • Citizen Report Corroborator: Auto-correlate citizen pins with model depth │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.1 Phase 1 — Hackathon / Demo Bulletproofing *(Immediate Priority)*
1. **1-Click Offline Replay Engine**:
   * Pre-compute and cache full simulation depth rasters and impact statistics for:
     * *Scenario A*: **July 26, 2005 Cloudburst** (944 mm historic deluge — extreme stress test).
     * *Scenario B*: **July 8, 2024 Cloudburst** (>300 mm in 6 hours with peak high tide).
     * *Scenario C*: **Normal Monsoon + Spring Tide Lock** (4.5m tide locking gravity floodgates).
   * Add a top-bar toggle: `[ LIVE OPEN-METEO ]` vs `[ BENCHMARK EVENT REPLAY ]`.
2. **Local Containerized PostGIS**:
   * Add a lightweight Docker Compose definition running PostGIS with pre-seeded SQL tables so database queries never depend on cloud network connectivity.

### 5.2 Phase 2 — Machine Learning Surrogate Engine
1. **Batch Physics Data Generation**:
   * Script the 2D diffusive wave solver to run across 300 combinations of rainfall rate (10–180 mm/h), storm duration (1–6 h), and tidal head ($0.5 - 4.5\text{m}$).
   * Save pairs as HDF5/Zarr tensors: `[Rainfall Schedule, DEM, Imperviousness]` $\rightarrow$ `[Depth Grid Timesteps]`.
2. **Train ConvGRU**:
   * Execute `services/ml/train.py` using PyTorch to fit model weights.
   * Mount the trained weights in `services/ml/inference.py` to allow operators to choose between **"High-Precision Physics (3s)"** and **"Instant ML Surrogate (40ms)"**.

### 5.3 Phase 3 — Municipal Operational Enhancements
1. **Flood-Aware Dijkstra Evacuation Routing**:
   * Wire the 14,563 road segments to the simulated depth grid.
   * If water depth on a road segment exceeds 30 cm (engine intake/exhaust threshold for ambulances), penalize or sever the road weight.
   * Dynamically render alternate safe routes to major trauma centers (KEM Hospital, Sion Hospital, Lilavati Hospital).
2. **Hotspot Micro-Elevation Inset**:
   * Blend a 5m synthetic micro-DEM patch over **Hindmata, Milan Subway, and Gandhi Market** to visualize road curb overtopping and underpass flooding in fine detail.
3. **Citizen Corroboration Engine**:
   * When a resident submits an incident with a measured depth (e.g., "50 cm waterlogged on Katrak Road"), compare it with the model's depth array at that cell.
   * If within 15%, badge the citizen report as **"Scientifically Corroborated Ground Truth"**.

---

## 6. Current Technical Stack & Execution Commands

### 6.1 Technology Stack
* **Hydrodynamics & Infiltration**: NumPy, SciPy, Rasterio, Shapely, PyProj.
* **Backend API**: FastAPI 0.111, Uvicorn, Pydantic v2, Structlog, AsyncPG, GeoAlchemy2.
* **Frontends**: Next.js 16 (React 19), Turbopack, Leaflet, CartoDB/Esri GIS Tiles.
* **Database**: PostgreSQL 18.6 + PostGIS 3.6.4 (with automatic local memory fallback).

### 6.2 Manual Launch Commands
All services run locally without Docker:

```powershell
# 1. Start FastAPI Backend (Port 8000)
python -m uvicorn services.api.main:app --host 127.0.0.1 --port 8000 --reload

# 2. Start Municipal Command Dashboard (Port 3001)
npm --prefix apps/city-dashboard run dev -- -p 3001

# 3. Start Citizen Emergency Portal (Port 3000)
npm --prefix apps/citizen-web run dev -- -p 3000
```
