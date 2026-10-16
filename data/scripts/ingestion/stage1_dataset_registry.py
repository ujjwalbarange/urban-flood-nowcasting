"""Stage 1: Create dataset_registry table and register all existing datasets.

Does NOT modify or delete any existing tables or data.
Creates a NEW table 'dataset_registry' to track provenance of every dataset.
"""
import asyncio
import os
import ssl
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

_root = Path(__file__).resolve().parent
for _ in range(10):
    if (_root / ".env").exists():
        break
    _root = _root.parent
load_dotenv(_root / ".env")


DATASET_REGISTRY_DDL = """
CREATE TABLE IF NOT EXISTS public.dataset_registry (
    dataset_id VARCHAR(128) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(64) NOT NULL,
    provider VARCHAR(255) NOT NULL,
    product VARCHAR(128),
    description TEXT,
    spatial_coverage VARCHAR(255),
    temporal_coverage VARCHAR(255),
    spatial_resolution VARCHAR(64),
    temporal_resolution VARCHAR(64),
    units VARCHAR(64),
    processing_level VARCHAR(32),
    crs VARCHAR(32) DEFAULT 'EPSG:4326',
    db_table VARCHAR(128),
    file_path TEXT,
    source_url TEXT,
    license VARCHAR(255),
    record_count INTEGER,
    version VARCHAR(64),
    checksum VARCHAR(128),
    ingestion_date TIMESTAMPTZ DEFAULT NOW(),
    last_verified TIMESTAMPTZ DEFAULT NOW(),
    processing_status VARCHAR(32) DEFAULT 'ingested',
    quality_status VARCHAR(32) DEFAULT 'unverified',
    confidence VARCHAR(32),
    limitations TEXT,
    downstream_usage TEXT,
    provenance JSONB DEFAULT '{}',
    attributes JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_dataset_registry_category ON public.dataset_registry(category);
CREATE INDEX IF NOT EXISTS idx_dataset_registry_provider ON public.dataset_registry(provider);
"""

