# MUFNS — Phase 2 Master Plan

**Author:** Antigravity Agent  
**Date:** 2026-09-26  
**Repository:** `e:\urban\sih\urban-flood-nowcasting\`  
**Status:** AWAITING APPROVAL  

---

## 1. Current Architecture (Verified Ground Truth)

### 1.1 Codebase Size

| Metric | Value |
|--------|-------|
| Python files | 171 |
| Total Python size | ~1,074 KB |
| Test files | 15 (9 formal + 6 scratch) |
| ORM model classes | 17 |
| API routers | 10 |
| API endpoints | 55+ |
| Service packages | 20 |
| Next.js frontend apps | 2 |
| PostGIS tables (schema) | 17 ORM-mapped |

### 1.2 Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                        FRONTEND APPS                             │
│  city-dashboard (Next.js :3001)  │  citizen-web (Next.js :3000) │
│  9 components (82KB page.tsx)     │  5 tabs (map/ai/shelter/     │
│  Modules: overview, risk, sim,   │  report/history)             │
│  incidents, drainage, historical, │                              │
│  validation, weather, health      │                              │
├──────────────────────────────────────────────────────────────────┤
│                     FastAPI API (uvicorn :8000)                   │
│  main.py → Lifespan + CORS + 10 routers                        │
│  ┌─────────┬──────────┬────────────┬──────────┐                 │
│  │ geodata │ nowcast  │ simulations│ rainfall │                 │
│  │ cities  │ ai       │ alerts     │validation│                 │
│  │ replay  │          │            │          │                 │
│  └─────────┴──────────┴────────────┴──────────┘                 │
├──────────────────────────────────────────────────────────────────┤
│                     SERVICE LAYER (20 packages)                   │
│  ┌─────────────────────────────────────────────┐                │
│  │ PHYSICS   │ flood/ hydrology/ coupling/     │ ✅ VALIDATED   │
│  │           │ hydraulics/ terrain/ routing/   │                │
│  ├───────────┼─────────────────────────────────┤                │
│  │ RAINFALL  │ rainfall/ (open_meteo, imerg,   │ ✅ LIVE        │
│  │           │ mosdac, synthetic, fusion)       │                │
│  ├───────────┼─────────────────────────────────┤                │
│  │ NOWCAST   │ nowcast/ (pipeline, replay,     │ ✅ WORKING     │
│  │           │ persistence)                     │                │
│  ├───────────┼─────────────────────────────────┤                │
│  │ ML        │ ml/ (conv_gru, flood_head,      │ ⚠️ UNTRAINED   │
│  │           │ losses)                          │                │
│  ├───────────┼─────────────────────────────────┤                │
│  │ RISK      │ risk/ (exposure_engine,         │ ⚠️ NO API      │
│  │           │ road_impact)                     │                │
│  ├───────────┼─────────────────────────────────┤                │
│  │ COASTAL   │ coastal/ (tide_service)         │ ⚠️ NO API      │
│  ├───────────┼─────────────────────────────────┤                │
│  │ AI        │ ai/ (operator)                  │ ⚠️ NO API      │
│  ├───────────┼─────────────────────────────────┤                │
│  │ ALERTS    │ alerts/ (cap)                   │ ⚠️ IN-MEMORY   │
│  ├───────────┼─────────────────────────────────┤                │
│  │ VALIDATION│ validation/ (satellite_sar,     │ ✅ WORKING     │
│  │           │ historical_validation)           │                │
│  └───────────┴─────────────────────────────────┘                │
├──────────────────────────────────────────────────────────────────┤
│  DATABASE — Aiven PostgreSQL 18.6 + PostGIS 3.6.4               │
│  17 ORM models (SQLAlchemy + GeoAlchemy2)                       │
│  Connection: services/database/connection.py                     │
│  Fallback: services/data/store.py (local GeoJSON)               │
│  Migration: Base.metadata.create_all (NO ALEMBIC)               │
└──────────────────────────────────────────────────────────────────┘
```

### 1.3 Existing Capabilities (Verified Working)

