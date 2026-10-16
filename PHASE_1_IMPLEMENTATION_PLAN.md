# MUFNS Phase 1 Implementation Plan
## Data Foundation → Nowcasting Pipeline Transition
**Date:** September 26, 2026 | **Status:** AUDIT COMPLETE — AWAITING APPROVAL

---

## A. Current Architecture

```
urban-flood-nowcasting/
├── services/                    # Python backend (FastAPI + physics engines)
│   ├── api/main.py             # FastAPI app entrypoint (v0.1.0)
│   │   └── routers/            # 8 API routers
│   │       ├── geodata.py      # GeoJSON/PostGIS spatial data (1164 lines)
│   │       ├── rainfall.py     # Multi-provider rainfall queries
│   │       ├── simulations.py  # Scenario simulation (synthetic storms)
│   │       ├── nowcast.py      # Live nowcasting pipeline
│   │       ├── validation.py   # Satellite SAR validation
│   │       ├── alerts.py       # CAP v1.2 alert generation
│   │       ├── ai.py           # LLM function-calling assistant
│   │       └── cities.py       # City configuration
│   ├── rainfall/               # Multi-sensor rainfall providers
│   │   ├── base.py             # Abstract RainfallProvider
│   │   ├── insat_service.py    # INSAT-3DR HEM/IMC (MOSDAC PostGIS)
│   │   ├── rainfall_fusion.py  # 6-mode fusion engine
│   │   ├── imerg.py            # NASA GPM IMERG provider
│   │   ├── mosdac.py           # MOSDAC API provider
│   │   ├── open_meteo.py       # Open-Meteo NWP provider
│   │   └── synthetic.py        # Synthetic storm generator
│   ├── hydrology/              # Rainfall-runoff models
│   │   ├── infiltration.py     # Horton infiltration (grid-aware)
│   │   └── surface.py          # 2D diffusive wave solver
│   ├── flood/                  # Flood simulation engine
│   │   ├── engine.py           # Master simulation orchestrator
│   │   └── raster_renderer.py  # Depth grid → PNG renderer
│   ├── coupling/exchange.py    # Surface-drainage orifice coupling
│   ├── terrain/                # DEM loading and conditioning
│   │   ├── dem_loader.py       # Copernicus GLO-30 loader + catchments
│   │   └── conditioning.py     # Sink filling
│   ├── nowcast/                # Nowcasting pipeline
│   │   ├── pipeline.py         # 988-line master pipeline
│   │   └── persistence.py      # Persistence-based nowcaster
│   ├── routing/dijkstra.py     # Flood-aware Dijkstra routing
│   ├── risk/road_impact.py     # Road/ward risk assessment
│   ├── ai/operator.py          # LLM "JalDrishti" assistant
│   ├── ml/                     # Neural network models
│   │   ├── models/conv_gru.py  # Skip-ConvGRU (U-RNN architecture)
│   │   ├── models/flood_head.py# Flood prediction head
│   │   └── losses.py           # Custom loss functions
│   ├── alerts/cap.py           # CAP v1.2 XML alert builder
│   ├── validation/satellite_sar.py # SAR flood mapping
│   ├── ingestion/              # Data loaders (DEM, roads, wards, etc.)
│   ├── data/store.py           # Local GeoJSON data store
│   ├── database/               # SQLAlchemy ORM + asyncpg
│   │   ├── connection.py       # Async engine (Aiven PostgreSQL)
│   │   └── models.py           # 15 ORM models (422 lines)
│   └── config/providers.py     # Provider configuration
├── packages/contracts/          # Pydantic data contracts
│   ├── flood.py                # SimulationConfig, MassBalance, FloodSnapshot
│   ├── rainfall.py             # RainfallObservation, RainfallSpatialType
│   ├── provenance.py           # DataQuality, DataOrigin, Provenance
│   ├── datasets.py             # Dataset metadata contracts
│   ├── drainage.py             # Drainage network contracts
│   └── city.py                 # City configuration contracts
├── apps/
│   ├── city-dashboard/         # Next.js admin dashboard (port 3001)
│   └── citizen-web/            # Next.js citizen portal (port 3000)
├── data/                       # Data directory
│   ├── raw/                    # 18 subdirectories
│   ├── processed/              # 16 subdirectories + INSAT-3DR
│   ├── derived/                # 9 subdirectories
│   ├── scripts/                # Ingestion/cleaning/validation
│   ├── metadata/               # Audit reports
│   └── schema.sql              # Full PostGIS DDL (958 lines, 42+ tables)
├── scripts/
│   ├── seed_database.py        # Database seeder (28K lines)
│   └── demo_historical_validation.py
└── tests/                      # Unit + integration test stubs
```

---

## B. Existing Database Tables (42+ base tables from schema.sql)

