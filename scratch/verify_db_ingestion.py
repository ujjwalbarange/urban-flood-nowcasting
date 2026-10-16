import os
import ssl
import asyncio
import asyncpg
from dotenv import load_dotenv

load_dotenv()
RAW_URL = os.environ.get("DATABASE_URL", "")
CLEAN_URL = RAW_URL.replace("postgresql+asyncpg://", "postgresql://").split("?")[0]
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

async def main():
    conn = await asyncpg.connect(CLEAN_URL, ssl=SSL_CTX)
    total = await conn.fetchval("SELECT count(*) FROM public.satellite_rainfall_observations;")
    valid_geoms = await conn.fetchval("SELECT count(*) FROM public.satellite_rainfall_observations WHERE ST_IsValid(geometry);")
    srid = await conn.fetchval("SELECT ST_SRID(geometry) FROM public.satellite_rainfall_observations LIMIT 1;")
    
    breakdown = await conn.fetch("""
        SELECT product, year, event_name, count(*) as count,
               round(min(min_value)::numeric, 2) as min_rain,
               round(max(max_value)::numeric, 2) as max_rain,
               round(avg(mean_value)::numeric, 3) as avg_mean_rain,
               min(observation_time) as earliest,
               max(observation_time) as latest
        FROM public.satellite_rainfall_observations
        GROUP BY product, year, event_name
        ORDER BY product, year, earliest;
    """)
    print(f"Total records: {total} | Valid Geometries: {valid_geoms}/{total} | SRID: {srid}\n")
    print(f"{'Product':<6} | {'Year':<5} | {'Count':<6} | {'Max (mm/h)':<10} | {'Avg Mean':<9} | {'Earliest':<20} | {'Latest':<20} | Event")
    print("-" * 115)
    for b in breakdown:
        e_str = b["earliest"].strftime("%Y-%m-%d %H:%M")
        l_str = b["latest"].strftime("%Y-%m-%d %H:%M")
        print(f"{b['product']:<6} | {b['year']:<5} | {b['count']:<6} | {b['max_rain']:<10} | {b['avg_mean_rain']:<9} | {e_str:<20} | {l_str:<20} | {b['event_name']}")
    
    # Check data_ingestion_runs
    run_log = await conn.fetchrow("""
        SELECT run_id, pipeline_name, source_id, records_ingested, status, started_at, completed_at, log_summary
        FROM public.data_ingestion_runs
        WHERE pipeline_name = 'mosdac_insat3dr_rainfall_ingestion'
        ORDER BY started_at DESC LIMIT 1;
    """)
    print("\nData Ingestion Run Log:")
    print(" ", dict(run_log))
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