| Capability | Module | Evidence |
|------------|--------|----------|
| 2D Diffusive Wave Solver | `flood/engine.py` | Mass balance 0.04%, test_physics.py passes |
| Horton Infiltration | `hydrology/infiltration.py` | Parametric tests pass |
| Surface Flow Routing | `hydrology/surface.py` | Coupled with engine |
| DEM Loading (Copernicus GLO-30) | `terrain/dem_loader.py` | 4 catchment regions working |
| Sink Filling | `terrain/conditioning.py` | Priority-flood algorithm |
| LULC → Hydrologic Params | `terrain/spatial_params.py` + `config/lulc_params.py` | 17 LULC classes mapped |
| Orifice Exchange Coupling | `coupling/exchange.py` | CouplingEngine class |
| Drainage Network Model | `hydraulics/network.py` | Node-link topology |
| Dijkstra Routing | `routing/dijkstra.py` | Shortest-path on network |
| Open-Meteo Live Weather | `rainfall/open_meteo.py` | 9-point spatial grid |
| NASA IMERG Satellite | `rainfall/imerg.py` | CMR granule search |
| ISRO MOSDAC Satellite | `rainfall/mosdac.py` | INSAT-3DR HEM/IMC |
| Rainfall Fusion Engine | `rainfall/rainfall_fusion.py` | HEM+IMC+GPM+bias correction |
| Persistence Nowcast | `nowcast/persistence.py` | Lagrangian decay |
| Full Nowcast Pipeline | `nowcast/pipeline.py` (43KB) | Weather→Flood integrated |
| Historical Replay | `nowcast/historical_replay.py` | July 2024 event validated |
| SAR Validation Framework | `validation/satellite_sar.py` | IoU/CSI/POD metrics |
| Historical Validation | `validation/historical_validation.py` | Extended benchmarks |
| CAP v1.2 Alert Generation | `alerts/cap.py` | XML generation |
| Ward Risk Scoring | `geodata.py` `/ward-risk` | H+E+V composite |
| Citizen Report CRUD | `geodata.py` | PostGIS persistence |
| System Health Check | `geodata.py` `/system-health` | Multi-subsystem probe |

### 1.4 Reusable Components (DO NOT REBUILD)

| Component | File(s) | Why |
|-----------|---------|-----|
| Physics engine | `services/flood/engine.py` | Validated at 0.04% mass balance |
| Rainfall providers | `services/rainfall/*.py` | Live APIs working |
| Rainfall fusion | `services/rainfall/rainfall_fusion.py` | Multi-source blending verified |
| Nowcast pipeline | `services/nowcast/pipeline.py` | 43KB of integrated logic |
| Historical replay | `services/nowcast/historical_replay.py` | July 2024 event proven |
| DEM/terrain stack | `services/terrain/*.py` | Copernicus GLO-30 working |
| Database models | `services/database/models.py` | 17 models, PostGIS indexed |
| ML architecture | `services/ml/models/*.py`, `losses.py` | Well-designed, needs training |
| Exposure engine | `services/risk/exposure_engine.py` | 9 PostGIS spatial queries |
| Tide service | `services/coastal/tide_service.py` | 5 tide scenarios |
| Dashboard components | `apps/city-dashboard/src/components/` | 9 React components |
| Citizen app | `apps/citizen-web/src/` | 5-tab portal |

---

## 2. Verified Gaps

### 2.1 In-Memory State (Must Migrate to PostGIS)

| Location | Variable | Impact |
|----------|----------|--------|
| `alerts.py:22` | `_alerts: list[dict] = []` | All alerts lost on restart |
| `simulations.py:29` | `_simulations: dict[str, dict] = {}` | Simulation results lost |
| `simulations.py:124` | `_simulations: dict[str, dict] = {}` | **DUPLICATE** declaration (bug) |
| `validation.py:30` | `_validation_reports: dict[str, dict] = {}` | Validation reports lost |
| `pipeline.py:488` | `_latest_nowcast: Optional[NowcastResult] = None` | Latest nowcast lost |
| `cities.py:34` | `_standalone_cities: dict = {}` | Acceptable (DB fallback exists) |

### 2.2 Code Defects Found