| # | Table | Description | Rows (last verified) |
|---|-------|-------------|---------------------|
| 1 | alerts | CAP flood alerts | 0 |
| 2 | bridges_and_culverts | Bridge/culvert structures | ~47 |
| 3 | buildings | OSM building footprints | ~30,000 |
| 4 | cities | City configurations | 1 |
| 5 | citizen_reports | Citizen flood reports | 0 |
| 6 | coastal_exposure_zones | Coastal risk areas | ~12 |
| 7 | critical_infrastructure | Hospitals/stations | ~85 |
| 8 | data_ingestion_runs | Provenance: ingestion log | ~20 |
| 9 | data_sources | Provenance: source registry | ~15 |
| 10 | dem_accumulated_flow | Flow accumulation cells | ~700K |
| 11 | dem_flow_direction | D8 flow direction cells | ~700K |
| 12 | dem_metadata | DEM tile metadata | 1 |
| 13 | dem_sinks_depression | Barnes Priority-Flood sinks | ~8,500 |
| 14 | dem_tiles | DEM raster tile URIs | 1 |
| 15 | dem_topographic_wetness_index | TWI raster cells | ~700K |
| 16 | drainage_links | Drainage pipe/channel links | ~0 (ORM only) |
| 17 | drainage_nodes | Drainage manholes/inlets | ~0 (ORM only) |
| 18 | flood_hotspots | Known chronic flood locations | ~35 |
| 19 | flood_snapshots | Simulation timestep snapshots | ~0 |
| 20 | greater_mumbai_boundary | City boundary polygon | 1 |
| 21 | historical_flood_events | Flood occurrence records | ~209 |
| 22 | impervious_surface_fractions | Impervious fraction cells | ~128 |
| 23 | land_use_land_cover | LULC classified polygons | ~69 |
| 24 | macro_drainage_channels | Major drainage channels | ~39 |
| 25 | micro_drainage_network | Minor local drain segments | variable |
| 26 | mumbai_drainage_channels | Drainage channels | ~41 |
| 27 | mumbai_drainage_nodes | Drainage node locations | variable |
| 28 | mumbai_roads | Road network segments | ~14,563 |
| 29 | mumbai_waterbodies | Rivers/nullahs/waterways | ~1,730 |
| 30 | mumbai_wards | 24 administrative wards | 24 |
| 31 | population_distribution_grids | WorldPop grid cells | ~1,215 |
| 32 | pumping_stations | Municipal pumping stations | ~10 |
| 33 | rainfall_observations | AWS ground gauge records | ~27 |
| 34 | rainfall_satellite | GPM IMERG satellite rainfall | ~576 |
| 35 | road_segments | Road segments (ORM mirror) | ~0 |
| 36 | satellite_rainfall_observations | **INSAT-3DR HEM+IMC** | **1,073** |
| 37 | shelters | Emergency shelters | ~25 |
| 38 | simulation_runs | Simulation run metadata | variable |
| 39 | slum_settlements | Informal settlements | ~72 |
| 40 | soil_types/soil_hydro_groups/soil_percolation_params | Soil data | ~6-12 each |
| 41 | tide_observations | Tidal predictions | ~72 |
| 42 | ward_vulnerability_index | Ward flood vulnerability | ~24 |
| 43 | weather_forecasts_grid | NWP forecast grid cells | ~30,240 |
| 44 | weather_observations | AWS weather observations | ~108 |

> **Note:** Database connection is currently OFFLINE (Aiven cloud PostgreSQL ConnectionRefusedError). This must be resolved before pipeline work can proceed.

---

## C. Existing Services — Maturity Assessment

| Service | File | Status | Notes |
|---------|------|--------|-------|
| **Infiltration (Horton)** | hydrology/infiltration.py | PRODUCTION-READY | Grid-aware, impervious-scaled |
| **Surface Flow (Diffusive Wave)** | hydrology/surface.py | PRODUCTION-READY | Vectorized 2D Manning's, mass-conserving |
| **Flood Engine** | flood/engine.py | PRODUCTION-READY | Chains rainfall-infiltration-routing-coupling |
| **Surface-Drainage Coupling** | coupling/exchange.py | PRODUCTION-READY | Signed orifice with capping |
| **DEM Loader** | terrain/dem_loader.py | FUNCTIONAL | Copernicus GLO-30, catchment subgrids |
| **DEM Conditioning** | terrain/conditioning.py | FUNCTIONAL | Priority-flood sink filling |
| **Rainfall Fusion** | rainfall/rainfall_fusion.py | PARTIAL | 6 modes defined but GPM+HEM not truly blending |
| **INSAT-3DR Provider** | rainfall/insat_service.py | FUNCTIONAL | Async PostGIS, accumulation, antecedent |
| **GPM IMERG Provider** | rainfall/imerg.py | FUNCTIONAL | PostGIS-backed historical |
| **Open-Meteo Provider** | rainfall/open_meteo.py | FUNCTIONAL | Live weather + forecast |
| **Nowcast Pipeline** | nowcast/pipeline.py | FUNCTIONAL BUT GAPS | Open-Meteo only; hardcoded imperviousness |
| **ConvGRU Neural Net** | ml/models/conv_gru.py | UNTRAINED | Architecture only, no weights |
| **Road Impact** | risk/road_impact.py | FUNCTIONAL | Passability thresholds |
| **AI Operator** | ai/operator.py | SCAFFOLD | Needs LLM API key |
| **Data Store** | data/store.py | FUNCTIONAL | Local GeoJSON loader |

