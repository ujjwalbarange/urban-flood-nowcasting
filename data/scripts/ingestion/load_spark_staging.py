"""Ingest Spark Spatial Data Package into PostGIS Staging Schema (mufns_spatial_staging).

Creates staging tables for all 10 datasets:
1. mufns_spatial_staging.staging_roads_curated_78
2. mufns_spatial_staging.staging_drainage_network_39
3. mufns_spatial_staging.staging_drainage_structures_41
4. mufns_spatial_staging.staging_land_use_land_cover_69
5. mufns_spatial_staging.staging_impervious_surface_128
6. mufns_spatial_staging.staging_flood_hotspots_35
7. mufns_spatial_staging.staging_low_lying_areas_15
8. mufns_spatial_staging.staging_coastal_exposure_15
9. mufns_spatial_staging.staging_bridges_culverts_33
10. mufns_spatial_staging.staging_green_open_spaces_25

Preserves all source metadata, attributes, geometries (EPSG:4326), and creates GIST spatial indexes.
"""

import os
import sys
import ssl
import json
import time
import asyncio
from pathlib import Path
import asyncpg
from dotenv import load_dotenv

load_dotenv()
RAW_URL = os.environ.get("DATABASE_URL", "")
CLEAN_URL = RAW_URL.replace("postgresql+asyncpg://", "postgresql://").split("?")[0]

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

SPARK_DIR = Path("mumbai_flood_spatial_data")