| File | Issue |
|------|-------|
| `simulations.py` | Duplicate `router = APIRouter()` (lines 26 and 121), duplicate `logger` (lines 25 and 120), duplicate `_simulations` (lines 29 and 124). Second block shadows first. |
| `simulations.py:149` | Still uses `np.full(dem.shape, 0.80)` for imperviousness — should use `spatial_params.py` |
| `validation.py:124` | Same hardcoded `np.full(dem.shape, 0.85)` imperviousness |
| `pipeline.py:895` | Same hardcoded `np.full(dem.shape, 0.80)` fallback |
| `historical_replay.py:300` | Same hardcoded imperviousness fallback |

### 2.3 Services Without API Integration

| Service | File | Has Router? |
|---------|------|-------------|
| ExposureEngine | `services/risk/exposure_engine.py` (283 lines, 9 PostGIS queries) | NO |
| RoadImpactAssessor | `services/risk/road_impact.py` (6.3KB) | NO |
| TideService | `services/coastal/tide_service.py` (253 lines, 5 scenarios) | NO |
| AIOperator | `services/ai/operator.py` (254 lines, LLM framework) | NO (ai.py router uses rule-based, not this) |

### 2.4 Missing Infrastructure

| Item | Status |
|------|--------|
| Alembic migrations | NOT INITIALIZED (pyproject.toml lists `alembic>=1.13.0` as dependency) |
| Automated scheduler | NO cron/scheduler |
| ML training pipeline | Architecture only, no training code |
| ML inference endpoint | No `/api/v1/ml/*` routes |
| Confidence/uncertainty | Point estimates only |
| Data QC layer | No validation/flagging pipeline |
| API authentication | No auth |
| Impact API endpoints | `/api/v1/impact/*` does not exist |
| Drainage status API | `/api/v1/drainage/status` does not exist |
| Decision support engine | No recommendation system |
| Field worker workflow | No task assignment system |

### 2.5 Existing Tests (Verified)

| Test File | Tests | Status |
|-----------|-------|--------|
| `tests/unit/test_physics.py` (9KB) | Horton, surface flow, coupling, mass balance | REAL physics tests |
| `tests/unit/test_alerts_routing.py` (4.7KB) | CAP XML generation, severity thresholds | Working |
| `tests/unit/test_contracts.py` (3.3KB) | Pydantic contract validation | Working |
| `tests/unit/test_data_foundation.py` (2KB) | Data store validation | Working |
| `tests/unit/test_dem_ingestion.py` (3.9KB) | DEM loading tests | Working |
| `tests/unit/test_provenance_boundaries.py` (1.6KB) | Provenance tracking | Working |
| `tests/unit/test_validation_engine.py` (4.2KB) | Validation metrics | Working |
| `tests/integration/test_nowcast_pipeline.py` (4.7KB) | End-to-end nowcast | Working |
| `tests/integration/test_simulation.py` (5.8KB) | Simulation integration | Working |
| `test_july2024_replay.py` (6.4KB) | Historical replay verification | Working |

---

## 3. Dependency Graph

```
    2A: Operational Data Foundation
    ├── 2B: Automated Nowcasting
    │   ├── 2D: Uncertainty & Validation
    │   └── 2F: Alerts & Decision Support
    ├── 2C: ML Surrogate
    │   └── 2D: Uncertainty & Validation
    ├── 2E: Tide / Drainage / Impact
    │   └── 2F: Alerts & Decision Support
    └──────────────────────────────────┐
        2F: Alerts & Decision Support  │
        ├── 2G: AI Assistant           │
        └── 2H: Workflows             │
            └── 2I: Security/Deploy    │
```

Critical path: **2A → 2B → 2F → 2H → 2I**

Parallel tracks possible: **2C** (ML) and **2E** (Tide/Drainage/Impact) can run alongside **2B**.

---

## 4. Implementation Order

### PHASE 2A — Operational Data Foundation

**Goal:** Persistent, production-grade data layer. Everything else depends on this.

