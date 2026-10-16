import asyncio
import os
import ssl
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

    tables = [
        "road_segments",
        "buildings",
        "population_grids",
        "critical_infrastructure",
        "shelters",
        "flood_hotspots",
        "wards",
        "water_bodies",
        "pumping_stations",
    ]

    print("Checking exposure tables schema and row counts:")
    for t in tables:
        cnt = await conn.fetchval(f"SELECT count(*) FROM public.{t};")
        cols = await conn.fetch("""
            SELECT column_name, udt_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = $1
            ORDER BY ordinal_position;
        """, t)
        geom_cols = [c['column_name'] for c in cols if 'geometry' in c['udt_name'] or 'geom' in c['column_name']]
        print(f"\nTable: {t:<25} | Rows: {cnt:<8} | Geom cols: {geom_cols}")
        print("  Key columns:", [c['column_name'] for c in cols[:6]])

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
