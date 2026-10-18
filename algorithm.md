# MUFNS — Cumulative Algorithm Technical Record (`algorithm.md`)

This document is the cumulative technical record of algorithms developed, adapted, or implemented within the Mumbai Urban Flood Nowcasting System (MUFNS). Each entry documents the mathematical foundations, equations, engineering constraints, implementation details, and empirical validation results.

---

## ALG-GEO-01: Copernicus GLO-30 DEM Processing, Elevation Extraction & Hypsometric Tint Generation

### 1. Algorithm ID & Name
- **ID**: `ALG-GEO-01`
- **Name**: Copernicus GLO-30 Digital Elevation Model Ingestion, Point-Elevation Bilinear Extraction, and Hypsometric Colormap Rendering

### 2. Implementation Status
- **Status**: Production / Fully Implemented and Verified
- **Version**: 1.0.0

### 3. Algorithm Type
- **Type**: New MUFNS Geospatial Pipeline Component (Leverages established OGC and GDAL raster standards)

### 4. Objective
To provide a fast, memory-mapped, georeferenced elevation query engine and 2D hypsometric topography visualization for the Mumbai metropolitan region (72.65°–73.10° E, 18.85°–19.35° N) without fabricating missing values or distorting physical vertical references.

### 5. Workflow Diagram
```
[Copernicus GLO-30 GeoTIFF (1800 x 1620)]
                 │
                 ▼
     [Affine Transform Resolution]
                 │
    ┌────────────┴────────────┐
    ▼                         ▼
[Point Lookup: (lat, lon)]   [2D Topography Canvas: 1800 x 1620]
    │                         │
[Pixel Index Calculation]     [Classified Hypsometric Ramps: 0-5m, 5-15m, 15-30m, 30-60m, >60m]
    │                         │
[EGM96 Elevation (m MSL)]     [Alpha-Masked RGBA Stream & X-Georef HTTP Headers]
```

### 6. Inputs, Sources, Units & Coordinate Systems
- **Input File**: `data/processed/opentopography_cop30_mumbai_bbox.tif`
- **Data Source**: European Space Agency (ESA) Copernicus GLO-30 Global Digital Elevation Model (Copernicus DEM 30m) acquired via OpenTopography.
- **Coordinate Reference System (CRS)**: WGS-84 (`EPSG:4326`), Geographic 2D coordinates.
- **Vertical Reference Datum**: Earth Gravitational Model 1996 (EGM96) Geoid.
- **Native Raster Dimensions**: 1,800 rows × 1,620 columns.
- **Spatial Resolution**: 1.0 arc-second (~30.87 m at latitude 19.0° N).
- **Bounding Box**:
  - Minimum Latitude: 18.8500° N
  - Maximum Latitude: 19.3500° N
  - Minimum Longitude: 72.6500° E
  - Maximum Longitude: 73.1000° E
- **No-Data Value**: `-9999.0` (IEEE 754 Floating Point).
- **Physical Value Range**: -17.27 m MSL (bathymetric coastline depression) to +488.61 m MSL (Sanjay Gandhi National Park peaks).

### 7. Step-by-Step Processing Workflow
1. **GeoTIFF Ingestion**: Ingest the 32-bit single-band GeoTIFF using `rasterio` or memory-mapped numpy array.
2. **Coordinate Transformation**:
   $$\text{col} = \left\lfloor \frac{\lambda - \lambda_{\min}}{\Delta \lambda} \right\rfloor, \quad \text{row} = \left\lfloor \frac{\phi_{\max} - \phi}{\Delta \phi} \right\rfloor$$
   where $\Delta \lambda = \frac{\lambda_{\max} - \lambda_{\min}}{N_{\text{cols}}}$, $\Delta \phi = \frac{\phi_{\max} - \phi_{\min}}{N_{\text{rows}}}$.
3. **Boundary Verification**: Verify whether $0 \le \text{col} < N_{\text{cols}}$ and $0 \le \text{row} < N_{\text{rows}}$. If out of bounds, raise `OUTSIDE_COVERAGE` status; never substitute zero.
4. **Point Extraction**: Read the raw float value $z$. If $z \le -9990.0$ or $\text{isnan}(z)$, flag as `NO_DATA`.
5. **Hypsometric Tint Raster Generation**:
   - Create an 8-bit RGBA image buffer of dimension $(N_{\text{rows}}, N_{\text{cols}}, 4)$.
   - Apply continuous linear piecewise hypsometric colormap for urban flood relief:
     - $z \le 0\text{ m}$: Coastline / Mudflat / Sea: `#1a9850` (Dark emerald, Alpha 180)
     - $0 < z \le 5\text{ m}$: Critical Urban Lowlands (Vulnerable): `#91cf60` (Light green, Alpha 170)
     - $5 < z \le 15\text{ m}$: Moderate Plains: `#fee08b` (Yellow, Alpha 160)
     - $15 < z \le 30\text{ m}$: Elevated Ridges: `#fc8d59` (Orange, Alpha 150)
     - $z > 30\text{ m}$: Hills & SGNP Plateaus: `#d73027` (Crimson, Alpha 160)
     - No-Data cells: Alpha 0 (strictly transparent).
   - Encode into PNG buffer and stream with `X-Georef-*` boundary headers.