STAGING_TABLES = [
    {
        "table": "staging_roads_curated_78",
        "file": "01_roads/mumbai_full_road_network.geojson",
        "ddl": """
            CREATE TABLE IF NOT EXISTS mufns_spatial_staging.staging_roads_curated_78 (
                road_id VARCHAR(64) PRIMARY KEY,
                name VARCHAR(255),
                highway VARCHAR(64),
                length_m DOUBLE PRECISION,
                surface VARCHAR(64),
                lanes INTEGER,
                bridge VARCHAR(16),
                tunnel VARCHAR(16),
                one_way VARCHAR(16),
                maxspeed DOUBLE PRECISION,
                access VARCHAR(64),
                ward_id VARCHAR(32),
                source TEXT,
                geometry GEOMETRY(LineString, 4326) NOT NULL,
                attributes JSONB DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_stg_roads_geom ON mufns_spatial_staging.staging_roads_curated_78 USING GIST (geometry);
        """,
        "map_row": lambda p, g: (
            p.get("road_id"), p.get("name"), p.get("highway"), float(p["length_m"]) if p.get("length_m") else None,
            p.get("surface"), int(p["lanes"]) if p.get("lanes") else None, p.get("bridge"), p.get("tunnel"),
            p.get("one_way"), float(p["maxspeed"]) if p.get("maxspeed") else None, p.get("access"),
            p.get("ward_id"), p.get("source"), json.dumps(g), json.dumps(p)
        ),
        "insert_sql": """
            INSERT INTO mufns_spatial_staging.staging_roads_curated_78 (
                road_id, name, highway, length_m, surface, lanes, bridge, tunnel,
                one_way, maxspeed, access, ward_id, source, geometry, attributes
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13,
                ST_SetSRID(ST_GeomFromGeoJSON($14), 4326), $15
            ) ON CONFLICT (road_id) DO NOTHING;
        """
    },
    {
        "table": "staging_drainage_network_39",
        "file": "02_drainage/mumbai_public_drainage_network.geojson",
        "ddl": """
            CREATE TABLE IF NOT EXISTS mufns_spatial_staging.staging_drainage_network_39 (
                drainage_id VARCHAR(64) PRIMARY KEY,
                name VARCHAR(255),
                drainage_type VARCHAR(64),
                length_m DOUBLE PRECISION,
                ward_id VARCHAR(32),
                source TEXT,
                source_date VARCHAR(64),
                confidence VARCHAR(32),
                geometry GEOMETRY(LineString, 4326) NOT NULL,
                attributes JSONB DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_stg_drn_geom ON mufns_spatial_staging.staging_drainage_network_39 USING GIST (geometry);
        """,
        "map_row": lambda p, g: (
            p.get("drainage_id"), p.get("name"), p.get("drainage_type"),
            float(p["length_m"]) if p.get("length_m") else None, p.get("ward_id"),
            p.get("source"), p.get("source_date"), p.get("confidence"),
            json.dumps(g), json.dumps(p)
        ),
        "insert_sql": """
            INSERT INTO mufns_spatial_staging.staging_drainage_network_39 (
                drainage_id, name, drainage_type, length_m, ward_id, source,
                source_date, confidence, geometry, attributes
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8,
                ST_SetSRID(ST_GeomFromGeoJSON($9), 4326), $10
            ) ON CONFLICT (drainage_id) DO NOTHING;
        """
    },
    {
        "table": "staging_drainage_structures_41",
        "file": "02_drainage/mumbai_drainage_structures.geojson",
        "ddl": """
            CREATE TABLE IF NOT EXISTS mufns_spatial_staging.staging_drainage_structures_41 (
                structure_id VARCHAR(64) PRIMARY KEY,
                structure_type VARCHAR(64),
                name VARCHAR(255),
                connected_drainage_id VARCHAR(64),
                ward_id VARCHAR(32),
                source TEXT,
                confidence VARCHAR(32),
                geometry GEOMETRY(Point, 4326) NOT NULL,
                attributes JSONB DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_stg_drn_str_geom ON mufns_spatial_staging.staging_drainage_structures_41 USING GIST (geometry);
        """,
        "map_row": lambda p, g: (
            p.get("structure_id"), p.get("structure_type"), p.get("name"),
            p.get("connected_drainage_id"), p.get("ward_id"), p.get("source"),
            p.get("confidence"), json.dumps(g), json.dumps(p)
        ),
        "insert_sql": """
            INSERT INTO mufns_spatial_staging.staging_drainage_structures_41 (
                structure_id, structure_type, name, connected_drainage_id, ward_id,
                source, confidence, geometry, attributes
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7,
                ST_SetSRID(ST_GeomFromGeoJSON($8), 4326), $9
            ) ON CONFLICT (structure_id) DO NOTHING;
        """
    },
    {
        "table": "staging_land_use_land_cover_69",
        "file": "03_land_cover/mumbai_land_use_land_cover.geojson",
        "ddl": """
            CREATE TABLE IF NOT EXISTS mufns_spatial_staging.staging_land_use_land_cover_69 (
                lulc_id VARCHAR(64) PRIMARY KEY,
                name VARCHAR(255),
                class VARCHAR(64),
                class_code INTEGER,
                area_m2 DOUBLE PRECISION,
                source TEXT,
                source_date VARCHAR(64),
                confidence VARCHAR(32),
                geometry GEOMETRY(Polygon, 4326) NOT NULL,
                attributes JSONB DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_stg_lulc_geom ON mufns_spatial_staging.staging_land_use_land_cover_69 USING GIST (geometry);
        """,
        "map_row": lambda p, g: (
            p.get("lulc_id"), p.get("name"), p.get("class"),
            int(p["class_code"]) if p.get("class_code") else None,
            float(p["area_m2"]) if p.get("area_m2") else None,
            p.get("source"), p.get("source_date"), p.get("confidence"),
            json.dumps(g), json.dumps(p)
        ),
        "insert_sql": """
            INSERT INTO mufns_spatial_staging.staging_land_use_land_cover_69 (
                lulc_id, name, class, class_code, area_m2, source, source_date,
                confidence, geometry, attributes
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8,
                ST_SetSRID(ST_GeomFromGeoJSON($9), 4326), $10
            ) ON CONFLICT (lulc_id) DO NOTHING;
        """
    },
    {
        "table": "staging_impervious_surface_128",
        "file": "03_land_cover/mumbai_impervious_surface.geojson",
        "ddl": """
            CREATE TABLE IF NOT EXISTS mufns_spatial_staging.staging_impervious_surface_128 (
                cell_id VARCHAR(64) PRIMARY KEY,
                impervious_fraction DOUBLE PRECISION,
                built_up_fraction DOUBLE PRECISION,
                source TEXT,
                confidence VARCHAR(32),
                geometry GEOMETRY(Polygon, 4326) NOT NULL,
                attributes JSONB DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_stg_imp_geom ON mufns_spatial_staging.staging_impervious_surface_128 USING GIST (geometry);
        """,
        "map_row": lambda p, g: (
            p.get("cell_id"), float(p["impervious_fraction"]) if p.get("impervious_fraction") is not None else None,
            float(p["built_up_fraction"]) if p.get("built_up_fraction") is not None else None,
            p.get("source"), p.get("confidence"),
            json.dumps(g), json.dumps(p)
        ),
        "insert_sql": """
            INSERT INTO mufns_spatial_staging.staging_impervious_surface_128 (
                cell_id, impervious_fraction, built_up_fraction, source,
                confidence, geometry, attributes
            ) VALUES (
                $1, $2, $3, $4, $5,
                ST_SetSRID(ST_GeomFromGeoJSON($6), 4326), $7
            ) ON CONFLICT (cell_id) DO NOTHING;
        """
    },
    {
        "table": "staging_flood_hotspots_35",
        "file": "04_flood_risk/mumbai_flood_hotspots.geojson",
        "ddl": """
            CREATE TABLE IF NOT EXISTS mufns_spatial_staging.staging_flood_hotspots_35 (
                hotspot_id VARCHAR(64) PRIMARY KEY,
                name VARCHAR(255),
                hotspot_type VARCHAR(64),
                evidence TEXT,
                source TEXT,
                source_url TEXT,
                confidence VARCHAR(32),
                recurrence VARCHAR(64),
                geometry GEOMETRY(Point, 4326) NOT NULL,
                attributes JSONB DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_stg_hotspots_geom ON mufns_spatial_staging.staging_flood_hotspots_35 USING GIST (geometry);
        """,
        "map_row": lambda p, g: (
            p.get("hotspot_id"), p.get("name"), p.get("hotspot_type"),
            p.get("evidence"), p.get("source"), p.get("source_url"),
            p.get("confidence"), p.get("recurrence"),
            json.dumps(g), json.dumps(p)
        ),
        "insert_sql": """
            INSERT INTO mufns_spatial_staging.staging_flood_hotspots_35 (
                hotspot_id, name, hotspot_type, evidence, source, source_url,
                confidence, recurrence, geometry, attributes
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8,
                ST_SetSRID(ST_GeomFromGeoJSON($9), 4326), $10
            ) ON CONFLICT (hotspot_id) DO NOTHING;
        """
    },
    {
        "table": "staging_low_lying_areas_15",
        "file": "04_flood_risk/mumbai_low_lying_areas.geojson",
        "ddl": """
            CREATE TABLE IF NOT EXISTS mufns_spatial_staging.staging_low_lying_areas_15 (
                area_id VARCHAR(64) PRIMARY KEY,
                name VARCHAR(255),
                type VARCHAR(64),
                elevation_min DOUBLE PRECISION,
                elevation_mean DOUBLE PRECISION,
                area_m2 DOUBLE PRECISION,
                source TEXT,
                confidence VARCHAR(32),
                geometry GEOMETRY(Polygon, 4326) NOT NULL,
                attributes JSONB DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_stg_low_geom ON mufns_spatial_staging.staging_low_lying_areas_15 USING GIST (geometry);
        """,
        "map_row": lambda p, g: (
            p.get("area_id"), p.get("name"), p.get("type"),
            float(p["elevation_min"]) if p.get("elevation_min") is not None else None,
            float(p["elevation_mean"]) if p.get("elevation_mean") is not None else None,
            float(p["area_m2"]) if p.get("area_m2") is not None else None,
            p.get("source"), p.get("confidence"),
            json.dumps(g), json.dumps(p)
        ),
        "insert_sql": """
            INSERT INTO mufns_spatial_staging.staging_low_lying_areas_15 (
                area_id, name, type, elevation_min, elevation_mean, area_m2,
                source, confidence, geometry, attributes
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8,
                ST_SetSRID(ST_GeomFromGeoJSON($9), 4326), $10
            ) ON CONFLICT (area_id) DO NOTHING;
        """
    },
    {
        "table": "staging_coastal_exposure_15",
        "file": "04_flood_risk/mumbai_coastal_exposure.geojson",
        "ddl": """
            CREATE TABLE IF NOT EXISTS mufns_spatial_staging.staging_coastal_exposure_15 (
                zone_id VARCHAR(64) PRIMARY KEY,
                name VARCHAR(255),
                zone_type VARCHAR(64),
                source TEXT,
                confidence VARCHAR(32),
                geometry GEOMETRY(Geometry, 4326) NOT NULL,
                attributes JSONB DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_stg_coast_geom ON mufns_spatial_staging.staging_coastal_exposure_15 USING GIST (geometry);
        """,
        "map_row": lambda p, g: (
            p.get("zone_id"), p.get("name"), p.get("zone_type"),
            p.get("source"), p.get("confidence"),
            json.dumps(g), json.dumps(p)
        ),
        "insert_sql": """
            INSERT INTO mufns_spatial_staging.staging_coastal_exposure_15 (
                zone_id, name, zone_type, source, confidence, geometry, attributes
            ) VALUES (
                $1, $2, $3, $4, $5,
                ST_SetSRID(ST_GeomFromGeoJSON($6), 4326), $7
            ) ON CONFLICT (zone_id) DO NOTHING;
        """
    },
    {
        "table": "staging_bridges_culverts_33",
        "file": "05_structures/mumbai_bridges_culverts.geojson",
        "ddl": """
            CREATE TABLE IF NOT EXISTS mufns_spatial_staging.staging_bridges_culverts_33 (
                structure_id VARCHAR(64) PRIMARY KEY,
                name VARCHAR(255),
                structure_type VARCHAR(64),
                road_name VARCHAR(255),
                waterway_name VARCHAR(255),
                source TEXT,
                confidence VARCHAR(32),
                geometry GEOMETRY(Point, 4326) NOT NULL,
                attributes JSONB DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_stg_brg_geom ON mufns_spatial_staging.staging_bridges_culverts_33 USING GIST (geometry);
        """,
        "map_row": lambda p, g: (
            p.get("structure_id"), p.get("name"), p.get("structure_type"),
            p.get("road_name"), p.get("waterway_name"), p.get("source"),
            p.get("confidence"), json.dumps(g), json.dumps(p)
        ),
        "insert_sql": """
            INSERT INTO mufns_spatial_staging.staging_bridges_culverts_33 (
                structure_id, name, structure_type, road_name, waterway_name,
                source, confidence, geometry, attributes
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7,
                ST_SetSRID(ST_GeomFromGeoJSON($8), 4326), $9
            ) ON CONFLICT (structure_id) DO NOTHING;
        """
    },
    {
        "table": "staging_green_open_spaces_25",
        "file": "06_green_infrastructure/mumbai_green_open_spaces.geojson",
        "ddl": """
            CREATE TABLE IF NOT EXISTS mufns_spatial_staging.staging_green_open_spaces_25 (
                area_id VARCHAR(64) PRIMARY KEY,
                name VARCHAR(255),
                type VARCHAR(64),
                area_m2 DOUBLE PRECISION,
                source TEXT,
                confidence VARCHAR(32),
                geometry GEOMETRY(Polygon, 4326) NOT NULL,
                attributes JSONB DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_stg_grn_geom ON mufns_spatial_staging.staging_green_open_spaces_25 USING GIST (geometry);
        """,
        "map_row": lambda p, g: (
            p.get("area_id"), p.get("name"), p.get("type"),
            float(p["area_m2"]) if p.get("area_m2") is not None else None,
            p.get("source"), p.get("confidence"),
            json.dumps(g), json.dumps(p)
        ),
        "insert_sql": """
            INSERT INTO mufns_spatial_staging.staging_green_open_spaces_25 (
                area_id, name, type, area_m2, source, confidence, geometry, attributes
            ) VALUES (
                $1, $2, $3, $4, $5, $6,
                ST_SetSRID(ST_GeomFromGeoJSON($7), 4326), $8
            ) ON CONFLICT (area_id) DO NOTHING;
        """
    }
]

