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
    cols = await conn.fetch("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = 'flood_hotspots'
        ORDER BY ordinal_position;
    """)
    print("Columns in flood_hotspots:")
    for c in cols:
        print(f"  {c['column_name']}: {c['data_type']}")
    rows = await conn.fetch("SELECT * FROM public.flood_hotspots;")
    print(f"Total rows: {len(rows)}")
    for r in rows[:5]:
        print(" ", dict(r))
        
    print("\nColumns in staging_flood_hotspots_35:")
    cols_stg = await conn.fetch("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_schema = 'mufns_spatial_staging' AND table_name = 'staging_flood_hotspots_35'
        ORDER BY ordinal_position;
    """)
    for c in cols_stg:
        print(f"  {c['column_name']}: {c['data_type']}")
    rows_stg = await conn.fetch("SELECT * FROM mufns_spatial_staging.staging_flood_hotspots_35 LIMIT 3;")
    for r in rows_stg:
        print(" ", dict(r))
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