| Task ID | Task | Files to Change | Definition of Done |
|---------|------|-----------------|-------------------|
| 2A-1 | Initialize Alembic | New: `alembic/`, `alembic.ini` | `alembic upgrade head` creates all tables from existing models |
| 2A-2 | Fix simulations.py duplicate | `services/api/routers/simulations.py` | Remove duplicate router/logger/dict at lines 120-124. Single router, no shadowing. |
| 2A-3 | Enhance Alert ORM model | `services/database/models.py` | Add columns: ward, status, valid_from, valid_until, affected_population, recommended_action, escalation_level, acknowledgement, resolution, deduplication_key |
| 2A-4 | Enhance SimulationRun ORM model | `services/database/models.py` | Add columns: terrain_version, parameter_set_json, runtime_seconds, max_depth_m, flooded_area_km2, flood_extent_geojson_uri, confidence_score, validation_metadata |
| 2A-5 | New: ValidationReport ORM model | `services/database/models.py` | New table for validation reports currently in `_validation_reports` dict |
| 2A-6 | New: NowcastRun ORM model | `services/database/models.py` | New table for nowcast run results currently in `_latest_nowcast` global |
| 2A-7 | Migrate alerts to PostGIS | `services/api/routers/alerts.py` | Replace `_alerts: list[dict]` with `Alert` ORM. Lifecycle: created→active→expired→resolved. All alerts survive restart. |
| 2A-8 | Migrate simulations to PostGIS | `services/api/routers/simulations.py` | Replace `_simulations: dict` with `SimulationRun` ORM. Lifecycle: queued→running→completed→failed. |
| 2A-9 | Migrate validation to PostGIS | `services/api/routers/validation.py` | Replace `_validation_reports: dict` with `ValidationReport` ORM. |
| 2A-10 | Migrate nowcast to PostGIS | `services/nowcast/pipeline.py` | Replace `_latest_nowcast` global with `NowcastRun` ORM. Keep in-memory cache for fast reads. |
| 2A-11 | Fix hardcoded imperviousness | `simulations.py`, `validation.py`, `pipeline.py`, `historical_replay.py` | Replace all `np.full(dem.shape, 0.80)` / `0.85` with call to `spatial_params.get_spatial_params()` |
| 2A-12 | Data QC pipeline | New: `services/data/qc.py`, `services/api/routers/data_quality.py` | Endpoints: `/api/v1/data/qc`, `/api/v1/data/provenance`, `/api/v1/data/health`. QC checks: missing, impossible, duplicate, stale, spike, provider disagreement. |
| 2A-13 | Create Alembic migration for all changes | `alembic/versions/001_*.py` | Single migration covering all model changes in 2A. |

**Tests required:**
- Simulation lifecycle roundtrip (create → update → read from DB)
- Alert persistence and deduplication
- Validation report persistence
- QC flag generation for bad rainfall values
- Alembic migration up/down
- Physics regression: `test_physics.py` still passes

---

### PHASE 2B — Automated Nowcasting

**Goal:** System runs every 15 minutes without human intervention.

| Task ID | Task | Files to Change | Definition of Done |
|---------|------|-----------------|-------------------|
| 2B-1 | Scheduler service | New: `services/scheduler/nowcast_scheduler.py` | APScheduler 15-min interval. Restart-safe. No duplicate runs (checks DB for in-progress run). |
| 2B-2 | Pipeline orchestration enhancement | `services/nowcast/pipeline.py` | Full cycle: fetch→QC→fuse→nowcast→persist→risk→alert check. Each step logged with timing. |
| 2B-3 | Provider failure handling | `services/rainfall/*.py` providers | Log failure, mark provider degraded, continue with available sources, record degradation in result metadata. |
| 2B-4 | Dynamic ward risk | `services/api/routers/geodata.py` | `/ward-risk` incorporates latest nowcast flood depths into hazard scoring. |
| 2B-5 | Scheduler API | New or modify `main.py` | `/api/v1/scheduler/status`, `/api/v1/scheduler/trigger` (manual trigger for testing) |
| 2B-6 | Dashboard live state | Frontend apps | Auto-refresh from latest persistent nowcast via polling or SSE. |

**Tests required:**
- Scheduler creates exactly 1 run per cycle (no duplicates)
- Failed provider does not crash pipeline (degrades gracefully)
- Dashboard receives updated data after scheduled run

---

### PHASE 2C — ML Surrogate

**Goal:** Trained ConvGRU model runs alongside physics engine.