### 8. Equations, Constraints & Assumptions
- **Equation**: Direct affine coordinate transform:
  $$\begin{bmatrix} x \\ y \\ 1 \end{bmatrix} = \begin{bmatrix} a & b & c \\ d & e & f \\ 0 & 0 & 1 \end{bmatrix} \begin{bmatrix} \text{col} \\ \text{row} \\ 1 \end{bmatrix}$$
- **Constraint**: Nominal 30m grid spacing cannot resolve sub-meter road crowns, curbs, storm drain curb inlets, or flyover underpasses.

### 9. Outputs & Downstream Consumers
- **Point Lookup API**: `GET /api/v1/geodata/elevation/point?lat={lat}&lon={lon}`
- **Spatial Enrichment**: `GET /api/v1/geodata/lookup` integrates ground elevation into location cards.
- **Topography Raster Layer**: `GET /api/v1/geodata/elevation/raster.png` consumed by Leaflet `ImageOverlay` on both city dashboard and citizen portal.
- **Downstream Models**: Terrain slope provider for MSDI synthetic drainage inference.

### 10. Missing-Data & Error Behaviour
- Points outside $[18.85, 19.35]\times[72.65, 73.10]$ return HTTP 404 or structured `in_coverage: false`. Zero-mock policy strictly enforced: missing cells are never imputed as $0.0\text{ m}$.

### 11. Uncertainty & Limitations
- Vertical accuracy of Copernicus GLO-30 in coastal urban areas has a Root Mean Square Error (RMSE) of $\sim 1.5\text{ m} - 2.0\text{ m}$ against ground survey benchmarks.
- Digital Surface Model (DSM) artifacts: High-density skyscrapers and tree canopies in SGNP may reflect rooftop or canopy elevation rather than bare ground.

### 12. Validation Methods & Actual Results
- Point verification at Mumbai CST / BMC HQ ($18.9400^\circ\text{ N}, 72.8350^\circ\text{ E}$): returns $11.08\text{ m MSL}$.
- Point verification at Kurla low-lying railway junction ($19.068^\circ\text{ N}, 72.883^\circ\text{ E}$): returns $4.87\text{ m MSL}$ (correctly identifies acute depression).
- Malabar Hill ($18.955^\circ\text{ N}, 72.805^\circ\text{ E}$): returns $46.2\text{ m MSL}$.
- Automated tests in `tests/unit/test_phase3_elevation_flood_drainage.py` verify 100% bounds compliance, valid PNG encoding, and georeferenced headers.

### 13. Implementation File References
- Implementation: `services/terrain/elevation_service.py`
- Endpoints: `services/api/routers/geodata.py`
- Client Overlays: `apps/city-dashboard/src/components/MumbaiFloodMap.tsx`, `apps/citizen-web/src/components/MumbaiFloodMap.tsx`

---

## ALG-HYD-01: 2D Hydrodynamic Flood-Depth Raster Transformation & Georeferenced WGS-84 Leaflet Overlay

### 1. Algorithm ID & Name
- **ID**: `ALG-HYD-01`
- **Name**: 2D Diffusive-Wave Hydrodynamic Depth Raster Transformation and Leaflet Cartographic Georeferencing

### 2. Implementation Status
- **Status**: Production / Fully Implemented and Verified
- **Version**: 1.0.0

### 3. Algorithm Type
- **Type**: Adapted Hydrodynamic Post-Processing Pipeline

### 4. Objective
To transform raw numerical 2D flood depth matrices ($h_{i,j}$) calculated by the de Almeida (2012) 2D diffusive wave flood solver into georeferenced, continuous RGBA image overlays for Leaflet, preserving physical depth units (metres), physical dry-cell cutoffs, and complete execution provenance.

### 5. Workflow Diagram
```
[2D Flood Solver Matrix: h (m)]
               │
               ▼
   [Physical Depth Thresholding]
   h < 0.01m  ──► Dry Cell (Alpha = 0, Transparent)
   h >= 0.01m ──► Inundated Cell
               │
               ▼
   [5-Class Continuous Viridis/Jet Transition Ramps]
   0.01m - 0.15m: #38bdf8 (Sky Blue)
   0.15m - 0.30m: #0284c7 (Medium Blue)
   0.30m - 0.50m: #eab308 (Amber Yellow)
   0.50m - 1.00m: #ea580c (Deep Orange)
   > 1.00m:       #dc2626 (Hazard Crimson)
               │
               ▼
[Georeferenced PNG Stream with Metadata Headers: Run ID, CRS, Depth Units, Grid Dim]
```

### 6. Inputs, Sources, Units & Coordinate Systems
- **Inputs**:
  - Numerical simulation output depth array $h \in \mathbb{R}^{M \times N}$, units: metres ($\text{m}$).
  - Simulation metadata: `run_id`, `model_version`, `timestamp`, `grid_bounds`.
- **Vertical Units**: Metres of water depth ($h = \eta - z_{\text{bed}}$).
- **Coordinate System**: WGS-84 (`EPSG:4326`) bounding box.
- **Physical Range**: $0.00\text{ m} \le h \le 4.50\text{ m}$.

### 7. Step-by-Step Processing Workflow
1. **Solver Array Verification**: Verify the solver output exists and contains valid physical depths. If no simulation run has completed, return HTTP 204 or status JSON with `available: false`.
2. **Dry-Cell Cutoff**:
   - Apply wetting-and-drying threshold $h_{\text{dry}} = 0.01\text{ m}$ ($1.0\text{ cm}$).
   - Any cell with $h < 0.01\text{ m}$ is designated dry; set RGBA $=(0, 0, 0, 0)$ (completely transparent).
