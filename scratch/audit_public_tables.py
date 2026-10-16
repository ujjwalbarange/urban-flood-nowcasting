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
    tables = await conn.fetch("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE' AND table_name != 'spatial_ref_sys'
        ORDER BY table_name;
    """)
    print(f"Total production tables in public: {len(tables)}\n")
    print(f"{'Table Name':<32} | {'Row Count':<10} | {'Geom Column / Type':<30}")
    print("-" * 78)
    total_features = 0
    for t in tables:
        tname = t["table_name"]
        cnt = await conn.fetchval(f"SELECT count(*) FROM public.\"{tname}\";")
        
        # Check geometry
        geom_info = await conn.fetchrow(f"""
            SELECT f_geometry_column, type, srid 
            FROM geometry_columns 
            WHERE f_table_schema = 'public' AND f_table_name = '{tname}';
        """)
        if geom_info:
            g_str = f"{geom_info['f_geometry_column']} ({geom_info['type']}, {geom_info['srid']})"
        else:
            # Check geography or other
            g_str = "None (Tabular/Raster ref)"
        print(f"{tname:<32} | {cnt:<10} | {g_str:<30}")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