| Task ID | Task | Files to Change | Definition of Done |
|---------|------|-----------------|-------------------|
| 2C-1 | Training data generation | New: `services/ml/data_generator.py` | Generate 500+ physics simulations. Vary: rainfall intensity (10-200 mm/h), duration (1-6h), spatial distribution, catchment. |
| 2C-2 | Dataset & DataLoader | New: `services/ml/dataset.py` | HDF5/Zarr dataset. Train/val/test split (70/15/15). Each sample: rainfall sequence → depth grid sequence. |
| 2C-3 | Training script | New: `services/ml/train.py` | PyTorch Lightning trainer using existing `SkipConvGRUEncoder` + `ConvGRUDecoder` + `FloodPredictionHead` + curriculum loss. |
| 2C-4 | Evaluation & metrics | New: `services/ml/evaluate.py` | MAE, RMSE, CSI, IoU, POD, FAR on test set. Compare against physics ground truth. |
| 2C-5 | Model registry | New: `services/ml/registry.py`, new DB table `ml_models` | Store: version, training dataset hash, parameters, metrics, checkpoint path, date, model hash. |
| 2C-6 | Inference service | New: `services/ml/inference.py` | Load checkpoint, predict on rainfall input. Returns depth grid + inference latency. |
| 2C-7 | ML API router | New: `services/api/routers/ml.py` | `/api/v1/ml/predict`, `/api/v1/ml/models`, `/api/v1/ml/metrics` |
| 2C-8 | Side-by-side comparison | Modify: `services/api/routers/nowcast.py` | Nowcast response can include: `physics_prediction`, `ml_prediction`, `comparison`, `recommended_prediction`, `model_confidence`. |
| 2C-9 | ML fallback logic | `services/nowcast/pipeline.py` | If ML unavailable or low confidence → physics only. Never fabricate ML output. |

**Tests required:**
- Data generator produces valid input/output tensor pairs
- Training runs without error for 1 epoch on sample data
- Inference produces depth grid of correct shape
- ML fallback to physics when model file missing

---

### PHASE 2D — Uncertainty & Validation

**Goal:** Every prediction has measurable, explainable confidence.

| Task ID | Task | Files to Change | Definition of Done |
|---------|------|-----------------|-------------------|
| 2D-1 | Confidence engine | New: `services/nowcast/confidence.py` | Multi-factor confidence: provider count, provider agreement, data freshness, spatial coverage, model divergence (physics vs ML), historical CSI. |
| 2D-2 | Nowcast uncertainty in responses | Modify: `services/nowcast/pipeline.py` | Every `NowcastResult` includes: `confidence_score` (0-100), `confidence_level` (HIGH/MODERATE/LOW), `confidence_factors` (list of contributing factors). |
| 2D-3 | Unified validation dashboard API | Modify/new: validation router | Endpoint showing IoU/CSI/POD/FAR/RMSE for both physics and ML across events. |
| 2D-4 | Auto-calibration framework | New: `services/calibration/optimizer.py` | Optimize Manning's n, Horton params against historical observations. Store: parameter_set → event → metrics_before → metrics_after → version. |

**Tests required:**
- Confidence degrades when provider fails
- Confidence factors explain "why" for each level
- Calibration produces versioned parameter sets

---

### PHASE 2E — Tide / Drainage / Impact

**Goal:** Connect existing services to API and to the nowcast pipeline.

| Task ID | Task | Files to Change | Definition of Done |
|---------|------|-----------------|-------------------|
| 2E-1 | Tide API router | New: `services/api/routers/tide.py` | `/api/v1/tide/current`, `/api/v1/tide/scenarios`, `/api/v1/tide/forecast` — backed by existing `TideService`. |
| 2E-2 | Tide boundary coupling in engine | Modify: `services/nowcast/pipeline.py`, `services/flood/engine.py` | `TideService` provides boundary condition schedule to flood engine for coastal cells. |
| 2E-3 | Drainage status router | New: `services/api/routers/drainage.py` | `/api/v1/drainage/status` (live drainage state), `/api/v1/drainage/surcharge` (identify overloaded links). |
| 2E-4 | Impact router | New: `services/api/routers/impact.py` | `/api/v1/impact/population`, `/buildings`, `/roads`, `/infrastructure`, `/shelters`, `/summary` — all backed by existing `ExposureEngine`. |
| 2E-5 | Impact in nowcast pipeline | Modify: pipeline | Every nowcast auto-computes exposure via `ExposureEngine.compute_exposure()`. Results persisted. |

