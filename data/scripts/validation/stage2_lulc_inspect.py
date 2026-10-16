"""Quick LULC and impervious check — with retry for transient Aiven connectivity."""
import asyncio, os, ssl, time
from pathlib import Path
from dotenv import load_dotenv

_root = Path(__file__).resolve().parent
for _ in range(10):
    if (_root / ".env").exists(): break
    _root = _root.parent
load_dotenv(_root / ".env")

async def connect_with_retry(url, ctx, max_retries=3, delay=5):
    import asyncpg
    for attempt in range(max_retries):
        try:
            conn = await asyncpg.connect(url, ssl=ctx, timeout=15)
            return conn
        except (ConnectionRefusedError, OSError) as e:
            if attempt < max_retries - 1:
                print(f"  Connection attempt {attempt+1} failed, retrying in {delay}s...")
                await asyncio.sleep(delay)
            else:
                raise

async def main():
    import asyncpg
    raw = os.environ.get("DATABASE_URL", "")
    url = raw.replace("postgresql+asyncpg://", "postgresql://").split("?")[0]
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    conn = await connect_with_retry(url, ctx)

    # LULC
    print("=== LULC CLASSES ===")
    rows = await conn.fetch("""
        SELECT class, class_code, name, area_m2, source, confidence
        FROM land_use_land_cover ORDER BY area_m2 DESC NULLS LAST
    """)
    for r in rows:
        area = (r['area_m2'] or 0) / 1e6
        print(f"  code={r['class_code'] or '?':<6} class={r['class'] or '?':<30} area={area:.2f}km2 conf={r['confidence']}")

    # Impervious
    print("\n=== IMPERVIOUS SURFACE GRID ===")
    stats = await conn.fetchrow("""
        SELECT count(*) as cnt, 
               min(impervious_fraction) as min_imp, max(impervious_fraction) as max_imp,
               avg(impervious_fraction) as avg_imp
        FROM impervious_surface_grid
    """)
    print(f"  cells={stats['cnt']} imp=[{stats['min_imp']:.3f}-{stats['max_imp']:.3f}] avg={stats['avg_imp']:.3f}")
    
    bbox = await conn.fetchrow("SELECT ST_Extent(geometry)::text as ext FROM impervious_surface_grid")
    print(f"  bbox={bbox['ext']}")

    # All drainage nodes
    print("\n=== ALL DRAINAGE NODES ===")
    rows = await conn.fetch("""
        SELECT node_id, node_type, invert_elevation_m, ground_elevation_m, data_quality,
               ST_X(geometry) as lon, ST_Y(geometry) as lat
        FROM drainage_nodes ORDER BY node_id
    """)
    for r in rows:
        print(f"  {r['node_id']:<18} type={r['node_type']:<15} inv={r['invert_elevation_m']:>6.1f}m gnd={r['ground_elevation_m']:>6.1f}m q={r['data_quality']}")

    await conn.close()

asyncio.run(main())