# All datasets to register, derived from actual database inspection
DATASETS = [
    {
        "dataset_id": "insat3dr_hem_2024_2025",
        "name": "INSAT-3DR Hydro-Estimator Precipitation (HEM)",
        "category": "rainfall",
        "provider": "ISRO / SAC / MOSDAC",
        "product": "3RIMG_L2B_HEM",
        "description": "Event-based INSAT-3DR Hydro-Estimator precipitation product for Mumbai monsoon flood episodes (2024-2025). Primary geostationary satellite rainfall product.",
        "spatial_coverage": "71.997E-73.010E, 17.996N-19.009N (Mumbai + Arabian Sea approach corridor)",
        "temporal_coverage": "2024-07-07 to 2024-07-11, 2025-08-13 to 2025-08-21",
        "spatial_resolution": "0.036 deg (~4 km)",
        "temporal_resolution": "30 min",
        "units": "mm/hr",
        "processing_level": "L2B",
        "db_table": "satellite_rainfall_observations",
        "file_path": "data/processed/rainfall/insat3dr/HEM/",
        "source_url": "https://mosdac.gov.in",
        "license": "ISRO/MOSDAC public data policy",
        "record_count": 644,
        "quality_status": "verified",
        "confidence": "high",
        "limitations": "Event-based coverage only (not continuous). ~4km resolution cannot resolve sub-city convective cells.",
        "downstream_usage": "Rainfall forcing for flood simulation; fusion engine (HEM_ONLY, GPM_HEM, FULL_FUSION modes)",
    },
    {
        "dataset_id": "insat3dr_imc_2024",
        "name": "INSAT-3DR IMAGER Precipitation Retrieval (IMC)",
        "category": "rainfall",
        "provider": "ISRO / SAC / MOSDAC",
        "product": "3RIMG_L2B_IMC",
        "description": "Event-based INSAT-3DR IMAGER precipitation retrieval product. Secondary/validation rainfall product.",
        "spatial_coverage": "71.997E-73.010E, 17.996N-19.009N",
        "temporal_coverage": "2024-07-07 to 2024-07-11, 2024-07-23 to 2024-07-26",
        "spatial_resolution": "0.036 deg (~4 km)",
        "temporal_resolution": "30 min",
        "units": "mm/hr",
        "processing_level": "L2B",
        "db_table": "satellite_rainfall_observations",
        "file_path": "data/processed/rainfall/insat3dr/IMC/",
        "source_url": "https://mosdac.gov.in",
        "license": "ISRO/MOSDAC public data policy",
        "record_count": 429,
        "quality_status": "verified",
        "confidence": "high",
        "limitations": "Event-based coverage. 2025 IMC data not available.",
        "downstream_usage": "Validation rainfall product; fusion engine (IMC_ONLY, GPM_IMC modes)",
    },
    {
        "dataset_id": "gpm_imerg_mumbai",
        "name": "NASA GPM IMERG Satellite Precipitation",
        "category": "rainfall",
        "provider": "NASA / JAXA",
        "product": "GPM IMERG V06B/V07B",
        "description": "Global Precipitation Measurement multi-satellite merged precipitation estimates for Mumbai region.",
        "spatial_coverage": "Mumbai metropolitan area",
        "temporal_coverage": "Historical events (variable)",
        "spatial_resolution": "0.1 deg (~10 km)",
        "temporal_resolution": "30 min",
        "units": "mm/hr",
        "processing_level": "L3",
        "db_table": "rainfall_satellite",
        "source_url": "https://gpm.nasa.gov/data/imerg",
        "license": "NASA open data",
        "record_count": 576,
        "quality_status": "verified",
        "confidence": "high",
        "limitations": "Coarser spatial resolution than INSAT. Latency for final-run product.",
        "downstream_usage": "Rainfall forcing; fusion engine (GPM_ONLY, GPM_HEM, GPM_IMC, FULL_FUSION modes)",
    },
    {
        "dataset_id": "aws_rainfall_gauges",
        "name": "Automatic Weather Station Rainfall Observations",
        "category": "rainfall",
        "provider": "BMC / IMD / MCGM",
        "product": "Ground gauge measurements",
        "description": "Ground-truth rainfall observations from automatic weather stations across Mumbai.",
        "spatial_coverage": "Mumbai urban area (point stations)",
        "temporal_coverage": "Variable event periods",
        "spatial_resolution": "Point observations",
        "temporal_resolution": "Hourly to sub-hourly",
        "units": "mm, mm/hr",
        "processing_level": "L1",
        "db_table": "rainfall_observations",
        "record_count": 27,
        "quality_status": "unverified",
        "confidence": "medium",
        "limitations": "Limited station count. Provenance/calibration status unknown.",
        "downstream_usage": "Ground-truth calibration for satellite rainfall; fusion engine (FULL_FUSION mode)",
    },
    {
        "dataset_id": "weather_nwp_forecasts",
        "name": "Numerical Weather Prediction Forecasts",
        "category": "meteorology",
        "provider": "Open-Meteo / ICON / GFS",
        "product": "NWP forecast grid",
        "description": "Gridded weather forecasts including precipitation, temperature, wind, humidity.",
        "spatial_coverage": "Mumbai metropolitan area",
        "temporal_coverage": "168-hour forecast horizon",
        "spatial_resolution": "Variable (model-dependent)",
        "temporal_resolution": "Hourly",
        "units": "Various (mm, °C, m/s, %)",
        "processing_level": "L3 (model output)",
        "db_table": "weather_forecasts",
        "record_count": 30240,
        "quality_status": "unverified",
        "confidence": "medium",
        "limitations": "Reanalysis/forecast data, not direct observations.",
        "downstream_usage": "Real-time nowcasting rainfall forcing; future rainfall scenario input",
    },
    {
        "dataset_id": "weather_observations",
        "name": "AWS Weather Observations",
        "category": "meteorology",
        "provider": "BMC / IMD",
        "product": "Surface weather observations",
        "description": "Surface weather observations from AWS stations (temperature, humidity, wind, pressure).",
        "spatial_coverage": "Mumbai urban area (point stations)",
        "temporal_coverage": "Variable",
        "spatial_resolution": "Point observations",
        "temporal_resolution": "Hourly",
        "units": "Various",
        "processing_level": "L1",
        "db_table": "weather_observations",
        "record_count": 108,
        "quality_status": "unverified",
        "confidence": "medium",
        "limitations": "Limited station count.",
        "downstream_usage": "Atmospheric context for flood simulation",
    },
    {
        "dataset_id": "copernicus_glo30_dem",
        "name": "Copernicus GLO-30 Digital Elevation Model",
        "category": "terrain",
        "provider": "ESA / Copernicus",
        "product": "GLO-30 DEM",
        "description": "30-meter resolution digital elevation model for Greater Mumbai from Copernicus programme.",
        "spatial_coverage": "72.65E-73.10E, 18.85N-19.35N (Greater Mumbai)",
        "spatial_resolution": "30 m (1 arcsecond)",
        "units": "metres above EGM2008 geoid",
        "processing_level": "L3",
        "db_table": "dem_tiles",
        "file_path": "data/raw/terrain/opentopography_cop30_mumbai_bbox.tif",
        "source_url": "https://portal.opentopography.org",
        "license": "Copernicus data policy (free and open)",
        "record_count": 1,
        "quality_status": "verified",
        "confidence": "high",
        "limitations": "30m resolution cannot resolve individual buildings or micro-drainage features.",
        "downstream_usage": "Hydraulic routing (2D diffusive wave); catchment delineation; flood depth calculation",
    },
    {
        "dataset_id": "terrain_derivatives",
        "name": "DEM Terrain Derivatives",
        "category": "terrain",
        "provider": "Derived (from Copernicus GLO-30)",
        "product": "Slope, aspect, flow direction, flow accumulation, TWI, sinks",
        "description": "Terrain analysis derivatives computed from the Copernicus GLO-30 DEM.",
        "spatial_coverage": "Greater Mumbai",
        "spatial_resolution": "30 m",
        "processing_level": "Derived",
        "db_table": "terrain_derivatives",
        "record_count": 6,
        "quality_status": "verified",
        "confidence": "high",
        "limitations": "Derived from 30m DEM; cannot resolve sub-grid features.",
        "downstream_usage": "Flow routing; catchment delineation; TWI for saturation excess; sink identification",
    },
    {
        "dataset_id": "lulc_mumbai",
        "name": "Land Use / Land Cover Classification",
        "category": "land_surface",
        "provider": "Unknown (audit pending)",
        "product": "LULC classified polygons",
        "description": "Land use/land cover classification for Mumbai. 69 distinct classes.",
        "spatial_coverage": "Greater Mumbai",
        "processing_level": "L3 (classified)",
        "db_table": "land_use_land_cover",
        "record_count": 69,
        "quality_status": "unverified",
        "confidence": "medium",
        "limitations": "Source provenance not independently verified. Class definitions need mapping to hydrologic parameters.",
        "downstream_usage": "Manning's roughness coefficient; infiltration parameters; runoff response curves",
    },
    {
        "dataset_id": "impervious_surface_mumbai",
        "name": "Impervious Surface Fraction Grid",
        "category": "land_surface",
        "provider": "Unknown (audit pending)",
        "product": "Impervious fraction + built-up fraction",
        "description": "Gridded impervious surface fractions and built-up fractions for Mumbai.",
        "spatial_coverage": "Mumbai urban area",
        "processing_level": "Derived",
        "db_table": "impervious_surface_grid",
        "record_count": 128,
        "quality_status": "unverified",
        "confidence": "medium",
        "limitations": "128 cells covers limited area. Source provenance not verified.",
        "downstream_usage": "Infiltration reduction; runoff generation; Horton model imperviousness scaling",
    },
    {
        "dataset_id": "drainage_primary",
        "name": "Primary Drainage Network",
        "category": "drainage",
        "provider": "BMC / BRIMSTOWAD / Public Records",
        "product": "Major drainage channels",
        "description": "39 major public drainage channels/storm drains in Mumbai.",
        "spatial_coverage": "Mumbai city area",
        "processing_level": "L1 (mapped)",
        "db_table": "primary_drainage_network",
        "record_count": 39,
        "quality_status": "unverified",
        "confidence": "medium",
        "limitations": "Does NOT represent complete underground storm-water system. No pipe diameters, invert levels, or Manning coefficients.",
        "downstream_usage": "Surface drainage guidance; major channel connectivity; coupling point identification",
    },
    {
        "dataset_id": "drainage_structures",
        "name": "Drainage Structures",
        "category": "drainage",
        "provider": "BMC / BRIMSTOWAD / Public Records",
        "product": "Outfalls, sluice gates, culverts",
        "description": "41 drainage structures including outfalls, sluice gates, and other hydraulic features.",
        "spatial_coverage": "Mumbai city area",
        "db_table": "drainage_structures",
        "record_count": 41,
        "quality_status": "unverified",
        "confidence": "medium",
        "limitations": "Operational parameters (discharge capacity, gate positions) unknown.",
        "downstream_usage": "Outfall boundary conditions; hydraulic feature mapping",
    },
    {
        "dataset_id": "drainage_nodes",
        "name": "Drainage Network Nodes",
        "category": "drainage",
        "provider": "BMC / Mapped",
        "product": "Manholes, inlets, junctions",
        "description": "35 drainage network nodes with type and elevation data.",
        "db_table": "drainage_nodes",
        "record_count": 35,
        "quality_status": "unverified",
        "confidence": "low",
        "limitations": "Very sparse coverage. Invert elevations may be assumed, not measured. Data quality column present.",
        "downstream_usage": "Surface-drainage coupling points for orifice exchange model",
    },
    {
        "dataset_id": "pumping_stations",
        "name": "Municipal Pumping Stations",
        "category": "drainage",
        "provider": "BMC",
        "product": "Pump locations and rated capacities",
        "description": "8 municipal pumping stations with rated capacities.",
        "db_table": "pumping_stations",
        "record_count": 8,
        "quality_status": "unverified",
        "confidence": "medium",
        "limitations": "Rated capacity only; actual operational capacity during events is unknown.",
        "downstream_usage": "Drainage coupling; outflow capacity constraints",
    },
    {
        "dataset_id": "water_bodies",
        "name": "Water Bodies / Waterways / Rivers",
        "category": "hydrology",
        "provider": "OpenStreetMap",
        "product": "Rivers, nullahs, creeks, streams, canals",
        "description": "1,730 water body features from OSM including rivers, nullahs, creeks, and drainage channels.",
        "spatial_coverage": "Greater Mumbai",
        "db_table": "water_bodies",
        "record_count": 1730,
        "quality_status": "unverified",
        "confidence": "medium",
        "limitations": "OSM community-sourced. Not hydraulically parameterized.",
        "downstream_usage": "Hydrographic network; flow routing guidance; proximity analysis for flood risk",
    },
    {
        "dataset_id": "tide_mumbai",
        "name": "Tide Observations / Predictions",
        "category": "coastal",
        "provider": "INCOIS / Survey of India / Tide tables",
        "product": "Tide height predictions",
        "description": "72 tidal height records for Mumbai coast.",
        "spatial_coverage": "Mumbai coast / Arabian Sea",
        "temporal_resolution": "Variable",
        "units": "metres above datum",
        "db_table": "tide_observations",
        "record_count": 72,
        "quality_status": "unverified",
        "confidence": "medium",
        "limitations": "Limited temporal coverage. Datum reference needs verification.",
        "downstream_usage": "Coastal boundary condition for flood simulation; compound flooding scenarios",
    },
    {
        "dataset_id": "historical_flood_events",
        "name": "Historical Flood Event Records",
        "category": "validation",
        "provider": "Multiple (BMC, news, research)",
        "product": "Flood occurrence records with attributes",
        "description": "209 historical flood event records with location, depth, duration, rainfall, and impact data.",
        "spatial_coverage": "Mumbai city area",
        "temporal_coverage": "2016-2025",
        "db_table": "historical_flood_events",
        "record_count": 209,
        "quality_status": "unverified",
        "confidence": "medium",
        "limitations": "Mixed provenance (observed, satellite-derived, modelled). Flood depth/extent not spatially complete.",
        "downstream_usage": "Model validation; hotspot hit rate; precision/recall calculation",
    },
    {
        "dataset_id": "flood_hotspots",
        "name": "Chronic Flood Hotspot Locations",
        "category": "validation",
        "provider": "BMC / Research / News analysis",
        "product": "Known recurring flood-prone locations",
        "description": "35 known chronic flood-prone locations in Mumbai with severity and recurrence data.",
        "db_table": "flood_hotspots",
        "record_count": 35,
        "quality_status": "verified",
        "confidence": "high",
        "limitations": "Point locations, not flood extent polygons. Not suitable as complete spatial ground truth.",
        "downstream_usage": "Validation: hotspot hit rate; model calibration targets",
    },
    {
        "dataset_id": "road_segments",
        "name": "Road Network Segments",
        "category": "exposure",
        "provider": "OpenStreetMap",
        "product": "Road segments with classification",
        "description": "14,563 road segments for Mumbai with road class, name, and length.",
        "spatial_coverage": "Greater Mumbai",
        "db_table": "road_segments",
        "record_count": 14563,
        "quality_status": "unverified",
        "confidence": "high",
        "limitations": "OSM community-sourced. Speed limits may be incomplete.",
        "downstream_usage": "Exposure overlay (affected roads); flood-aware routing; road impact assessment",
    },
    {
        "dataset_id": "buildings",
        "name": "Building Footprints",
        "category": "exposure",
        "provider": "OpenStreetMap / Microsoft",
        "product": "Building polygons",
        "description": "30,000 building footprints with area, type, and ward assignment.",
        "spatial_coverage": "Mumbai urban area",
        "db_table": "buildings",
        "record_count": 30000,
        "quality_status": "unverified",
        "confidence": "high",
        "limitations": "Not 100% complete coverage. Height/floor data sparse.",
        "downstream_usage": "Exposure overlay (affected buildings); population-at-risk estimation",
    },
    {
        "dataset_id": "population_grids",
        "name": "WorldPop Population Distribution Grids",
        "category": "exposure",
        "provider": "WorldPop / UN",
        "product": "Gridded population estimates",
        "description": "1,242 population grid cells covering Mumbai with density estimates.",
        "spatial_coverage": "Greater Mumbai",
        "db_table": "population_grids",
        "record_count": 1242,
        "quality_status": "unverified",
        "confidence": "medium",
        "limitations": "Model-based estimates, not census enumeration. Year reference needs verification.",
        "downstream_usage": "Exposure overlay (affected population); vulnerability assessment",
    },
    {
        "dataset_id": "critical_infrastructure",
        "name": "Critical Infrastructure",
        "category": "exposure",
        "provider": "OSM / BMC / Public records",
        "product": "Hospitals, police, fire stations, railway stations, emergency facilities",
        "description": "2,002 critical infrastructure points plus specialized tables for hospitals (1,667), police (122), fire (37), railway (167), emergency (9).",
        "spatial_coverage": "Mumbai urban area",
        "db_table": "critical_infrastructure, hospitals, police, fire_stations, railway_stations, emergency_facilities",
        "record_count": 2002,
        "quality_status": "unverified",
        "confidence": "medium",
        "downstream_usage": "Exposure overlay (affected infrastructure); emergency response planning",
    },
    {
        "dataset_id": "wards",
        "name": "Mumbai Administrative Wards",
        "category": "administrative",
        "provider": "BMC / MCGM",
        "product": "Ward boundary polygons",
        "description": "24 administrative ward boundaries for Greater Mumbai.",
        "spatial_coverage": "Greater Mumbai",
        "db_table": "wards",
        "record_count": 24,
        "quality_status": "verified",
        "confidence": "high",
        "downstream_usage": "Spatial aggregation; ward-level risk assessment; impact reporting",
    },
    {
        "dataset_id": "bridges_culverts",
        "name": "Bridges and Culverts",
        "category": "exposure",
        "provider": "OSM / Public records",
        "db_table": "bridges_and_culverts",
        "record_count": 33,
        "quality_status": "unverified",
        "confidence": "medium",
        "downstream_usage": "Hydraulic features; exposure overlay; flood-vulnerable infrastructure",
    },
    {
        "dataset_id": "low_lying_areas",
        "name": "Low-Lying Area Zones",
        "category": "terrain",
        "provider": "Derived (DEM analysis)",
        "db_table": "low_lying_areas",
        "record_count": 15,
        "quality_status": "unverified",
        "confidence": "medium",
        "downstream_usage": "Flood susceptibility; risk mapping",
    },
    {
        "dataset_id": "coastal_exposure",
        "name": "Coastal Exposure Zones",
        "category": "coastal",
        "provider": "Derived / Mapped",
        "db_table": "coastal_exposure_zones",
        "record_count": 15,
        "quality_status": "unverified",
        "confidence": "medium",
        "downstream_usage": "Coastal flood risk; tidal interaction zones",
    },
    {
        "dataset_id": "shelters",
        "name": "Emergency Shelters",
        "category": "exposure",
        "provider": "BMC / NDMA",
        "db_table": "shelters",
        "record_count": 10,
        "quality_status": "unverified",
        "confidence": "low",
        "limitations": "Very limited coverage (10 shelters).",
        "downstream_usage": "Evacuation planning; nearest shelter routing",
    },
    {
        "dataset_id": "green_open_spaces",
        "name": "Green and Open Spaces",
        "category": "land_surface",
        "provider": "OSM / Mapped",
        "db_table": "green_open_spaces",
        "record_count": 25,
        "quality_status": "unverified",
        "downstream_usage": "Pervious area identification; infiltration capacity",
    },
    {
        "dataset_id": "arterial_corridors",
        "name": "Critical Arterial Corridors",
        "category": "exposure",
        "provider": "OSM / Mapped",
        "db_table": "critical_arterial_corridors",
        "record_count": 78,
        "quality_status": "unverified",
        "downstream_usage": "Priority road impact assessment; traffic disruption estimation",
    },
]