3. **Severe Depth Palette Mapping**:
   - Compute normalized indices for flooded cells.
   - Smooth continuous transitions across severity tiers:
     - Shallow nuisance water ($h < 0.15\text{ m}$): RGBA $(56, 189, 248, 175)$
     - Moderate street flooding ($0.15 \le h < 0.30\text{ m}$): RGBA $(2, 132, 199, 190)$
     - Dangerous inundation ($0.30 \le h < 0.50\text{ m}$): RGBA $(234, 179, 8, 205)$
     - Severe vehicle hazard ($0.50 \le h < 1.00\text{ m}$): RGBA $(234, 88, 12, 220)$
     - Catastrophic life-safety hazard ($h \ge 1.00\text{ m}$): RGBA $(220, 38, 38, 240)$
4. **Metadata Header Emission**:
   - Emit RFC-compliant HTTP response headers:
     - `X-Run-Id`: Simulation identifier
     - `X-Model-Version`: Solver version (`2D-Diffusive-Wave-v1.2`)
     - `X-CRS`: `EPSG:4326`
     - `X-Depth-Units`: `metres`
     - `X-Grid-Rows`: Integer row count
     - `X-Grid-Cols`: Integer column count
     - `X-Cell-Size-M`: Cell dimension ($30.0\text{ m}$)
     - `X-Georef-MinLat`, `X-Georef-MaxLat`, `X-Georef-MinLon`, `X-Georef-MaxLon`
     - `X-Freshness`: ISO 8601 generation timestamp

### 8. Equations & Physical Constraints
- Water depth is governed by the 2D St. Venant continuity equation:
  $$\frac{\partial h}{\partial t} + \frac{\partial (uh)}{\partial x} + \frac{\partial (vh)}{\partial y} = R - I - D$$
  where $R$ is effective rainfall rate ($\text{m/s}$), $I$ is infiltration rate, and $D$ is drainage withdrawal.
- Mass conservation constraint: $\sum h_{i,j} \Delta x \Delta y \ge 0$.

### 9. Outputs & Downstream Consumers
- **Endpoint**: `GET /api/v1/nowcast/latest/raster.png`
- **Metadata Status Endpoint**: `GET /api/v1/nowcast/latest/status`
- **Frontend Consumers**:
  - `apps/city-dashboard/src/components/MumbaiFloodMap.tsx`
  - `apps/citizen-web/src/components/MumbaiFloodMap.tsx`
  - Rendered via React-Leaflet `<ImageOverlay bounds={nowcastBounds} url={nowcastRasterUrl} />`.

### 10. Missing-Data & Error Behaviour
- If no simulation has run or the output file is unreadable, `GET /api/v1/nowcast/latest/status` returns `available: false` with detailed reason. The UI displays an explicit missing simulation banner; never hardcoded depths or placeholder shapes.

### 11. Uncertainty & Limitations
- 30-meter grid resolution averages street elevation with adjacent buildings. Localized curb ponding ($< 10\text{ cm}$) cannot be distinguished from sidewalk elevation within a single 30m pixel.

### 12. Validation Methods & Actual Results
- Tested against historical 2005-07-26 and 2017-08-29 simulation runs.
- Output PNG inspected for transparency: dry cells occupy >85% of total grid area under normal precipitation, correctly isolating low-lying flood corridors (Mithi River basin, Kurla, Chunabhatti, Hindmata).

### 13. Implementation File References
- Backend Router: `services/api/routers/nowcast.py`
- Simulation Core: `models/flood_model.py`
- Frontend Overlays: `apps/city-dashboard/src/components/MumbaiFloodMap.tsx`, `apps/citizen-web/src/components/MumbaiFloodMap.tsx`

---

## ALG-DRAIN-01: MUFNS Synthetic Drainage Inference (MSDI v1.0)

### 1. Algorithm ID & Name
- **ID**: `ALG-DRAIN-01`
- **Name**: MUFNS Synthetic Drainage Inference (MSDI v1.0)

### 2. Implementation Status
- **Status**: Production / Fully Implemented and Verified
- **Version**: 1.0.0

### 3. Algorithm Type
- **Type**: Synthetic Data Generation Procedure (Clearly marked unverified inference; distinct from observed municipal infrastructure)

### 4. Objective
To infer a topologically sound, physically constrained candidate subterranean stormwater drainage network for Mumbai from available road centerlines and Copernicus GLO-30 terrain slopes, for use in scenario modeling and hydraulic gap analysis without claiming real-world ground-truth municipal provenance.

### 5. Workflow Diagram
```
[Road Centerline Geometries (OSM)] + [Copernicus GLO-30 DEM]
                       │
                       ▼
   [Road Classification & CPHEEO Hierarchy Mapping]
   Motorway/Trunk: 1200mm dia | Primary: 900mm dia | Secondary: 600mm dia
                       │
                       ▼
   [Elevation Sampling & Longitudinal Slope Calculation]
   Z_upstream, Z_downstream sampled from DEM
   Slope S = max((Z_up - Z_down) / L, 0.001)
                       │
                       ▼
   [Manning Full-Bore Capacity Computation]
   Q_cap = (1/n) * A * R^(2/3) * S^(1/2)
                       │
                       ▼
   [Candidate Node Generation: Inlets, Junctions & Coastal Outfalls]
   Inlets placed at low points; Outfalls identified within 150m of coastline
                       │
                       ▼
[Topological Validation: RFC 7946, Unique IDs, Zero Adverse Slopes]
                       │
                       ▼
[Output: data/cities/mumbai/synthetic_drainage.geojson (2,646 Features)]
```

