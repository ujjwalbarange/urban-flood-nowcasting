import asyncio
import os
import ssl
import json
from datetime import datetime
import asyncpg
from dotenv import load_dotenv

load_dotenv()
RAW_URL = os.environ.get("DATABASE_URL", "")
CLEAN_URL = RAW_URL.replace("postgresql+asyncpg://", "postgresql://").split("?")[0]

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

async def run_deep_audit():
    conn = await asyncpg.connect(CLEAN_URL, ssl=SSL_CTX)
    audit = {}
    
    # 1. DB Name and Versions
    db_name = await conn.fetchval("SELECT current_database()")
    pg_version = await conn.fetchval("SELECT version()")
    postgis_ver = await conn.fetchval("SELECT PostGIS_Full_Version()")
    
    audit["database_name"] = db_name
    audit["postgres_version"] = pg_version
    audit["postgis_version"] = postgis_ver
    
    # 2. All tables in public schema
    table_rows = await conn.fetch("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """)
    tables = [r["table_name"] for r in table_rows]
    audit["total_tables_count"] = len(tables)
    audit["table_names"] = tables
    
    # 3. Exact row counts and column definitions for every table
    table_details = {}
    for t in tables:
        count = await conn.fetchval(f'SELECT count(*) FROM "{t}"')
        
        # Columns
        cols_rows = await conn.fetch("""
            SELECT column_name, data_type, udt_name, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = $1
            ORDER BY ordinal_position;
        """, t)
        cols = [{
            "column_name": r["column_name"],
            "data_type": r["data_type"],
            "udt_name": r["udt_name"],
            "is_nullable": r["is_nullable"],
            "column_default": r["column_default"]
        } for r in cols_rows]
        
        # Constraints (PK, FK, Unique)
        constraints_rows = await conn.fetch("""
            SELECT tc.constraint_name, tc.constraint_type, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
              AND tc.table_schema = kcu.table_schema
            WHERE tc.table_schema = 'public' AND tc.table_name = $1;
        """, t)
        constraints = [{
            "name": r["constraint_name"],
            "type": r["constraint_type"],
            "column": r["column_name"]
        } for r in constraints_rows]
        
        # Indexes
        idx_rows = await conn.fetch("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public' AND tablename = $1;
        """, t)
        indexes = [{
            "name": r["indexname"],
            "def": r["indexdef"]
        } for r in idx_rows]
        
        # Check if table has geometry column
        geom_info = await conn.fetch("""
            SELECT f_geometry_column, coord_dimension, srid, type
            FROM geometry_columns
            WHERE f_table_schema = 'public' AND f_table_name = $1;
        """, t)
        geoms = [{
            "column": r["f_geometry_column"],
            "dimension": r["coord_dimension"],
            "srid": r["srid"],
            "type": r["type"]
        } for r in geom_info]
        
        table_details[t] = {
            "row_count": count,
            "columns_count": len(cols),
            "columns": cols,
            "constraints": constraints,
            "indexes": indexes,
            "geometries": geoms
        }
    
    audit["tables"] = table_details
    
    # 4. Specific deep queries on key tables
    # Wards
    audit["wards_audit"] = {
        "count": await conn.fetchval("SELECT count(*) FROM wards"),
        "distinct_ward_ids": await conn.fetchval("SELECT count(DISTINCT ward_id) FROM wards"),
        "names": [r["name"] for r in await conn.fetch("SELECT name FROM wards ORDER BY name")],
        "total_pop": await conn.fetchval("SELECT sum(population) FROM wards"),
        "extent": await conn.fetchval("SELECT ST_AsText(ST_Extent(geometry)) FROM wards"),
        "invalid_geoms": await conn.fetchval("SELECT count(*) FROM wards WHERE NOT ST_IsValid(geometry)")
    }
    
    # Historical Flood Events
    audit["historical_events_audit"] = {
        "count": await conn.fetchval("SELECT count(*) FROM historical_flood_events"),
        "distinct_event_ids": await conn.fetchval("SELECT count(DISTINCT event_id) FROM historical_flood_events"),
        "min_year": await conn.fetchval("SELECT min(year) FROM historical_flood_events"),
        "max_year": await conn.fetchval("SELECT max(year) FROM historical_flood_events"),
        "min_date": str(await conn.fetchval("SELECT min(date) FROM historical_flood_events")),
        "max_date": str(await conn.fetchval("SELECT max(date) FROM historical_flood_events")),
        "measured_depth_count": await conn.fetchval("SELECT count(*) FROM historical_flood_events WHERE flood_depth_cm IS NOT NULL"),
        "min_depth": await conn.fetchval("SELECT min(flood_depth_cm) FROM historical_flood_events"),
        "max_depth": await conn.fetchval("SELECT max(flood_depth_cm) FROM historical_flood_events"),
        "avg_depth": await conn.fetchval("SELECT avg(flood_depth_cm) FROM historical_flood_events"),
        "extent": await conn.fetchval("SELECT ST_AsText(ST_Extent(location)) FROM historical_flood_events"),
        "null_locations": await conn.fetchval("SELECT count(*) FROM historical_flood_events WHERE location IS NULL"),
        "invalid_geoms": await conn.fetchval("SELECT count(*) FROM historical_flood_events WHERE location IS NOT NULL AND NOT ST_IsValid(location)")
    }
    
    # Weather Forecasts
    audit["weather_forecasts_audit"] = {
        "count": await conn.fetchval("SELECT count(*) FROM weather_forecasts"),
        "stations": [r["station_id"] for r in await conn.fetch("SELECT DISTINCT station_id FROM weather_forecasts ORDER BY station_id")],
        "variables": [r["variable"] for r in await conn.fetch("SELECT DISTINCT variable FROM weather_forecasts ORDER BY variable")],
        "min_lead_m": await conn.fetchval("SELECT min(lead_minutes) FROM weather_forecasts"),
        "max_lead_m": await conn.fetchval("SELECT max(lead_minutes) FROM weather_forecasts"),
        "min_lead_h": await conn.fetchval("SELECT min(lead_hours) FROM weather_forecasts"),
        "max_lead_h": await conn.fetchval("SELECT max(lead_hours) FROM weather_forecasts"),
        "min_valid": str(await conn.fetchval("SELECT min(forecast_valid_time) FROM weather_forecasts")),
        "max_valid": str(await conn.fetchval("SELECT max(forecast_valid_time) FROM weather_forecasts")),
        "min_generated": str(await conn.fetchval("SELECT min(forecast_generated_at) FROM weather_forecasts")),
        "null_values": await conn.fetchval("SELECT count(*) FROM weather_forecasts WHERE value IS NULL")
    }
    
    # Weather Observations
    audit["weather_observations_audit"] = {
        "count": await conn.fetchval("SELECT count(*) FROM weather_observations"),
        "stations": [r["station_id"] for r in await conn.fetch("SELECT DISTINCT station_id FROM weather_observations ORDER BY station_id")],
        "variables": [r["variable"] for r in await conn.fetch("SELECT DISTINCT variable FROM weather_observations ORDER BY variable")],
        "min_time": str(await conn.fetchval("SELECT min(timestamp) FROM weather_observations")),
        "max_time": str(await conn.fetchval("SELECT max(timestamp) FROM weather_observations")),
        "null_values": await conn.fetchval("SELECT count(*) FROM weather_observations WHERE value IS NULL")
    }
    
    # Water Bodies
    audit["water_bodies_audit"] = {
        "count": await conn.fetchval("SELECT count(*) FROM water_bodies"),
        "types": [{ "type": r["feature_type"], "count": r["c"] } for r in await conn.fetch("SELECT feature_type, count(*) as c FROM water_bodies GROUP BY feature_type ORDER BY c DESC")],
        "extent": await conn.fetchval("SELECT ST_AsText(ST_Extent(geometry)) FROM water_bodies"),
        "null_geoms": await conn.fetchval("SELECT count(*) FROM water_bodies WHERE geometry IS NULL"),
        "invalid_geoms": await conn.fetchval("SELECT count(*) FROM water_bodies WHERE geometry IS NOT NULL AND NOT ST_IsValid(geometry)")
    }
    
    # Critical Infrastructure
    audit["critical_infrastructure_audit"] = {
        "count": await conn.fetchval("SELECT count(*) FROM critical_infrastructure"),
        "categories": [{ "cat": r["category"], "count": r["c"] } for r in await conn.fetch("SELECT category, count(*) as c FROM critical_infrastructure GROUP BY category ORDER BY c DESC")],
        "extent": await conn.fetchval("SELECT ST_AsText(ST_Extent(location)) FROM critical_infrastructure"),
        "null_locations": await conn.fetchval("SELECT count(*) FROM critical_infrastructure WHERE location IS NULL"),
        "invalid_geoms": await conn.fetchval("SELECT count(*) FROM critical_infrastructure WHERE location IS NOT NULL AND NOT ST_IsValid(location)")
    }
    
    # Tide Observations
    audit["tide_observations_audit"] = {
        "count": await conn.fetchval("SELECT count(*) FROM tide_observations"),
        "stations": [r["station_name"] for r in await conn.fetch("SELECT DISTINCT station_name FROM tide_observations")],
        "min_height": await conn.fetchval("SELECT min(tide_height_m) FROM tide_observations"),
        "max_height": await conn.fetchval("SELECT max(tide_height_m) FROM tide_observations"),
        "avg_height": await conn.fetchval("SELECT avg(tide_height_m) FROM tide_observations"),
        "min_time": str(await conn.fetchval("SELECT min(timestamp) FROM tide_observations")),
        "max_time": str(await conn.fetchval("SELECT max(timestamp) FROM tide_observations"))
    }
    
    # DEM tiles
    audit["dem_tiles_audit"] = {
        "count": await conn.fetchval("SELECT count(*) FROM dem_tiles"),
        "rows": [{
            "product_name": r["product_name"],
            "resolution_m": r["resolution_m"],
            "width": r["width"],
            "height": r["height"],
            "storage_path": r["storage_path"],
            "min_elevation_m": r["min_elevation_m"],
            "max_elevation_m": r["max_elevation_m"],
            "mean_elevation_m": r["mean_elevation_m"],
            "source_url": r["source_url"]
        } for r in await conn.fetch("SELECT product_name, resolution_m, width, height, storage_path, min_elevation_m, max_elevation_m, mean_elevation_m, source_url FROM dem_tiles")]
    }
    
    # Terrain derivatives
    audit["terrain_derivatives_audit"] = {
        "count": await conn.fetchval("SELECT count(*) FROM terrain_derivatives"),
        "rows": [{
            "derivative_type": r["derivative_type"],
            "storage_path": r["storage_path"],
            "min_value": r["min_value"],
            "max_value": r["max_value"],
            "mean_value": r["mean_value"],
            "parameters": r["parameters"]
        } for r in await conn.fetch("SELECT derivative_type, storage_path, min_value, max_value, mean_value, parameters FROM terrain_derivatives")]
    }
    
    # Ingestion Runs
    audit["data_ingestion_runs_audit"] = {
        "count": await conn.fetchval("SELECT count(*) FROM data_ingestion_runs"),
        "runs": [{
            "run_id": str(r["run_id"]),
            "pipeline_name": r["pipeline_name"],
            "source_id": r["source_id"],
            "records_ingested": r["records_ingested"],
            "status": r["status"],
            "started_at": str(r["started_at"]),
            "completed_at": str(r["completed_at"]),
            "log_summary": r["log_summary"]
        } for r in await conn.fetch("SELECT run_id, pipeline_name, source_id, records_ingested, status, started_at, completed_at, log_summary FROM data_ingestion_runs")]
    }

    await conn.close()
    
    with open("data/scripts/validation/db_deep_audit_results.json", "w", encoding="utf-8") as f:
        json.dump(audit, f, indent=2, default=str)
    print("Database deep audit complete! Results saved to data/scripts/validation/db_deep_audit_results.json")

if __name__ == "__main__":
    asyncio.run(run_deep_audit())