async def ingest_staging():
    print("=================================================================")
    print("   INGESTING SPARK SPATIAL PACKAGE INTO POSTGIS STAGING SCHEMA   ")
    print("=================================================================\n")
    
    conn = await asyncpg.connect(CLEAN_URL, ssl=SSL_CTX)
    await conn.execute("CREATE SCHEMA IF NOT EXISTS mufns_spatial_staging;")
    
    summary = {}
    
    for item in STAGING_TABLES:
        tname = item["table"]
        fpath = SPARK_DIR / item["file"]
        print(f"Loading {tname} from {fpath}...")
        
        # 1. Execute DDL
        await conn.execute(item["ddl"])
        await conn.execute(f"TRUNCATE TABLE mufns_spatial_staging.{tname};")
        
        # 2. Parse GeoJSON
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        features = data.get("features", [])
        rows = []
        for feat in features:
            geom = feat.get("geometry")
            props = feat.get("properties", {})
            if geom:
                row = item["map_row"](props, geom)
                rows.append(row)
                
        # 3. Batch insert
        if rows:
            await conn.executemany(item["insert_sql"], rows)
            
        count = await conn.fetchval(f"SELECT count(*) FROM mufns_spatial_staging.{tname};")
        summary[tname] = count
        print(f"  -> Ingested {count:,}/{len(features):,} features into mufns_spatial_staging.{tname}")
        
    print("\n=== STAGING SCHEMA INGESTION SUMMARY ===")
    for tbl, cnt in summary.items():
        print(f"  {tbl:<35}: {cnt:>5} rows")
        
    await conn.close()

if __name__ == "__main__":
    asyncio.run(ingest_staging())