**Tests required:**
- Tide scenario changes simulation boundary condition
- Impact numbers come from PostGIS spatial queries (not hardcoded)
- Drainage surcharge correctly identified when capacity exceeded

---

### PHASE 2F — Alerts & Decision Support

**Goal:** Automated alert lifecycle and actionable decision recommendations.

| Task ID | Task | Files to Change | Definition of Done |
|---------|------|-----------------|-------------------|
| 2F-1 | Alert engine | New: `services/alerts/engine.py` | Full lifecycle: detection→threshold check→dedup→severity assignment→creation→escalation→acknowledgement→resolution. |
| 2F-2 | Alert thresholds | New: `services/alerts/thresholds.py` | Configurable thresholds: depth, rate of increase, affected population, critical infrastructure, road disruption, rainfall forecast, confidence. |
| 2F-3 | Decision support engine | New: `services/decision/recommendations.py` | Produces actionable recommendations: WHY + WHAT IS AFFECTED + WHAT SHOULD BE DONE + WHERE + HOW URGENTLY. References actual model outputs. |
| 2F-4 | Decision API | New: `services/api/routers/decisions.py` | `/api/v1/decisions/current`, `/api/v1/decisions/recommendations`. |
| 2F-5 | Alert integration in nowcast | Modify: pipeline | After each nowcast cycle, alert engine evaluates thresholds. |

**Tests required:**
- Alert generated when depth threshold crossed
- Duplicate alert NOT created for same ongoing event
- Recommendations reference actual model outputs with evidence

---

### PHASE 2G — AI Assistant

**Goal:** LLM-grounded assistant using system data.

| Task ID | Task | Files to Change | Definition of Done |
|---------|------|-----------------|-------------------|
| 2G-1 | Integrate AIOperator with router | `services/api/routers/ai.py`, `services/ai/operator.py` | Chat queries go through `AIOperator` tool-calling instead of keyword matching. |
| 2G-2 | Expand tool registry | `services/ai/operator.py` | Add tools: ward_risk, nowcast_latest, alerts_active, shelters_nearest, drainage_status, historical_events, impact_summary, decision_recommendations. |
| 2G-3 | LLM integration | `services/ai/operator.py` | Gemini API function-calling for intent detection and response formatting. |
| 2G-4 | Response grounding | `services/ai/operator.py` | Every response cites data source, timestamp, confidence. Never fabricates. |

**Tests required:**
- "Which wards are at highest risk?" returns data from `/ward-risk`
- Unknown questions receive honest "I don't have that data"
- Never fabricates flood depth values

---

### PHASE 2H — Workflows (Municipal / Field / Citizen)

**Goal:** Connected workflows across three user interfaces.

| Task ID | Task | Files to Change | Definition of Done |
|---------|------|-----------------|-------------------|
| 2H-1 | Municipal dashboard integration | `apps/city-dashboard/` | All 20 command center features connected to live backend. Map changes when simulation runs. |
| 2H-2 | Field worker backend | New: `services/api/routers/field_ops.py`, new DB model `FieldTask` | Task assignment, inspection checklist, photo upload, status update. |
| 2H-3 | Field worker frontend | New page/component in citizen-web or separate app | Mobile-first task interface: assigned incident, location, priority, water depth, actions. |
| 2H-4 | Citizen dashboard completion | `apps/citizen-web/` | Current risk, shelters, alerts, report flooding, AI assistant — all from live backend. |
| 2H-5 | Report verification pipeline | New: `services/data/report_verification.py` | Classify: UNVERIFIED→SUPPORTED→LIKELY→CONFLICTING→RESOLVED. Cross-check vs model prediction and nearby reports. |

**Tests required:**
- Field worker update appears in command center
- Citizen report creates PostGIS record
- Map actually changes when simulation runs
- Report verification classifies correctly

---

### PHASE 2I — Security, Monitoring, Deployment

**Goal:** Production-ready operational infrastructure.

