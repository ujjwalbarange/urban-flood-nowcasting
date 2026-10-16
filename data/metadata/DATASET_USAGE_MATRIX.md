# MUFNS Dataset Usage Matrix
**Generated:** September 26, 2026  
**Source:** `dataset_registry` table (29 registered datasets)

---

## Purpose

Every dataset in the system must have a defined downstream purpose. No dataset should be silently unused. This matrix traces:

**Dataset → Used By → Processing Step → Output**

---

## Rainfall Forcing Chain

```
INSAT-3DR HEM (644 granules)  ──┐
INSAT-3DR IMC (429 granules)  ──┤
GPM IMERG (576 records)       ──┼──► RAINFALL FUSION ENGINE ──► Rainfall Forcing Grid
AWS Gauges (27 records)       ──┤    (6 modes: HEM_ONLY, IMC_ONLY, GPM_ONLY,
NWP Forecasts (30,240)       ──┘     GPM_HEM, GPM_IMC, FULL_FUSION)
                                          │
                                          ▼
                                   RAINFALL VALIDATION
                                   (bias, MAE, RMSE, correlation)
```

## Hydrological / Runoff Chain

```
Rainfall Forcing Grid  ──────────────┐
Copernicus GLO-30 DEM (1 tile)  ─────┤
  └─ Terrain Derivatives (6 types) ──┤
LULC (69 classes)  ──────────────────┼──► HYDROLOGICAL MODEL
Impervious Surface (128 cells) ──────┤    (Horton infiltration + SCS-CN)
                                     │         │
                                     │         ▼
                                     │    RUNOFF EXCESS GRID
                                     │         │
                                     └─────────▼
                                        2D DIFFUSIVE WAVE SOLVER
                                        (surface flow routing)
```

## Drainage / Coupling Chain

```
Primary Drainage Network (39)  ──┐
Drainage Structures (41)       ──┤
Drainage Nodes (35)           ──┼──► SURFACE-DRAINAGE COUPLING
Drainage Links (8)            ──┤    (signed orifice exchange)
Pumping Stations (8)          ──┤         │
Water Bodies (1,730)          ──┘         ▼
                                    COUPLED FLOOD DEPTH GRID
```

## Coastal / Tidal Chain

```
Tide Observations (72)  ──────► COASTAL BOUNDARY CONDITION
Coastal Exposure Zones (15) ──► Spatial risk overlay              
                                     │
                                     ▼
                              COMPOUND FLOOD SCENARIOS
                              (rain only, rain+tide, rain+high tide)
```

## Flood Output Chain

```
COUPLED FLOOD DEPTH GRID  ──► Flood Extent
                           ──► Water Depth Map
                           ──► Flow Velocity
                           ──► Inundation Duration
                           ──► Time-to-Inundation
```

## Exposure / Impact Chain

```
Flood Depth Grid  ───────────────────┐
Road Segments (14,563)  ─────────────┤
Buildings (30,000)  ─────────────────┤
Population Grids (1,242)  ───────────┼──► SPATIAL EXPOSURE OVERLAY
Critical Infrastructure (2,002)  ────┤    (PostGIS ST_Intersects)
Hospitals (1,667)  ──────────────────┤         │
Railway Stations (167)  ─────────────┤         ▼
Bridges/Culverts (33)  ──────────────┤    IMPACT ASSESSMENT
Critical Arterial Corridors (78)  ───┤    - Affected roads (km)
Shelters (10)  ──────────────────────┤    - Affected buildings (count)
Low-Lying Areas (15)  ───────────────┤    - Affected population
Green/Open Spaces (25)  ─────────────┘    - Affected infrastructure
                                          - Ward-level risk scores
```

## Validation Chain

```
Flood Simulation Output  ──────────┐
Historical Flood Events (209)  ────┼──► VALIDATION ENGINE
Flood Hotspots (35)  ──────────────┤    - Hotspot hit rate
Legacy Hotspots (10)  ─────────────┘    - Precision / Recall
                                        - Timing error
                                        - Depth error (where available)
```

## Administrative / Aggregation

```
Wards (24)  ──► Spatial aggregation unit for all outputs
Cities (1)  ──► System configuration
```

---

## Detailed Dataset-to-Pipeline Mapping

| Dataset | DB Table | Pipeline Stage | Processing Step | Output |
|---------|----------|---------------|-----------------|--------|
| INSAT HEM | `satellite_rainfall_observations` | Rainfall Fusion | Satellite rain input | Fused rainfall field |
| INSAT IMC | `satellite_rainfall_observations` | Rainfall Fusion | Validation/secondary rain | Fused rainfall field |
| GPM IMERG | `rainfall_satellite` | Rainfall Fusion | Satellite rain input | Fused rainfall field |
| AWS Gauges | `rainfall_observations` | Rainfall Fusion | Ground calibration | Fused rainfall + validation |
| NWP Forecasts | `weather_forecasts` | Nowcast Forcing | Future rain prediction | Real-time rainfall forcing |
| Weather Obs | `weather_observations` | Context | Atmospheric state | Model initialization |
| DEM | `dem_tiles` + file | Terrain Loading | DEM → conditioned DEM | Elevation grid for routing |
| Derivatives | `terrain_derivatives` | Feature Gen | Slope/flow/TWI | Catchments, flow paths |
| LULC | `land_use_land_cover` | Runoff Params | LULC → Manning's n, CN | Roughness + infiltration grids |
| Imperviousness | `impervious_surface_grid` | Infiltration | Imp. fraction → Horton scaling | Infiltration reduction |
| Primary Drainage | `primary_drainage_network` | Coupling | Channel routing | Surface-drain exchange |
| Drainage Structures | `drainage_structures` | Coupling | Outfall/gate mapping | Boundary conditions |
| Drainage Nodes | `drainage_nodes` | Coupling | Coupling point mapping | Orifice exchange points |
| Pumping Stations | `pumping_stations` | Coupling | Pump capacity | Outflow capacity |
| Water Bodies | `water_bodies` | Hydrology | Network topology | Flow routing guidance |
| Tide | `tide_observations` | Coastal BC | Tidal boundary | Downstream water level |
| Historical Events | `historical_flood_events` | Validation | Observed floods | Validation reference |
| Hotspots | `flood_hotspots` | Validation | Known flood locations | Hotspot hit rate |
| Roads | `road_segments` | Exposure | Flood × roads | Affected road length |
| Buildings | `buildings` | Exposure | Flood × buildings | Affected building count |
| Population | `population_grids` | Exposure | Flood × population | Affected population |
| Infrastructure | `critical_infrastructure` + subtables | Exposure | Flood × infra | At-risk facilities |
| Wards | `wards` | Aggregation | Spatial grouping | Ward-level reporting |
| Bridges | `bridges_and_culverts` | Exposure | Flood × bridges | Vulnerable crossings |
| Low-Lying Areas | `low_lying_areas` | Risk | Depression overlay | High-risk zones |
| Coastal Zones | `coastal_exposure_zones` | Risk | Coastal overlay | Tidal risk zones |
| Shelters | `shelters` | Response | Nearest shelter | Evacuation routing |
| Green Spaces | `green_open_spaces` | Land Surface | Pervious areas | Infiltration zones |
| Arterial Corridors | `critical_arterial_corridors` | Exposure | Priority roads | Traffic disruption |

---

## Currently Unused Datasets: NONE

All 29 registered datasets have a defined downstream purpose in the pipeline.
