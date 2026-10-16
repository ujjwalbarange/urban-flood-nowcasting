"""Ingestion of 2024-2025 MOSDAC INSAT-3DR Satellite Rainfall Data into PostGIS.

Populates public.satellite_rainfall_observations with 1,073 verified granules:
- 644 HEM (Hydro-Estimator Method) granules (Primary)
- 429 IMC (IMAGER Retrieval) granules (Secondary/Validation)

Preserves raster geometry (EPSG:4326), grid arrays (28x28), statistics, hashes,
provenance, core Mumbai subsets, and event classifications.
"""

import os
import ssl
import json
import uuid
import asyncio
from datetime import datetime, timezone
from pathlib import Path
import asyncpg
import rasterio
import numpy as np
from dotenv import load_dotenv

load_dotenv()
RAW_URL = os.environ.get("DATABASE_URL", "")
CLEAN_URL = RAW_URL.replace("postgresql+asyncpg://", "postgresql://").split("?")[0]

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

AUDIT_JSON = Path("data/metadata/mosdac_insat_audit_report.json")
CANONICAL_DIR = Path("data/processed/rainfall/insat3dr")

async def init_table(conn: asyncpg.Connection):
    """Create satellite_rainfall_observations table and indexes."""
    print("Creating public.satellite_rainfall_observations table...", flush=True)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS public.satellite_rainfall_observations (
            observation_id VARCHAR(100) PRIMARY KEY,
            satellite VARCHAR(50) NOT NULL,
            sensor VARCHAR(50) NOT NULL,
            product VARCHAR(50) NOT NULL,
            product_level VARCHAR(50) NOT NULL,
            product_description TEXT,
            observation_time TIMESTAMPTZ NOT NULL,
            year INTEGER NOT NULL,
            event_name VARCHAR(150),
            geometry GEOMETRY(Polygon, 4326),
            raster_width INTEGER NOT NULL,
            raster_height INTEGER NOT NULL,
            spatial_resolution_deg DOUBLE PRECISION NOT NULL,
            spatial_resolution_km DOUBLE PRECISION NOT NULL,
            min_value DOUBLE PRECISION,
            max_value DOUBLE PRECISION,
            mean_value DOUBLE PRECISION,
            std_value DOUBLE PRECISION,
            p50_value DOUBLE PRECISION,
            p90_value DOUBLE PRECISION,
            p99_value DOUBLE PRECISION,
            valid_pixel_count INTEGER NOT NULL,
            total_pixel_count INTEGER NOT NULL,
            nodata_value DOUBLE PRECISION NOT NULL,
            nodata_pixel_count INTEGER NOT NULL,
            mumbai_core_max_value DOUBLE PRECISION,
            mumbai_core_mean_value DOUBLE PRECISION,
            unit VARCHAR(20) DEFAULT 'mm/hr',
            source VARCHAR(100) DEFAULT 'ISRO MOSDAC',
            source_file TEXT NOT NULL,
            canonical_file_path TEXT NOT NULL,
            file_hash VARCHAR(64) NOT NULL,
            file_size_bytes BIGINT NOT NULL,
            grid_data JSONB,
            attributes JSONB,
            ingestion_run_id UUID,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_sat_rain_obs_geom 
            ON public.satellite_rainfall_observations USING GIST (geometry);
        CREATE INDEX IF NOT EXISTS idx_sat_rain_obs_time 
            ON public.satellite_rainfall_observations USING btree (observation_time);
        CREATE INDEX IF NOT EXISTS idx_sat_rain_obs_prod_time 
            ON public.satellite_rainfall_observations USING btree (product, observation_time);
        CREATE INDEX IF NOT EXISTS idx_sat_rain_obs_prod_year 
            ON public.satellite_rainfall_observations USING btree (product, year);
        CREATE INDEX IF NOT EXISTS idx_sat_rain_obs_event 
            ON public.satellite_rainfall_observations USING btree (event_name);
    """)
    print("Table and indexes initialized.", flush=True)

async def ingest_mosdac():
    conn = await asyncpg.connect(CLEAN_URL, ssl=SSL_CTX)
    await init_table(conn)

    with open(AUDIT_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = data["records"]
    print(f"\nIngesting {len(records)} MOSDAC records into PostGIS...", flush=True)

    ingestion_run_id = uuid.uuid4()
    
    # Register in data_sources if not present
    await conn.execute("""
        INSERT INTO public.data_sources (
            source_id, provider_name, provider_type, description, url,
            license, spatial_resolution, temporal_resolution, crs, status, last_successful_fetch
        ) VALUES (
            'isro_mosdac_insat3dr',
            'ISRO Space Applications Centre (SAC)',
            'satellite',
            'INSAT-3DR Imager Level-2B Hydro-Estimator Method (HEM) and IMAGER Precipitation Retrieval (IMC)',
            'https://mosdac.gov.in',
            'Government of India Open Access',
            '0.036177 deg (~4.0 km)',
            'Half-hourly',
            'EPSG:4326',
            'active',
            CURRENT_TIMESTAMP
        ) ON CONFLICT (source_id) DO UPDATE SET 
            status = 'active', 
            last_successful_fetch = CURRENT_TIMESTAMP;
    """)

    # Log run in data_ingestion_runs
    await conn.execute("""
        INSERT INTO public.data_ingestion_runs (
            run_id, pipeline_name, source_id, records_ingested, records_failed, status, started_at
        ) VALUES ($1, 'mosdac_insat3dr_rainfall_ingestion', 'isro_mosdac_insat3dr', 0, 0, 'RUNNING', CURRENT_TIMESTAMP);
    """, ingestion_run_id)

    # Truncate table to ensure idempotent reload
    await conn.execute("TRUNCATE TABLE public.satellite_rainfall_observations;")

    batch_size = 100
    rows = []
    
    for idx, r in enumerate(records):
        prod = r["product"]
        obs_dt = datetime.fromisoformat(r["observation_time"])
        ts_slug = obs_dt.strftime("%Y%m%d_%H%M")
        obs_id = f"INSAT3DR_{prod}_{ts_slug}"
        
        prod_desc = (
            "INSAT-3DR Level-2B Hydro-Estimator Method (HEM) Precipitation Rate (Primary)"
            if prod == "HEM" else
            "INSAT-3DR Level-2B IMAGER Precipitation Retrieval (IMC) (Secondary/Validation)"
        )
        
        canonical_rel = f"data/processed/rainfall/insat3dr/{prod}/{r['year']}/{r['file_name']}"
        canonical_full = Path(canonical_rel)
        
        # Read the 28x28 raster data
        if canonical_full.exists():
            with rasterio.open(canonical_full) as src:
                arr = src.read(1)
                # Mask negative nodata values
                clean_arr = np.where(arr >= 0.0, np.round(arr, 3), -999.0)
                grid_list = clean_arr.tolist()
        else:
            grid_list = None
            
        b = r["bounds"]  # [left, bottom, right, top]
        # Polygon envelope WKT
        envelope_wkt = f"SRID=4326;POLYGON(({b[0]} {b[1]}, {b[2]} {b[1]}, {b[2]} {b[3]}, {b[0]} {b[3]}, {b[0]} {b[1]}))"
        
        attrs = {
            "version": "V01R00",
            "resolution_deg": r["resolution_deg"],
            "resolution_km": 4.0,
            "bounds": b,
            "percentiles": {
                "p50": r["p50_mm_hr"],
                "p90": r["p90_mm_hr"],
                "p99": r["p99_mm_hr"]
            }
        }
        
        row = (
            obs_id,
            "INSAT-3DR",
            "IMAGER",
            prod,
            "L2B",
            prod_desc,
            obs_dt,
            r["year"],
            r["event_name"],
            envelope_wkt,
            r["dimensions"][0],
            r["dimensions"][1],
            r["resolution_deg"],
            4.0,
            r["min_mm_hr"],
            r["max_mm_hr"],
            r["mean_mm_hr"],
            r["std_mm_hr"],
            r["p50_mm_hr"],
            r["p90_mm_hr"],
            r["p99_mm_hr"],
            r["valid_pixels"],
            r["total_pixels"],
            r["nodata_value"],
            r["nodata_pixels"],
            r["mumbai_core_max_mm_hr"],
            r["mumbai_core_mean_mm_hr"],
            "mm/hr",
            "ISRO MOSDAC",
            r["relative_path"],
            canonical_rel,
            r["file_hash_sha256"],
            r["file_size_bytes"],
            json.dumps(grid_list) if grid_list else None,
            json.dumps(attrs),
            ingestion_run_id
        )
        rows.append(row)
        
        if len(rows) >= batch_size:
            await insert_batch(conn, rows)
            print(f"  Ingested {idx + 1}/{len(records)} records...", flush=True)
            rows = []

    if rows:
        await insert_batch(conn, rows)
        print(f"  Ingested {len(records)}/{len(records)} records.", flush=True)

    # Update ingestion run status
    await conn.execute("""
        UPDATE public.data_ingestion_runs
        SET status = 'SUCCESS', records_ingested = $2, completed_at = CURRENT_TIMESTAMP, log_summary = $3
        WHERE run_id = $1;
    """, ingestion_run_id, len(records), json.dumps({
        "records_ingested": len(records),
        "products": {"HEM": sum(1 for r in records if r["product"] == "HEM"), "IMC": sum(1 for r in records if r["product"] == "IMC")},
        "years": {"2024": sum(1 for r in records if r["year"] == 2024), "2025": sum(1 for r in records if r["year"] == 2025)}
    }))

    # Verify count
    total_cnt = await conn.fetchval("SELECT count(*) FROM public.satellite_rainfall_observations;")
    hem_cnt = await conn.fetchval("SELECT count(*) FROM public.satellite_rainfall_observations WHERE product = 'HEM';")
    imc_cnt = await conn.fetchval("SELECT count(*) FROM public.satellite_rainfall_observations WHERE product = 'IMC';")
    print(f"\n=================================================================")
    print(f"  INGESTION SUCCESSFUL: {total_cnt} total records in PostGIS")
    print(f"    - HEM (Primary): {hem_cnt} records")
    print(f"    - IMC (Secondary): {imc_cnt} records")
    print(f"=================================================================\n", flush=True)

    await conn.close()

async def insert_batch(conn: asyncpg.Connection, rows: list):
    """Insert batch of records with geometry casting."""
    await conn.executemany("""
        INSERT INTO public.satellite_rainfall_observations (
            observation_id, satellite, sensor, product, product_level,
            product_description, observation_time, year, event_name,
            geometry, raster_width, raster_height, spatial_resolution_deg,
            spatial_resolution_km, min_value, max_value, mean_value,
            std_value, p50_value, p90_value, p99_value, valid_pixel_count,
            total_pixel_count, nodata_value, nodata_pixel_count,
            mumbai_core_max_value, mumbai_core_mean_value, unit,
            source, source_file, canonical_file_path, file_hash,
            file_size_bytes, grid_data, attributes, ingestion_run_id
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9,
            ST_GeomFromEWKT($10), $11, $12, $13, $14, $15, $16, $17,
            $18, $19, $20, $21, $22, $23, $24, $25,
            $26, $27, $28, $29, $30, $31, $32,
            $33, $34::jsonb, $35::jsonb, $36
        );
    """, rows)

if __name__ == "__main__":
    asyncio.run(ingest_mosdac())
