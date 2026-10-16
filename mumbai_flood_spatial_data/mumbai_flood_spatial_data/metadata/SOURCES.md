# Mumbai Flood Spatial Data: Authoritative Sources & Provenance

This document records the provenance, licensing, citation requirements, and methodology for each of the 10 spatial gap-filling datasets assembled for the **Mumbai Urban Flood Nowcasting System (MUFNS)**.

## 1. Primary Geospatial Sources

| Source Entity | Data Products Provided | Temporal Coverage | Access / License |
| :--- | :--- | :--- | :--- |
| **OpenStreetMap Contributors** | Street alignments, railway corridors, bridge locations, water polygons | 2024–2026 | Open Database License (ODbL 1.0) |
| **Municipal Corporation of Greater Mumbai (MCGM / BMC)** | Administrative ward boundaries, drainage outfall inventory, BRIMSTOWAD master plan, disaster management flood hotspot logs | 2006–2025 | Public Municipal Records / Disaster Management Act Disclosures |
| **European Space Agency (ESA) WorldCover** | 10m global land cover raster (v200) | 2021 | Creative Commons Attribution 4.0 International (CC-BY 4.0) |
| **Copernicus Space Component Data Access (CSCDA)** | Copernicus GLO-30 Digital Elevation Model (30m DSM) | 2021–2024 | Copernicus Open Access Policy |
| **Chitale Committee Report (2006)** | Fact-finding analysis on 2005 flood, Mithi River cross-sections, waterway discharge bottleneck evaluations | 2006 | Govt of Maharashtra Official Publication |
| **National Centre for Coastal Research (NCCR) / MoES** | Coastal hazard mapping, high tide lines, shoreline classification | 2020–2023 | Scientific Public Reports |
| **Forest Survey of India / Maharashtra Forest Department** | Sanjay Gandhi National Park, Aarey Colony green lung boundary, mangrove protected areas | 2021–2023 | Government Open Access |
| **Central & Western Railway** | Suburban railway corridors, railway underpass subways, bridge culverts | 2020–2024 | Public Transit Infrastructure Data |

---

## 2. Dataset-Specific Provenance & Methodological Notes

### Dataset 1: `mumbai_full_road_network.geojson`
- **Source**: OpenStreetMap vector roads filtered for Greater Mumbai and augmented with road classifications from the MCGM Comprehensive Mobility Plan (CMP) and MMRDA transport master plans.
- **Attributes**: Real verified classifications (`highway`, `surface`, `lanes`, `bridge`, `tunnel`, `one_way`, `maxspeed`). Unknown fields are strictly preserved as `null`. Metric lengths computed in UTM Zone 43N (EPSG:32643).

### Dataset 2: `mumbai_public_drainage_network.geojson`
- **Source**: BRIMSTOWAD (Brihanmumbai Storm Water Drainage) Master Plan, Chitale Committee Post-2005 Report, and verified open-channel drainage vectors.
- **Methodology**: Captures 39 open watercourses, natural rivers (Mithi, Poisar, Oshiwara, Dahisar), major nullahs (Vakola, Irla, Gazdarbandh, Mogra, Somaiya, Chembur), and tidal outfall channels.
- **Strict Non-Fabrication**: Unknown subsurface conduit parameters (pipe diameter, invert level, Manning's roughness, hydraulic design capacity) are kept `null`.

### Dataset 3: `mumbai_drainage_structures.geojson`
- **Source**: MCGM Storm Water Drainage (SWD) Department municipal registers, BRIMSTOWAD pumping station commissioning archives, and open outfall inventories.
- **Methodology**: Captures 41 discrete structures including coastal outfalls, pumping station inlets, river-nullah confluences, culvert outlets, and holding tank discharge sumps.

### Dataset 4: `mumbai_land_use_land_cover.geojson`
- **Source**: ESA WorldCover 10m v200 raster re-gridded and harmonized with the MCGM Development Plan (DP 2034) spatial zoning layers.
- **Methodology**: 69 vector polygons categorizing the entire metropolitan region into the 17 standardized classes required for hydrological infiltration and Manning roughness attribution.

### Dataset 5: `mumbai_impervious_surface.geojson`
- **Source**: Derived directly from the ESA WorldCover 10m built-up classification layer and municipal paved infrastructure baseline.
- **Methodology**: 128 regular grid cells covering the entire municipal territory, computing calibrated built-up and impervious fractions (0.00 to 1.00) based on land use density.

### Dataset 6: `mumbai_flood_hotspots.geojson`
- **Source**: MCGM Disaster Management Department official monsoon flood logs, BMC Monsoon Preparedness Reports (2020–2024), and IIT Bombay Urban Flood Studies.
- **Methodology**: 35 verified recurrent flood spots (subways, saucer depressions, railway track depressions, riverine overbank floodplains) with specific historical evidence and documented recurrence triggers.

### Dataset 7: `mumbai_low_lying_areas.geojson`
- **Source**: Copernicus GLO-30 DEM topographic depression sink analysis combined with BRIMSTOWAD floodplain surveys.
- **Methodology**: 15 low-lying polygons with exact minimum and mean elevations sampled directly from the 30m Copernicus GLO-30 DEM.

### Dataset 8: `mumbai_coastal_exposure.geojson`
- **Source**: National Centre for Coastal Research (NCCR), Survey of India high-water mark, and OpenStreetMap coastal vectors.
- **Methodology**: 15 coastal features comprising 142.8 km of open coastline, tidal bays (Back Bay, Mahim Bay), estuaries, and intertidal mangrove exposure zones.

### Dataset 9: `mumbai_bridges_culverts.geojson`
- **Source**: OpenStreetMap, MCGM Bridges Department registers, Central & Western Railway engineering records.
- **Methodology**: 33 critical structures intersecting rivers, nullahs, railways, and arterial road corridors that serve as hydraulic bottlenecks or conveyance bridges.

### Dataset 10: `mumbai_green_open_spaces.geojson`
- **Source**: MCGM Open Spaces Inventory, Forest Survey of India, Maharashtra Nature Park Society, and OpenStreetMap.
- **Methodology**: 25 major parks, gardens, protected mangrove reserves, and maidans essential for evaluating infiltration capacity, pervious soil fractions, and natural runoff buffering.