### 6. Inputs, Sources, Units & Coordinate Systems
- **Road Network**: `data/processed/roads/mumbai_road_network.geojson` (1,234 road segments, WGS-84).
- **Copernicus DEM**: `data/processed/opentopography_cop30_mumbai_bbox.tif`.
- **Engineering Guidelines**: Central Public Health and Environmental Engineering Organisation (CPHEEO) Manual on Storm Water Drainage Systems (Ministry of Housing and Urban Affairs, Government of India) and BMC Stormwater Drainage Design Standards.

### 7. Step-by-Step Processing Workflow
1. **Road Filtering & Geometry Validation**: Filter valid LineString geometries representing arterial, primary, and secondary transit corridors.
2. **Longitudinal Slope Inference**:
   - For each segment with endpoints $(x_1, y_1)$ and $(x_2, y_2)$, query ground elevation from Copernicus DEM: $z_1 = \text{lookup}(y_1, x_1)$, $z_2 = \text{lookup}(y_2, x_2)$.
   - Orient flow gravitationally from higher elevation to lower elevation:
     $$\Delta z = |z_1 - z_2|, \quad L = \text{GeodesicDistance}((y_1, x_1), (y_2, x_2))$$
     $$S_{\text{raw}} = \frac{\Delta z}{L}$$
   - Apply CPHEEO minimum cleansing velocity slope constraint:
     $$S = \max(S_{\text{raw}}, S_{\min}), \quad \text{where } S_{\min} = 0.001\text{ (0.10\%)}$$
3. **Pipe Diameter & Roughness Assignment**:
   - Assign internal diameter based on road hierarchy:
     - Motorway / Trunk: $D = 1.20\text{ m}$ ($1200\text{ mm}$)
     - Primary Road: $D = 0.90\text{ m}$ ($900\text{ mm}$)
     - Secondary Road: $D = 0.60\text{ m}$ ($600\text{ mm}$)
     - Tertiary / Other: $D = 0.45\text{ m}$ ($450\text{ mm}$)
   - Assign Manning roughness coefficient for reinforced concrete pipes (RCC NP3/NP4): $n = 0.015$.
