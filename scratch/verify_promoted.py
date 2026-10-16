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
    tables = [
        "critical_arterial_corridors",
        "road_segments",
        "primary_drainage_network",
        "drainage_structures",
        "land_use_land_cover",
        "impervious_surface_grid",
        "flood_hotspots",
        "flood_hotspots_v1_legacy",
        "low_lying_areas",
        "coastal_exposure_zones",
        "bridges_and_culverts",
        "green_open_spaces"
    ]
    print(f"{'Table Name':<30} | {'Count':<8} | {'SRID':<6} | {'Valid Geoms':<12}")
    print("-" * 65)
    for t in tables:
        cnt = await conn.fetchval(f"SELECT count(*) FROM public.{t};")
        # Find geom column
        geom_col = await conn.fetchval(f"""
            SELECT f_geometry_column 
            FROM geometry_columns 
            WHERE f_table_schema = 'public' AND f_table_name = '{t}';
        """)
        if not geom_col:
            # Check if column is 'geometry' or 'location'
            has_geom = await conn.fetchval(f"""
                SELECT column_name FROM information_schema.columns 
                WHERE table_schema = 'public' AND table_name = '{t}' AND column_name IN ('geometry', 'location');
            """)
            geom_col = has_geom
            
        if geom_col:
            srid = await conn.fetchval(f"SELECT ST_SRID({geom_col}) FROM public.{t} WHERE {geom_col} IS NOT NULL LIMIT 1;")
            valid_cnt = await conn.fetchval(f"SELECT count(*) FROM public.{t} WHERE ST_IsValid({geom_col});")
            print(f"{t:<30} | {cnt:<8} | {srid or 'N/A':<6} | {valid_cnt}/{cnt} valid")
        else:
            print(f"{t:<30} | {cnt:<8} | N/A    | N/A")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