| Task ID | Task | Files to Change | Definition of Done |
|---------|------|-----------------|-------------------|
| 2I-1 | JWT authentication | New: `services/api/auth.py` | Roles: admin, municipal, field_worker, citizen. Protected endpoints. |
| 2I-2 | Rate limiting | Modify: `services/api/main.py` | Per-endpoint rate limits using slowapi or custom middleware. |
| 2I-3 | Prometheus metrics | New: metrics middleware | `/metrics` endpoint for Grafana. |
| 2I-4 | CI/CD | New: `.github/workflows/ci.yml` | lint → typecheck → test → build → deploy validation. |
| 2I-5 | Docker Compose | New: `docker-compose.yml` | api + scheduler + postgres + frontend containers. |
| 2I-6 | Alembic in CI/CD | Modify: CI workflow | `alembic upgrade head` as part of deployment. |

---

## 5. Testing Strategy

### Unit Tests (per phase)
- Each phase adds tests in `tests/unit/` and/or `tests/integration/`
- Physics regression: existing `test_physics.py` must continue to pass after every change
- New tests verify actual behavior, not just that code runs

### Integration Tests
- End-to-end nowcast: weather → flood → risk → alert → persist
- Historical replay: must produce same validated July 2024 result

### Regression Guard
- Physics engine mass balance must remain < 1%
- All 9 existing formal test files must pass after every phase
- July 2024 replay result must not regress

---

## 6. Deployment Strategy

### Development (Current)
```bash
uvicorn services.api.main:app --reload --host 0.0.0.0 --port 8000
cd apps/city-dashboard && npm run dev  # port 3001
cd apps/citizen-web && npm run dev     # port 3000
```

### Production Target
```yaml
# docker-compose.yml
services:
  api:
    build: .
    command: uvicorn services.api.main:app --workers 4 --host 0.0.0.0 --port 8000
  scheduler:
    build: .
    command: python -m services.scheduler.nowcast_scheduler
  postgres:
    image: postgis/postgis:16-3.4
  dashboard:
    build: apps/city-dashboard
  citizen:
    build: apps/citizen-web
```

### Migration Path
1. Alembic initialized (Phase 2A)
2. Docker Compose created (Phase 2I)
3. GitHub Actions CI (Phase 2I)

---

## 7. Demonstration Scenario (Phase 2 Exit Criteria)

At the end of Phase 2, the following must work end-to-end:

1. System auto-fetches live rainfall (Open-Meteo + IMERG + MOSDAC)
2. QC pipeline flags bad observations
3. Fusion engine blends sources
4. Nowcast pipeline runs every 15 minutes
5. 2D flood model produces depth grid on real DEM
6. ML surrogate produces fast prediction
7. Confidence score explains reliability
8. Ward risk scores update dynamically
9. Affected population/roads/infrastructure calculated
10. Alert generated when threshold crossed
11. Decision recommendations produced
12. Command center shows live flood map
13. Citizen app shows current risk + shelters + AI assistant
14. Field worker receives task assignment
15. Citizen reports submitted and cross-checked
16. Historical replay validates against observed events
17. All state persists across restarts

---

## 8. Progress Tracking

File: `docs/PHASE_2_PROGRESS.md`

For each feature:
- Status: `DONE` | `IN_PROGRESS` | `BLOCKED` | `NOT_STARTED`
- Files changed
- APIs added
- Database changes
- Tests added
- Verification result

---

## 9. Immediate Next Step

**Begin PHASE 2A — Task 2A-1: Initialize Alembic**

Then: 2A-2 → 2A-3 → 2A-4 → ... → 2A-13 (sequential)

Do NOT proceed to Phase 2B until all Phase 2A tasks pass tests and the API server starts cleanly.

---

## 10. Rules (Repeated for Clarity)

1. DO NOT rebuild existing working systems.
2. DO NOT replace the physics engine.
3. DO NOT create parallel implementations.
4. DO NOT fake functionality for UI purposes.
5. DO NOT use fake data where real data already exists.
6. DO NOT use `create_all` as production migration strategy.
7. DO NOT silently delete bad observations — flag them.
8. DO NOT silently pretend a failed provider worked.
9. DO NOT claim ML accuracy before actual validation.
10. DO NOT expose fake confidence percentages.
11. DO NOT implement 20 features and only test at the end.
12. After every phase: IMPLEMENT → TEST → RUN → VERIFY → FIX → DOCUMENT → COMMIT.