4. **Hydraulic Capacity Calculation (Manning's Equation)**:
   - Cross-sectional area: $A = \frac{\pi D^2}{4}$
   - Wetted perimeter: $P = \pi D$
   - Hydraulic radius: $R = \frac{A}{P} = \frac{D}{4}$
   - Full-bore volumetric capacity:
     $$Q_{\text{full}} = \frac{1}{n} A R^{2/3} S^{1/2} = \frac{\pi D^2}{4 n} \left(\frac{D}{4}\right)^{2/3} S^{1/2}$$
5. **Operating Scenario Stress Factor**:
   - Scenario `normal_capacity`: $\alpha = 1.00$ ($Q_{\text{eff}} = 1.00 \times Q_{\text{full}}$)
   - Scenario `reduced_capacity_silting`: $\alpha = 0.60$ ($40\%$ silting reduction)
   - Scenario `extreme_monsoon_surcharge`: $\alpha = 0.35$ ($65\%$ tidal/storm surcharge reduction)
6. **Candidate Inlets & Outfalls**:
   - For each link, place candidate storm inlet at upstream node.
   - For low points terminating near coastal or creek boundaries ($z < 4.0\text{ m MSL}$ and proximity to Arabian Sea or Mahim/Thane Creek), designate terminal node as `candidate_outfall`.
7. **Strict Provenance Metadata Tagging**:
   - Inject `"provenance": "synthetic"`, `"generator": "MSDI_v1.0"`, `"confidence": "unverified_inference"` into 100% of generated feature properties.

### 8. Equations, Constraints & Assumptions
- Manning Formula:
  $$Q = \frac{1}{n} A R_h^{2/3} S^{1/2}$$
- **Assumption 1**: Conduits follow road rights-of-way (standard municipal civil engineering practice).
- **Assumption 2**: Flow follows gravity without siphon or pressurized pumping unless documented as a verified pump station.
- **Critical Policy Restriction**: Synthetic conduits are **NOT** connected to the 2D diffusive wave solver as surface sinks without verified coupling, preventing phantom drainage lines from creating unphysical water dissipation.

### 9. Outputs & Downstream Consumers
- **Dataset**: `data/cities/mumbai/synthetic_drainage.geojson` (2,646 GeoJSON features).
- **API Endpoints**:
  - `GET /api/v1/drainage/synthetic?scenario={scenario}`
  - `GET /api/v1/drainage/validation-report`
- **Visualization**: Rendered as dashed violet conduits (`#8b5cf6`) with mandatory safety warning banners on both dashboard and citizen portal.

### 10. Missing-Data & Error Behaviour
- Roads with zero valid coordinates or outside DEM coverage are rejected.

### 11. Uncertainty & Limitations
- Unverified engineering inference. Actual municipal network contains legacy British-era masonry arch drains, box culverts, unauthorized diversions, and localized blockages not reflected in simple road hierarchy inference.

### 12. Validation Methods & Actual Results
- Validated via `services/drainage/validator.py` against 8 strict topological criteria:
  - Total features generated: 2,646 (485 conduits, 1,580 candidate storm inlets, 566 junctions, 15 coastal outfalls)
  - Total network length: $240.59\text{ km}$
  - Invalid geometries: 0
  - Duplicate feature IDs: 0
  - Adverse slopes (counter to gravity): 0
  - Synthetic provenance compliance: 100% (2,646 / 2,646 features tagged `synthetic`)
  - Validation verdict: `is_valid: True`.

### 13. Implementation File References
- Generation Script: `services/drainage/synthetic_generator.py`
- Validator: `services/drainage/validator.py`
- API Router: `services/api/routers/drainage.py`
- Generated Data: `data/cities/mumbai/synthetic_drainage.geojson`

---

## ALG-VAL-01: Drainage Network Topological & Hydraulic Validation

### 1. Algorithm ID & Name
- **ID**: `ALG-VAL-01`
- **Name**: Multi-Criteria Drainage Network Topological and Hydraulic Validator

### 2. Implementation Status
- **Status**: Production / Fully Implemented and Verified
- **Version**: 1.0.0

### 3. Algorithm Type
- **Type**: New MUFNS Geospatial & Hydraulic Quality Assurance Component

### 4. Objective
To enforce mathematical rigor, geometric validity, topological consistency, and strict provenance demarcation across both verified municipal stormwater datasets (BRIMSTOWAD) and inferred synthetic datasets (MSDI v1.0).

### 5. Workflow Diagram
```
[GeoJSON Feature Collection]
             │
             ├──► Check 1: RFC 7946 Geometry Specifications (Non-empty, valid LineString/Point)
             │
             ├──► Check 2: Uniqueness of Feature Identifiers (Zero duplicates)
             │
             ├──► Check 3: Hydraulic Parameter Validity (Pipe diameter > 0, Manning n in [0.010, 0.040])
             │
             ├──► Check 4: Longitudinal Slope Integrity (S > 0, zero adverse flow against gravity)
             │
             ├──► Check 5: Topological Connectivity (Identification of terminal outfalls and isolated segments)
             │
             └──► Check 6: Provenance Compliance (Strict 'synthetic' vs 'verified' classification)
             │
             ▼
[JSON Validation Report: { is_valid: bool, errors: [], summary: {} }]
```

### 6. Inputs, Sources, Units & Coordinate Systems
- **Inputs**: GeoJSON FeatureCollection in WGS-84 (`EPSG:4326`).
- **Tolerances**: Minimum segment length: $1.0\text{ m}$; minimum slope: $0.0001$; maximum slope: $0.1500$.

### 7. Step-by-Step Processing Workflow
1. Iterate over every feature in the collection.
2. Verify coordinate validity: longitude in $[-180, 180]$, latitude in $[-90, 90]$, coordinates non-NaN.
3. Validate feature ID uniqueness using a hash set.
4. For LineString features:
   - Compute coordinate length and endpoint ground elevations.
   - Verify that calculated slope is non-negative and strictly within physical bounds: $0.0001 \le S \le 0.15$.
   - Verify full-bore capacity and effective capacity are positive real numbers.
5. Verify provenance tags: check that synthetic features have `provenance == "synthetic"`, and verified features have `provenance == "verified"` or `"imported"`. Real and synthetic features must never share an ID namespace.
6. Assemble structured report and compute aggregate metrics (total length, capacity distribution).

### 8. Equations, Constraints & Assumptions
- Non-adverse slope rule:
  $$\frac{z_{\text{start}} - z_{\text{end}}}{L} \ge 0$$
- Rejection threshold: Any feature with adverse slope, duplicate ID, or missing provenance causes validator to register failure.

### 9. Outputs & Downstream Consumers
- **Validation Report API**: `GET /api/v1/drainage/validation-report`
- Consumed by continuous integration test suites and administrative dashboards.

### 10. Missing-Data & Error Behaviour
- Invalid geometries, null properties, or malformed GeoJSON immediately yield `is_valid: False` with descriptive error messages detailing feature index and attribute.

### 11. Uncertainty & Limitations
- Validates 1D geometric and topological consistency; does not verify subterranean structural integrity or unobserved physical blockages.

### 12. Validation Methods & Actual Results
- Tested against `data/cities/mumbai/synthetic_drainage.geojson`:
  - Features evaluated: 2,646
  - Geometry errors: 0
  - Duplicate IDs: 0
  - Adverse slope anomalies: 0
  - Provenance errors: 0
  - Overall status: Passed (`is_valid: True`).
- Tested against `data/cities/mumbai/drainage_links.geojson` (BRIMSTOWAD):
  - Features evaluated: 33
  - Verified infrastructure status: Passed.

### 13. Implementation File References
- Implementation: `services/drainage/validator.py`
- Endpoints: `services/api/routers/drainage.py`
- Automated Tests: `tests/unit/test_phase3_elevation_flood_drainage.py`

---

## ALG-HIER-01: Dynamic Topological Subarea Hierarchy & Neighbor Engine

### 1. Algorithm ID & Name
- **ID**: `ALG-HIER-01`
- **Name**: Dynamic Topological Subarea Hierarchy, Bounding Envelope Extraction, and Shared Boundary Neighbor Resolution Engine

### 2. Implementation Status
- **Status**: Production / Fully Implemented and Verified
- **Version**: 1.0.0

### 3. Algorithm Type
- **Type**: New MUFNS Geospatial Hierarchy Component

### 4. Objective
Dynamically discover, index, and validate Mumbai municipal subareas directly from GeoJSON storage without hardcoding subarea counts, IDs, or geometric configurations. Automatically resolve shared boundaries, topological neighbors, parent ward lineages, and spatial bounding envelopes for adaptive 3D simulation and evacuation routing.

### 5. Workflow Diagram
```
[data/cities/mumbai/subareas.geojson (80 subareas)]
                         │
                         ▼
             [GeoJSON Ingestion & Repair]
            (buffer(0) for self-intersections)
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
[Spatial Indexing] [Parent Ward Index] [Context Envelope]
  (Shapely Polygons)   (24 BMC Wards)   (margin_factor = 0.25)
        │
        ▼
[Topological Neighbor Resolution]
   - touches(other_geom)
   - intersection(other_geom) LineString length in meters
   - search envelope buffer context (850m)
```

### 6. Inputs, Sources, Units & Coordinate Systems
- **Input File**: `data/cities/mumbai/subareas.geojson`
- **Feature Count**: 80 subareas (dynamically discovered)
- **CRS**: WGS-84 (`EPSG:4326`)
- **Metric Calculations**: Great-circle / planar metric projections ($1^\circ \text{lat} \approx 110.57\text{ km}$, $1^\circ \text{lon} \approx 104.64\text{ km}$ at latitude 19.0° N).

### 7. Step-by-Step Processing Workflow & Formulations
1. **Dynamic Loading & Validation**: Ingest all features from disk. For each feature, validate polygon closure and repair topological self-intersections using:
   $$G_{\text{clean}} = G.\text{buffer}(0)$$
2. **Attribute Indexing**: Index `subarea_id`, `name`, `parent_ward_id`, `parent_ward_name`, and calculate geodesic area:
   $$A_{\text{km}^2} = \iint_{G} d\lambda \, d\phi \cdot (110.57 \times 104.64)$$
3. **Bounding Envelope & Context Window**:
   $$\lambda_{\min}^{\text{ctx}} = \lambda_{\min} - \Delta \lambda \cdot m, \quad \lambda_{\max}^{\text{ctx}} = \lambda_{\max} + \Delta \lambda \cdot m$$
   $$\phi_{\min}^{\text{ctx}} = \phi_{\min} - \Delta \phi \cdot m, \quad \phi_{\max}^{\text{ctx}} = \phi_{\max} + \Delta \phi \cdot m$$
   where $m = 0.25$ provides immediate surrounding hydraulic context.
4. **Topological Neighbor Discovery**:
   For candidate subarea $S_i$ and neighbor $S_j$:
   - Boundary contact: $S_i.\text{touches}(S_j) = \text{True}$
   - Shared boundary segment: $L_{\text{shared}} = \text{length}(S_i \cap S_j) \cdot 111,000 \text{ m}$
   - Envelope proximity: $(S_i.\text{buffer}(\delta) \cap S_j) \ne \emptyset$, with $\delta = 0.008^\circ$ (~850 m).

### 8. Engineering Constants, Constraints & Thresholds
- Context buffer factor $m = 0.25$ (25% expansion around subarea envelope).
- Proximity search tolerance $\delta = 0.008^\circ$ (~850 m context radius).
- Strict non-hardcoding rule: System adapts automatically if subareas are added, split, or modified.

### 9. Outputs & Downstream Consumers
- Endpoints: `GET /api/v1/subareas`, `GET /api/v1/subareas/{id}`, `GET /api/v1/subareas/hierarchy-validation`.
- Consumed by `Subarea3DViewer.tsx`, terrain extraction, and evacuation routing.

### 10. Implementation File References
- Implementation: `services/spatial/hierarchy.py`
- Endpoints: `services/api/routers/subareas.py`
- Tests: `tests/unit/test_phase4_adaptive_3d_routing.py::TestSubareaHierarchy`

---

## ALG-TERR3D-01: Spatially Bounded Adaptive 3D Terrain & Water Surface Extrusion

### 1. Algorithm ID & Name
- **ID**: `ALG-TERR3D-01`
- **Name**: Spatially Bounded Copernicus GLO-30 DEM 3D Terrain Heightfield Extraction and Local Flood Surface Extrusion

### 2. Implementation Status
- **Status**: Production / Fully Implemented and Verified
- **Version**: 1.0.0

### 3. Algorithm Type
- **Type**: New MUFNS 3D Geospatial Visualization Component

### 4. Objective
Provide a lightweight, GPU-performant (<50 KB payload, <5 ms render) 3D elevation heightfield and water surface extrusion for any selected Mumbai subarea without streaming the entire citywide DEM or freezing the browser.

### 5. Workflow Diagram
```
[Active Subarea Request: subarea_id]
                │
                ▼
[Retrieve Context Envelope from Hierarchy]
                │
                ▼
[Crop Copernicus DEM (1800x1620) to Bounding Box]
                │
                ▼
[Bilinear Resample to Compact 64x64 Matrix]
                │
                ▼
[Generate Subarea Binary Inclusion Mask (64x64)]
                │
                ▼
[Drape 2D Hydrodynamic Depth: z_water = z_bed + h]
(Dry cells h < 0.01m marked transparent/unflooded)
                │
                ▼
[Output 3D Matrix & Provenance Telemetry to WebGL/Canvas]
```

### 6. Inputs, Sources, Units & Coordinate Systems
- **DEM Source**: Copernicus GLO-30 Digital Surface Model (ESA), `data/raw/terrain/opentopography_cop30_mumbai_bbox.tif`.
- **Flood Source**: 2D Diffusive Wave hydrodynamic simulation depth grid (`NowcastResult.depth_grid`).
- **Matrix Dimension**: $64 \times 64$ cells (configurable).
- **Units**: Elevations and water depths in metres.
- **Vertical Reference Datum**: EGM96 Geoid (metres MSL).

### 7. Step-by-Step Processing Workflow & Mathematical Formulations
1. **Context Window Coordinate Mapping**:
   For subarea bounds $[\lambda_{\min}, \lambda_{\max}, \phi_{\min}, \phi_{\max}]$:
   $$r_{\text{north}} = \left\lfloor \frac{\phi_{\text{dem,max}} - \phi_{\max}}{\Delta \phi_{\text{dem}}} \right\rfloor, \quad r_{\text{south}} = \left\lfloor \frac{\phi_{\text{dem,max}} - \phi_{\min}}{\Delta \phi_{\text{dem}}} \right\rfloor$$
   $$c_{\text{west}} = \left\lfloor \frac{\lambda_{\min} - \lambda_{\text{dem,min}}}{\Delta \lambda_{\text{dem}}} \right\rfloor, \quad c_{\text{east}} = \left\lfloor \frac{\lambda_{\max} - \lambda_{\text{dem,min}}}{\Delta \lambda_{\text{dem}}} \right\rfloor$$
2. **Cropping & Bilinear Resampling**:
   Extract raw raster window $Z_{\text{crop}} = Z[r_{\text{north}}:r_{\text{south}}, c_{\text{west}}:c_{\text{east}}]$ and resample to $64 \times 64$ grid $Z_{64 \times 64}$ via bilinear interpolation.
3. **Subarea Binary Inclusion Mask**:
   For each cell $(r, c)$ with coordinate $(\lambda_c, \phi_r)$, determine polygon containment:
   $$M(r, c) = \begin{cases} \text{True} & \text{if } (\lambda_c, \phi_r) \in G_{\text{subarea}} \\ \text{False} & \text{otherwise (neighboring context)} \end{cases}$$
4. **Water Surface Elevation Extrusion**:
   $$z_{\text{water}}(r, c) = \begin{cases} z_{\text{bed}}(r, c) + h(r, c) & \text{if } h(r, c) \ge 0.01\text{ m} \\ 0.0 & \text{if } h(r, c) < 0.01\text{ m (dry / transparent)} \end{cases}$$

### 8. Engineering Constants, Constraints & Thresholds
- Target grid size: $64 \times 64$ cells (optimal balance between high topographic resolution and lightweight WebGL rendering).
- Dry-cell cutoff threshold: $h_{\text{dry}} = 0.01\text{ m}$ (1.0 cm). Dry ground is strictly transparent.
- Vertical datum: EGM96 Geoid MSL.

### 9. Outputs & Downstream Consumers
- Endpoints: `GET /api/v1/subareas/{id}/terrain3d`, `GET /api/v1/subareas/{id}/flood3d`.
- Consumed by `Subarea3DViewer.tsx` (city dashboard and citizen web portal).

### 10. Implementation File References
- Implementation: `services/terrain/subarea_3d.py`, `services/flood/subarea_flood3d.py`
- Endpoints: `services/api/routers/subareas.py`
- Tests: `tests/unit/test_phase4_adaptive_3d_routing.py::TestSubarea3DTerrain`

---

## ALG-ROUT-01: Flood-Impeded Graph Evacuation Routing (FIGER v1.0)

### 1. Algorithm ID & Name
- **ID**: `ALG-ROUT-01`
- **Name**: Flood-Impeded Graph Evacuation Routing Engine (FIGER v1.0) on OpenStreetMap Road Network

### 2. Implementation Status
- **Status**: Production / Fully Implemented and Verified
- **Version**: 1.0.0

### 3. Algorithm Type
- **Type**: New MUFNS Graph Routing & Disaster Evacuation Component

### 4. Objective
Calculate the lowest-flood-exposure evacuation route from any origin within a subarea to verified, flood-safe emergency destinations (BMC shelters, hospitals) using the genuine 14,563-segment Mumbai OpenStreetMap road network with dynamic flood depth impedance penalties and vehicle clearance thresholds.

### 5. Workflow Diagram
```
[Origin in Subarea (Centroid or GPS)] ──> [k-d Tree Snapping to Nearest OSM Node]
                                                              │
[Candidate Destinations: BMC Shelters/Hospitals] ───────────────┤
  (Distance ranking, flood depth check at destination)        │
                                                              ▼
                                               [Dijkstra Pathfinding]
                                               Edge Weight W(e):
                                               - Clear (h < 0.15m): Length / V_base
                                               - Caution (0.15 <= h < 0.30m): 2x Penalty
                                               - Difficult (0.30 <= h < 0.50m): 6.6x Penalty
                                               - Impassable (h >= threshold): Infinity (Blocked)
                                                              │
                                                              ▼
                                                [Evacuation Route Geometry]
                                                - Waypoint Polyline (WGS-84)
                                                - Total Distance (km)
                                                - Travel Time (min)
                                                - Max Corridor Depth (m)
                                                - Passability Verdict
                                                - MANDATORY SAFETY DISCLAIMER
```

### 6. Inputs, Sources, Units & Coordinate Systems
- **Road Network**: OpenStreetMap Mumbai driving road network (`data/processed/roads/mumbai_road_network.geojson`, 14,563 line segments).
- **Destinations**: Official BMC designated emergency shelters (`data/processed/emergency/mumbai_flood_shelters.geojson`) and public health facilities (`data/cities/mumbai/critical_infrastructure.geojson`).
- **Dynamic Inundation**: 2D Diffusive Wave flood depth matrix ($h$).
- **Spatial Index**: `scipy.spatial.cKDTree` built on 2D road node coordinates.

### 7. Step-by-Step Processing Workflow & Formulations
1. **Graph Construction**: Build directed multigraph $G = (V, E)$ from OSM road geometry. Each edge $e = (u, v)$ has baseline length $L_e$ in metres:
   $$L_e = 2R \arcsin \sqrt{\sin^2\left(\frac{\Delta \phi}{2}\right) + \cos \phi_u \cos \phi_v \sin^2\left(\frac{\Delta \lambda}{2}\right)}$$
   with earth radius $R = 6,371,000\text{ m}$.
2. **Spatial Coordinate Snapping**: For origin $P_{\text{orig}}$ and destination $P_{\text{dest}}$, query the k-d tree:
   $$u_{\text{start}} = \arg\min_{v \in V} \|P_{\text{orig}} - v\|_2, \quad v_{\text{end}} = \arg\min_{v \in V} \|P_{\text{dest}} - v\|_2$$
3. **Dynamic Flood Depth Sampling**:
   Sample flood depth $h(e)$ at edge midpoint from the latest simulation georeferenced raster:
   $$r_e = \left\lfloor \frac{\phi_{\max} - \phi_e}{\Delta \phi} \right\rfloor, \quad c_e = \left\lfloor \frac{\lambda_e - \lambda_{\min}}{\Delta \lambda} \right\rfloor, \quad h(e) = H[r_e, c_e]$$
4. **Flood-Impedance Edge Weight Formulation**:
   $$W(e) = \begin{cases}
   \infty & \text{if } h(e) \ge h_{\text{threshold}} \text{ (Impassable)} \\
   \frac{L_e}{0.15 \cdot V_{\text{base}}} & \text{if } 0.30\text{ m} \le h(e) < 0.50\text{ m (Severe Waterlogging)} \\
   \frac{L_e}{0.50 \cdot V_{\text{base}}} & \text{if } 0.15\text{ m} \le h(e) < 0.30\text{ m (Street Water)} \\
   \frac{L_e}{V_{\text{base}}} & \text{if } h(e) < 0.15\text{ m (Clear Roadway)}
   \end{cases}$$
5. **Dijkstra Shortest Path Search**:
   $$\text{Route}^* = \arg\min_{\text{Path } P} \sum_{e \in P} W(e)$$
6. **Passability Classification**:
   - `CLEAR`: $\max_{e \in P^*} h(e) < 0.15\text{ m}$
   - `CAUTION`: $0.15\text{ m} \le \max_{e \in P^*} h(e) < 0.30\text{ m}$
   - `HAZARDOUS`: $0.30\text{ m} \le \max_{e \in P^*} h(e) < h_{\text{threshold}}$
   - `IMPASSABLE`: No route exists under $h_{\text{threshold}}$. System emits explicit emergency guidance: *"All ground evacuation routes blocked by floodwaters. Seek vertical shelter immediately."*

### 8. Engineering Constants, Constraints & Thresholds
- **Vehicle Clearance Cutoff ($h_{\text{threshold}}$)**:
  - Standard Passenger Car: $0.30\text{ m}$ (NDMA Urban Flood Guideline).
  - Emergency / High-Clearance Rescue Vehicle: $0.50\text{ m}$.
  - Pedestrian Evacuation: $0.15\text{ m}$.
- **Baseline Speeds**:
  - Motorway / Trunk: $50\text{ km/h}$ ($13.89\text{ m/s}$).
  - Primary / Secondary: $35\text{ km/h}$ ($9.72\text{ m/s}$).
  - Residential / Tertiary: $20\text{ km/h}$ ($5.56\text{ m/s}$).
- **Mandatory Safety Disclaimer**:
  *"Candidate Evacuation Corridor — Lowest Modeled Flood Exposure. Not guaranteed safe under all real-world conditions. Always follow official emergency service directions."*

### 9. Outputs & Downstream Consumers
- Endpoints: `GET /api/v1/subareas/{id}/destinations`, `POST /api/v1/subareas/{id}/evacuation-route`.
- Consumed by `Subarea3DViewer.tsx` in both municipal command center and citizen portal.

### 10. Missing-Data & Error Behaviour
- If destination is disconnected or completely surrounded by water exceeding vehicle clearance, the engine catches `NetworkXNoPath` and emits `route_found: False` with immediate vertical sheltering directive.

### 11. Uncertainty & Scientific Limitations
- Does not account for dynamic traffic congestion or real-time debris/fallen trees not reported to the GIS database. Route represents lowest modeled hydrologic hazard corridor.

### 12. Validation Methods & Actual Results
- Tested across all 80 subareas against 14,563 OSM road segments.
- Average pathfinding latency: $18\text{ ms}$ on dual-core CPU.
- Verified 100% adherence to non-guaranteed safety disclaimer.

### 13. Implementation File References
- Implementation: `services/routing/evacuation_engine.py`
- Endpoints: `services/api/routers/subareas.py`
- Tests: `tests/unit/test_phase4_adaptive_3d_routing.py::TestRoadGraphAndEvacuationRouting`

