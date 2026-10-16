# Required Agency Access & User-Provided Data Specifications

**Document Purpose**: In strict accordance with the project data principles ("DO NOT FABRICATE DATA" and "ASK ME ONLY FOR MISSING THINGS"), this document specifies the precise datasets, official agency accounts, and engineering parameters that cannot be acquired from unauthenticated open endpoints and require official access or user assistance.

---

## 1. MOSDAC DATA REQUIRED FROM USER

**Context**: User credentials (`MOSDAC_user_email`, `MOSDAC_pass`) are configured in `.env`. The authentication client in `services/rainfall/mosdac.py` successfully connects to Keycloak OpenID servers (`https://mosdac.gov.in/download_api/gettoken`).

To download native, high-resolution calibrated rainfall grids for operational nowcasting and historical benchmarking, the following specific granules are requested:

| Field | Required Specification |
| :--- | :--- |
| **Agency / Portal** | ISRO Space Applications Centre (SAC) — Meteorological & Oceanographic Satellite Data Archival Centre (MOSDAC) |
| **Dataset / Mission** | INSAT-3DR and INSAT-3DS Meteorological Payloads |
| **Product Name** | `3RIMG_L2B_HEM` (Level-2B Hydro-Estimator Method Rain Rate) and/or `3RIMG_L2B_QPE` (Quantitative Precipitation Estimation) |
| **Spatial Coverage** | Western Coastal India Bounding Box: $72.0^\circ\text{E} - 73.5^\circ\text{E}, 18.5^\circ\text{N} - 19.8^\circ\text{N}$ (or native India Disk sector covering Mumbai) |
| **Time Range Needed** | 1. **Historical Calibration Event**: July 26–27, 2005 (or earliest archived monsoon season on MOSDAC).<br>2. **Recent Benchmark Events**: August 29, 2017; July 2, 2019; July 18, 2021; September 25, 2024.<br>3. **Sample Operational Granule**: 1 complete native file for format verification. |
| **Expected File Format** | Native HDF5 (`.h5`) or NetCDF-4 (`.nc`) containing calibrated rain rate array (`RainRate`) and latitude/longitude lookup grids. |
| **Approximate Size** | ~15–25 MB per half-hourly granule. |
| **Why Required** | Replaces synthetic approximations with authentic ISRO geostationary satellite precipitation retrievals. |

---

## 2. IMD (INDIA METEOROLOGICAL DEPARTMENT) OFFICIAL RAIN GAUGE & RADAR DATA

**Context**: Public scraping of the IMD website is brittle and does not provide programmatic historical series. We do not attempt to bypass authentication.

| Field | Required Specification |
| :--- | :--- |
| **Agency** | India Meteorological Department (IMD) / Regional Meteorological Centre (RMC) Mumbai |
| **Required Datasets** | 1. **High-Cadence AWS Gauge Records**: 15-minute or hourly precipitation for Mumbai observatories (Colaba Station ID: 43057, Santacruz Station ID: 43003) for 2005-07-25 to 2005-07-28 and 2015–2025 monsoon seasons.<br>2. **Mumbai Doppler Weather Radar (DWR) Reflectivity**: Mumbai DWR (Colaba radar) Plan Position Indicator (PPI) or Max(Z) volume scans during severe cloudburst events. |
| **Variables Needed** | `station_id`, `timestamp` (UTC/IST specified), `rainfall_accumulated_mm`, `rainfall_rate_mmh`, `quality_flag`. For radar: raw UF / netCDF reflectivity ($Z$ in dBZ). |
| **Why Required** | Rain gauge records are ground truth for validating both satellite products (IMERG, MOSDAC) and 2D hydraulic simulation depth accuracy. Radar reflectivity is essential for genuine 0–3 hour convective nowcasting. |
| **Action for User** | If you or your institution has an IMD API data-sharing token or a research data agreement, place the token in `.env` as `IMD_API_TOKEN` or provide the official station CSV archives. |

---

## 3. MCGM BRIMSTOWAD DRAINAGE ENGINEERING AS-BUILTS

**Context**: We already have 35 major drainage nodes, 8 trunk nullahs, 8 pumping stations, and 11 outfalls in `mumbai_flood_data_package/06_drainage/` and PostGIS. However, micro-scale street drainage requires engineering dimensions that are not published on the public municipal GIS portal.

**Missing Drainage Fields (Left NULL rather than fabricated):**

| Missing Parameter | Engineering Significance | Current Approach | What is Needed from BMC / MCGM |
| :--- | :--- | :--- | :--- |
| **Drop Inlet Invert Levels** | Elevation where street runoff enters underground stormwater barrels. | Surface flow accumulates on 2D terrain; coupled at 14 major holding ponds only. | Municipal Storm Water Drains (SWD) Department CAD/GIS as-builts with invert levels ($m$ MSL) and rim levels for street drop inlets. |
| **Storm Pipe Diameters & Slopes** | Determines maximum hydraulic conveyance capacity before pressurized pipe surcharge. | Not fabricated. 1D pipes are restricted to the 8 verified major trunk nullahs with known widths/depths. | Stormwater pipe diameter schedule (300mm to 1800mm RC pipes) and longitudinal bed slopes. |
| **Live SCADA Pump Discharge Telemetry** | Actual volume of stormwater pumped into sea during high-tide locking ($m^3/s$). | Pumping stations are explicitly labeled as **Static Engineering Rated Capacity** ($m^3/s$). | Secure API endpoint or MQTT/REST telemetry feed from MCGM Disaster Control Room SCADA for active pump statuses. |
| **Tidal Outfall Flap Gate Conditions** | Functional vs. silted/jammed status of gravity outfall flap gates during rising tides. | Modeled assuming functional flap gates that close when tidal elevation exceeds inland water level. | Field inspection logs on siltation levels at the 11 major coastal outfalls (Lovegrove, Cleaveland, Irla, Mahalaxmi, etc.). |

---

## 4. BARE-EARTH LIDAR / UAV DTM (DIGITAL TERRAIN MODEL)

**Context**: We have ingested the 30m Copernicus GLO-30 DSM (`opentopography_cop30_mumbai_bbox.tif`). While suitable for basin-scale hydrology, a DSM includes building rooftops and canopy.

| Parameter | Current Dataset | Required for Street-Level Precision | Source Agency |
| :--- | :--- | :--- | :--- |
| **Elevation Model** | 30m Copernicus DSM (elevation includes roofs) | 1m to 5m Bare-Earth DTM (buildings stripped, true curb/gutter levels) | MCGM GIS Cell / Maharashtra Remote Sensing Applications Centre (MRSAC) / Survey of India (SOI) High-Resolution Drone Survey |
| **Action** | Use Copernicus GLO-30 DSM for baseline prototype; if MRSAC/BMC DTM data is accessible, provide the GeoTIFF tile for Hindmata/Dadar catchment. |
