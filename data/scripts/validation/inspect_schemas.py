"""Inspect actual column schemas for key tables to reconcile ORM models."""
import asyncio, os, ssl, json
from pathlib import Path
from dotenv import load_dotenv

_root = Path(__file__).resolve().parent
for _ in range(10):
    if (_root / ".env").exists(): break
    _root = _root.parent
load_dotenv(_root / ".env")

async def main():
    import asyncpg
    raw = os.environ.get("DATABASE_URL", "")
    url = raw.replace("postgresql+asyncpg://", "postgresql://").split("?")[0]
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    conn = await asyncpg.connect(url, ssl=ctx)

    tables = [
        "wards", "road_segments", "impervious_surface_grid", "population_grids",
        "weather_forecasts", "water_bodies", "primary_drainage_network",
        "drainage_structures", "drainage_nodes", "drainage_links",
        "terrain_derivatives", "dem_tiles", "land_use_land_cover",
        "tide_observations", "historical_flood_events", "flood_hotspots",
        "buildings", "critical_infrastructure", "pumping_stations",
        "simulation_runs", "flood_snapshots", "rainfall_observations",
        "rainfall_satellite", "satellite_rainfall_observations",
        "data_sources", "data_ingestion_runs", "cities",
        "hospitals", "police", "fire_stations", "railway_stations",
        "shelters", "low_lying_areas", "green_open_spaces",
        "coastal_exposure_zones", "critical_arterial_corridors",
        "emergency_facilities", "citizen_reports", "alerts",
        "flood_hotspots_v1_legacy"
    ]

    result = {}
    for t in tables:
        rows = await conn.fetch("""
            SELECT column_name, data_type, udt_name, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_schema='public' AND table_name=$1
            ORDER BY ordinal_position
        """, t)
        cols = []
        for r in rows:
            cols.append({
                "name": r["column_name"],
                "type": r["data_type"],
                "udt": r["udt_name"],
                "nullable": r["is_nullable"],
                "default": str(r["column_default"])[:60] if r["column_default"] else None
            })
        result[t] = cols
        print(f"{t}: {len(cols)} columns")

    await conn.close()

    out = _root / "data" / "metadata" / "actual_table_schemas.json"
    with open(out, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved to {out}")

asyncio.run(main())