---

## D. Existing APIs (8 routers)

| Router | Prefix | Status |
|--------|--------|--------|
| geodata | /api/v1/geodata/ | Rich (30+ endpoints) |
| rainfall | /api/v1/rainfall/ | Multi-provider |
| simulations | /api/v1/simulations/ | Uses synthetic storms only |
| nowcast | /api/v1/nowcast/ | Functional (Open-Meteo only) |
| validation | /api/v1/validation/ | Scaffold |
| alerts | /api/v1/alerts/ | CAP v1.2 |
| ai | /api/v1/ai/ | Needs LLM API key |
| cities | /api/v1/cities/ | Basic |

**Missing API endpoints per requirements:**
- GET /datasets, GET /datasets/{id}
- POST /rainfall/fusion
- GET /flood/current, GET /flood/forecast, GET /flood/timeline
- GET /exposure
- GET /provenance/{output_id}
- GET /models

---

## E. Existing Frontend / Admin Pages

Both apps/city-dashboard/ and apps/citizen-web/ are Next.js apps with node_modules installed and .next build cache. They are disconnected from the actual pipeline and should only be touched AFTER backend is proven.

---

## F. MOSDAC Integration — Verified Complete

- 1,073 granules audited (0 corrupt, 0 duplicate hashes)
- Canonical organization in data/processed/rainfall/insat3dr/
- PostGIS table satellite_rainfall_observations with 1,073 rows
- INSAT3DRProvider and RainfallFusionEngine operational
- SHA-256 checksums and provenance registered

---

## G. What is Production-Ready

1. 2D Diffusive Wave surface flow solver
2. Horton infiltration model (grid-aware)
3. Surface-Drainage coupling (signed orifice)
4. Flood engine orchestrator
5. DEM loader + sink filling
6. INSAT-3DR data provider
7. GPM IMERG data provider
8. Open-Meteo live weather
9. Pydantic data contracts
10. Depth grid to PNG raster renderer

---

## H. What is Incomplete — 11 Identified Gaps

| # | Gap | Severity | Description |
|---|-----|----------|-------------|
| 1 | No historical event replay | CRITICAL | Pipeline only runs Open-Meteo live. Cannot replay July 8 2024 cloudburst using INSAT/GPM. |
| 2 | Rainfall fusion is shallow | CRITICAL | GPM_HEM mode just returns HEM, not actual blend. No validation metrics. |
| 3 | No simulation persistence | HIGH | Runs stored in-memory only. No PostGIS-backed reproducible simulation records. |
| 4 | Hardcoded imperviousness | HIGH | Pipeline uses np.full(dem.shape, 0.80) instead of actual LULC/impervious data. |
| 5 | No tide/coastal integration | HIGH | Tide data exists (72 rows) but never used as boundary condition. |
| 6 | No exposure calculation | HIGH | Impact analysis uses hardcoded lists, not spatial overlay with PostGIS. |
| 7 | No dataset registry | HIGH | data_sources exists but no full dataset_registry with versions/metadata. |
| 8 | AI/ML untrained | MEDIUM | ConvGRU architecture exists but no weights, training loop, or data pipeline. |
| 9 | No provenance chain | MEDIUM | Cannot trace output to model to inputs to sources end-to-end. |
| 10 | No automated tests | MEDIUM | tests/ directory has stubs only. |
| 11 | Database offline | BLOCKER | Aiven PostgreSQL returning ConnectionRefusedError. |

---

## I. Proposed Phase 1 Tasks (Ordered by Priority)

### Immediate Blocker

**Task 0: Restore Database Connectivity**
- Diagnose Aiven PostgreSQL connection failure
- Verify .env credentials and network access
- Test with fallback local PostgreSQL if cloud is down

### Phase 1A: Data Standardization (Tasks 1-3)

**Task 1: Dataset Registry and Provenance Tables**
- Extend PostGIS schema: dataset_registry, dataset_versions, processing_runs
- Register every existing dataset with metadata
- Dependencies: Task 0