async def main():
    import asyncpg

    raw = os.environ.get("DATABASE_URL", "")
    url = raw.replace("postgresql+asyncpg://", "postgresql://").split("?")[0]
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    conn = await asyncpg.connect(url, ssl=ctx)

    # 1. Create dataset_registry table
    print("Creating dataset_registry table...")
    await conn.execute(DATASET_REGISTRY_DDL)
    print("  [OK] Table created (IF NOT EXISTS)")

    # 2. Insert/update all datasets
    print(f"\nRegistering {len(DATASETS)} datasets...")
    inserted = 0
    updated = 0

    for ds in DATASETS:
        exists = await conn.fetchval(
            "SELECT 1 FROM dataset_registry WHERE dataset_id=$1",
            ds["dataset_id"]
        )

        if exists:
            # Update existing record
            await conn.execute("""
                UPDATE dataset_registry SET
                    name=$2, category=$3, provider=$4, product=$5,
                    description=$6, record_count=$7, quality_status=$8,
                    confidence=$9, limitations=$10, downstream_usage=$11,
                    db_table=$12, last_verified=NOW()
                WHERE dataset_id=$1
            """,
                ds["dataset_id"], ds.get("name", ""), ds.get("category", ""),
                ds.get("provider", ""), ds.get("product"),
                ds.get("description"), ds.get("record_count"),
                ds.get("quality_status", "unverified"), ds.get("confidence"),
                ds.get("limitations"), ds.get("downstream_usage"),
                ds.get("db_table")
            )
            updated += 1
            print(f"  [UPD] {ds['dataset_id']}")
        else:
            await conn.execute("""
                INSERT INTO dataset_registry (
                    dataset_id, name, category, provider, product,
                    description, spatial_coverage, temporal_coverage,
                    spatial_resolution, temporal_resolution, units,
                    processing_level, db_table, file_path, source_url,
                    license, record_count, quality_status, confidence,
                    limitations, downstream_usage
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21)
            """,
                ds["dataset_id"], ds.get("name", ""), ds.get("category", ""),
                ds.get("provider", ""), ds.get("product"),
                ds.get("description"), ds.get("spatial_coverage"),
                ds.get("temporal_coverage"), ds.get("spatial_resolution"),
                ds.get("temporal_resolution"), ds.get("units"),
                ds.get("processing_level"), ds.get("db_table"),
                ds.get("file_path"), ds.get("source_url"),
                ds.get("license"), ds.get("record_count"),
                ds.get("quality_status", "unverified"), ds.get("confidence"),
                ds.get("limitations"), ds.get("downstream_usage")
            )
            inserted += 1
            print(f"  [NEW] {ds['dataset_id']}")

    # 3. Verify
    total = await conn.fetchval("SELECT count(*) FROM dataset_registry")
    print(f"\n{'='*60}")
    print(f"STAGE 1 COMPLETE: {total} datasets registered ({inserted} new, {updated} updated)")
    print(f"{'='*60}")

    # Print summary
    rows = await conn.fetch(
        "SELECT dataset_id, name, category, record_count, quality_status FROM dataset_registry ORDER BY category, dataset_id"
    )
    print(f"\n{'Dataset ID':<35} {'Category':<15} {'Records':<10} {'Quality'}")
    print("-" * 80)
    for r in rows:
        print(f"{r['dataset_id']:<35} {r['category']:<15} {str(r['record_count'] or '?'):<10} {r['quality_status']}")

    await conn.close()


asyncio.run(main())
