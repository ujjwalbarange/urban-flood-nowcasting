"""Stage 2 Prep: Inspect actual LULC, imperviousness, drainage, and tide data in PostGIS."""
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

    print("=" * 70)
    print("STAGE 2 DATA INSPECTION")
    print("=" * 70)

    # 1. LULC classes
    print("\n--- LULC Classes ---")
    rows = await conn.fetch("""
        SELECT class, class_code, name, count(*) as cnt, 
               sum(area_m2) as total_area, source, confidence
        FROM land_use_land_cover 
        GROUP BY class, class_code, name, source, confidence
        ORDER BY total_area DESC NULLS LAST
    """)
    for r in rows:
        area_km2 = (r['total_area'] or 0) / 1e6
        print(f"  {r['class_code'] or '?':<6} {r['class'] or '?':<25} {r['name'] or '':<30} cnt={r['cnt']} area={area_km2:.2f}km2 conf={r['confidence']}")

    # 2. Impervious surface grid
    print("\n--- Impervious Surface Grid ---")
    rows = await conn.fetch("""
        SELECT cell_id, impervious_fraction, built_up_fraction, source, confidence,
               ST_AsText(ST_Centroid(geometry)) as centroid
        FROM impervious_surface_grid
        ORDER BY impervious_fraction DESC
        LIMIT 15
    """)
    for r in rows:
        print(f"  cell={r['cell_id']} imp={r['impervious_fraction']:.3f} built={r['built_up_fraction']:.3f} src={r['source']} conf={r['confidence']} at {r['centroid']}")
    
    stats = await conn.fetchrow("""
        SELECT count(*) as cnt, 
               min(impervious_fraction) as min_imp, max(impervious_fraction) as max_imp,
               avg(impervious_fraction) as avg_imp,
               min(built_up_fraction) as min_bu, max(built_up_fraction) as max_bu,
               ST_Extent(geometry) as bbox
        FROM impervious_surface_grid
    """)
    print(f"  STATS: n={stats['cnt']} imp=[{stats['min_imp']:.3f}-{stats['max_imp']:.3f}] avg={stats['avg_imp']:.3f} bbox={stats['bbox']}")

    # 3. Drainage nodes with elevation
    print("\n--- Drainage Nodes (with elevation) ---")
    rows = await conn.fetch("""
        SELECT node_id, node_type, invert_elevation_m, ground_elevation_m, data_quality,
               ST_AsText(geometry) as geom
        FROM drainage_nodes
        ORDER BY node_id
        LIMIT 15
    """)
    for r in rows:
        print(f"  {r['node_id']:<15} type={r['node_type']:<12} inv={r['invert_elevation_m']} gnd={r['ground_elevation_m']} q={r['data_quality']} {r['geom']}")

    # 4. Pumping stations
    print("\n--- Pumping Stations ---")
    rows = await conn.fetch("SELECT pump_id, name, ward, num_pumps, rated_capacity_mld, current_status FROM pumping_stations ORDER BY pump_id")
    for r in rows:
        print(f"  {r['pump_id']:<10} {r['name']:<35} ward={r['ward']} pumps={r['num_pumps']} cap={r['rated_capacity_mld']}MLD status={r['current_status']}")

    # 5. Tide observations
    print("\n--- Tide Observations ---")
    rows = await conn.fetch("""
        SELECT station_name, timestamp, tide_height_m, datum, data_source, quality_flag
        FROM tide_observations
        ORDER BY timestamp
        LIMIT 12
    """)
    for r in rows:
        print(f"  {r['station_name']:<20} {r['timestamp']} h={r['tide_height_m']:.2f}m datum={r['datum']} src={r['data_source']} q={r['quality_flag']}")
    
    tide_stats = await conn.fetchrow("""
        SELECT count(*) as cnt, 
               min(tide_height_m) as min_h, max(tide_height_m) as max_h,
               avg(tide_height_m) as avg_h,
               min(timestamp) as t_min, max(timestamp) as t_max
        FROM tide_observations
    """)
    print(f"  STATS: n={tide_stats['cnt']} h=[{tide_stats['min_h']:.2f}-{tide_stats['max_h']:.2f}]m avg={tide_stats['avg_h']:.2f}m range={tide_stats['t_min']} to {tide_stats['t_max']}")

    # 6. Historical flood events for July 2024
    print("\n--- Historical Flood Events (July 2024) ---")
    rows = await conn.fetch("""
        SELECT event_id, date, ward, locality, flood_depth_cm, flood_severity, 
               rainfall_1h_mm, rainfall_3h_mm, rainfall_24h_mm
        FROM historical_flood_events
        WHERE date >= '2024-07-01' AND date <= '2024-07-31'
        ORDER BY date, ward
        LIMIT 20
    """)
    print(f"  Found {len(rows)} events in July 2024")
    for r in rows:
        print(f"  {r['date']} ward={r['ward']:<6} {r['locality'] or '':<25} depth={r['flood_depth_cm']}cm sev={r['flood_severity']} rain1h={r['rainfall_1h_mm']} rain3h={r['rainfall_3h_mm']} rain24h={r['rainfall_24h_mm']}")

    # 7. INSAT data for July 7-11 2024
    print("\n--- INSAT-3DR Data: July 7-11, 2024 ---")
    rows = await conn.fetch("""
        SELECT product, event_name,
               count(*) as cnt,
               min(observation_time) as t_min, max(observation_time) as t_max,
               avg(mumbai_core_mean_value) as avg_rain, max(mumbai_core_max_value) as max_rain
        FROM satellite_rainfall_observations
        WHERE observation_time >= '2024-07-07' AND observation_time <= '2024-07-12'
        GROUP BY product, event_name
        ORDER BY product
    """)
    for r in rows:
        print(f"  {r['product']:<5} event={r['event_name']:<25} n={r['cnt']} from={r['t_min']} to={r['t_max']} avg_rain={r['avg_rain']:.2f} max_rain={r['max_rain']:.1f}")

    # 8. Terrain derivatives
    print("\n--- Terrain Derivatives ---")
    rows = await conn.fetch("SELECT derivative_id, dem_tile_id, derivative_type, storage_path, min_value, max_value, mean_value FROM terrain_derivatives ORDER BY derivative_id")
    for r in rows:
        print(f"  {r['derivative_type']:<20} min={r['min_value']} max={r['max_value']} mean={r['mean_value']} path={r['storage_path']}")

    # 9. Low-lying areas
    print("\n--- Low-Lying Areas ---")
    rows = await conn.fetch("SELECT zone_id, name, depression_type, elevation_min_m, elevation_mean_m, area_m2 FROM low_lying_areas ORDER BY elevation_min_m")
    for r in rows:
        print(f"  {r['name']:<30} type={r['depression_type']} elev_min={r['elevation_min_m']:.1f}m area={r['area_m2']/1e6:.2f}km2")

    await conn.close()

asyncio.run(main())