**Task 2: Connect Real LULC/Imperviousness to Pipeline**
- Replace hardcoded np.full(dem.shape, 0.80) with actual data from PostGIS
- Map LULC classes to Manning's n, CN values, infiltration parameters
- Dependencies: Task 0

**Task 3: Connect Real Soil Parameters to Pipeline**
- Use soil_hydro_groups and soil_percolation_parameters for spatially-varying Horton
- Dependencies: Task 2

### Phase 1B: Rainfall Fusion (Tasks 4-5)

**Task 4: Complete Rainfall Fusion Engine**
- Implement actual GPM+HEM blending
- Add AWS gauge calibration in FULL_FUSION mode
- Store fusion run metadata with source weights and confidence
- Dependencies: Task 0

**Task 5: Rainfall Validation Metrics**
- Compare satellite vs gauge: bias, MAE, RMSE, correlation, peak difference, timing error
- Generate validation reports per event window
- Dependencies: Task 4

### Phase 1C: Historical Event Replay (Tasks 6-8)

**Task 6: Historical Event Replay Pipeline**
- New POST /simulation/replay endpoint
- Accept event_id -> load INSAT + GPM + tide -> run simulation
- Every replay gets a simulation_id with full provenance
- Dependencies: Tasks 2, 3, 4

**Task 7: Tide/Coastal Boundary Integration**
- Use tide_observations as downstream boundary condition
- Implement 5 scenarios: rainfall-only, tide-only, rain+normal, rain+high, rain+extreme
- Dependencies: Task 6

**Task 8: Validation Against Historical Observations**
- Compare simulation flood extent vs historical_flood_events and flood_hotspots
- Calculate: hotspot hit rate, precision, recall, timing error
- Honest uncertainty reporting
- Dependencies: Task 6

### Phase 1D: Exposure and Impact (Task 9)

**Task 9: Spatial Exposure Overlay**
- Replace hardcoded infrastructure with PostGIS spatial joins
- ST_Intersects flood extent with roads, buildings, population, hotspots, infrastructure
- Dependencies: Task 6

### Phase 1E: Simulation Persistence (Task 10)

**Task 10: Persistent Simulation Runs**
- Store every simulation in PostGIS with config, inputs, outputs, mass balance
- Enable GET /simulation/{id}/results and GET /provenance/{output_id}
- Dependencies: Task 6

### Phase 2: AI/Nowcasting (Tasks 11-12) — AFTER Physics Validation

**Task 11: Feature Engineering and Training Data**
- Build feature vectors from validated historical replays
- Train/val/test split BY EVENT (not random pixels)
- Dependencies: Task 8

**Task 12: Train ConvGRU Surrogate**
- Use validated physics runs as training targets
- Hybrid architecture: physics baseline + AI correction
- Dependencies: Task 11

### Phase 3: Admin Panel (Task 13) — AFTER Backend is Proven

**Task 13: Connect Admin Dashboard to Real Pipeline**
- Dashboard consumes actual API endpoints, not dummy data
- Dependencies: All above

---

## J. Dependencies Between Tasks

```
Task 0 (Restore DB)
  ├── Task 1 (Dataset Registry)
  ├── Task 2 (Real LULC/Imperviousness)
  │     └── Task 3 (Real Soil Params)
  └── Task 4 (Complete Fusion)
        └── Task 5 (Rainfall Validation)

Tasks 2,3,4 ──► Task 6 (Historical Event Replay)
                  ├── Task 7 (Tide Integration)
                  ├── Task 8 (Historical Validation)
                  ├── Task 9 (Exposure Overlay)
                  └── Task 10 (Sim Persistence)

Task 8 ──► Task 11 (Feature Engineering)
             └── Task 12 (Train ConvGRU)

Tasks 9,10,12 ──► Task 13 (Admin Dashboard)
```

---

## Risks and Limitations

| Risk | Severity | Mitigation |
|------|----------|------------|
| Database offline | BLOCKER | Check Aiven dashboard, verify billing/credentials |
| No underground drainage | Accepted | Surface-only routing with calibrated params. Do NOT fabricate pipe data. |
| Sparse ground truth | Accepted | Report validation honestly. Hotspot hit rate is achievable. |
| INSAT resolution (~4km) | Inherent | Do not claim high-resolution rainfall. Use as storm-scale forcing. |
| Single DEM (30m) | Inherent | Adequate for macro flood mapping, not micro-drainage features. |

---

## Exact Next Step

**STEP 1: Restore database connectivity and verify all 42+ tables are intact.**

Before any code changes, the PostGIS database must be back online. Please check:
1. Is the Aiven PostgreSQL service still active/paid?
2. Has the IP allowlist changed?
3. Can you connect from another tool (pgAdmin, psql)?

Once DB is confirmed, I will execute Task 1 (Dataset Registry) and Task 2 (Real LULC integration) as the first implementation batch.
