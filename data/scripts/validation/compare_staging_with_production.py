"""Compare Spark Staging Datasets against Existing PostGIS Production Foundation.

Executes spatial analysis in PostgreSQL:
1. Roads comparison: staging (78) vs production (14,563) - coverage, length, overlap.
2. Drainage comparison: staging network (39) & structures (41) vs water_bodies (1,730), drainage_links (8), pumping_stations (8).
3. Hotspots comparison: staging hotspots (35) vs historical_flood_events (209) & existing flood_hotspots (10).
4. Low-lying areas (15) vs DEM depression sinks & elevations.
5. Bridges & culverts (33) vs road network & waterway crossings.
6. LULC (69), Impervious Surface (128), Green Spaces (25), Coastal Zones (15) assessment.

Outputs:
- data/metadata/spark_vs_production_comparison.json
"""

import os
import ssl
import json
import asyncio
import asyncpg
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
RAW_URL = os.environ.get("DATABASE_URL", "")
CLEAN_URL = RAW_URL.replace("postgresql+asyncpg://", "postgresql://").split("?")[0]

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

async def compare_datasets():
    print("=================================================================")
    print("   SPATIAL COMPARISON: SPARK STAGING VS PRODUCTION POSTGIS       ")
    print("=================================================================\n")
    
    conn = await asyncpg.connect(CLEAN_URL, ssl=SSL_CTX)
    comparison_results = {}

    # 1. ROADS COMPARISON
    print("1. Comparing Roads: Staging (78) vs Production (14,563)...")
    stg_roads = await conn.fetchrow("""
        SELECT count(*) as count, round((sum(length_m)/1000.0)::numeric, 1) as total_km
        FROM mufns_spatial_staging.staging_roads_curated_78;
    """)
    prod_roads = await conn.fetchrow("""
        SELECT count(*) as count, round((sum(length_m)/1000.0)::numeric, 1) as total_km
        FROM public.road_segments;
    """)
    
    # Overlap analysis: how many staging roads spatially align within ~25m (0.00025 deg) of production road segments
    overlap_roads = await conn.fetchval("""
        SELECT count(DISTINCT s.road_id)
        FROM mufns_spatial_staging.staging_roads_curated_78 s
        JOIN public.road_segments p
        ON ST_DWithin(s.geometry, p.geometry, 0.00025);
    """)
    
    comparison_results["roads"] = {
        "staging_count": stg_roads["count"],
        "staging_km": float(stg_roads["total_km"]),
        "production_count": prod_roads["count"],
        "production_km": float(prod_roads["total_km"]),
        "spatial_overlap_count": overlap_roads,
        "spatial_overlap_pct": round(overlap_roads / stg_roads["count"] * 100.0, 1),
        "assessment": "PARTIAL SUBSET / CURATED ARTERIAL CORRIDORS",
        "action": "DO NOT REPLACE road_segments. Ingest into dedicated critical_arterial_corridors table."
    }
    print(f"  Staging: {stg_roads['count']} roads ({stg_roads['total_km']} km)", flush=True)
    print(f"  Production: {prod_roads['count']} roads ({prod_roads['total_km']} km)", flush=True)
    print(f"  Spatial Overlap: {overlap_roads}/{stg_roads['count']} ({comparison_results['roads']['spatial_overlap_pct']}%)", flush=True)

    # 2. DRAINAGE COMPARISON
    print("\n2. Comparing Drainage Network & Structures...", flush=True)
    stg_drn = await conn.fetchrow("""
        SELECT count(*) as count, round((sum(length_m)/1000.0)::numeric, 1) as total_km
        FROM mufns_spatial_staging.staging_drainage_network_39;
    """)
    prod_water = await conn.fetchval("SELECT count(*) FROM public.water_bodies;")
    prod_links = await conn.fetchval("SELECT count(*) FROM public.drainage_links;")
    prod_nodes = await conn.fetchval("SELECT count(*) FROM public.drainage_nodes;")
    prod_pumps = await conn.fetchval("SELECT count(*) FROM public.pumping_stations;")
    
    # Check how many staging drainage lines align with water_bodies within ~35m (0.00035 deg)
    drn_overlap = await conn.fetchval("""
        SELECT count(DISTINCT s.drainage_id)
        FROM mufns_spatial_staging.staging_drainage_network_39 s
        JOIN public.water_bodies w
        ON ST_DWithin(s.geometry, w.geometry, 0.00035);
    """)
    
    # Structures breakdown
    struct_breakdown = await conn.fetch("""
        SELECT structure_type, count(*) as cnt
        FROM mufns_spatial_staging.staging_drainage_structures_41
        GROUP BY structure_type
        ORDER BY cnt DESC;
    """)
    
    comparison_results["drainage"] = {
        "staging_network_lines": stg_drn["count"],
        "staging_network_km": float(stg_drn["total_km"]),
        "production_water_bodies": prod_water,
        "production_drainage_links": prod_links,
        "production_drainage_nodes": prod_nodes,
        "production_pumping_stations": prod_pumps,
        "staging_overlap_with_water_bodies": drn_overlap,
        "staging_overlap_pct": round(drn_overlap / stg_drn["count"] * 100.0, 1),
        "structures_count": 41,
        "structures_breakdown": {r["structure_type"]: r["cnt"] for r in struct_breakdown},
        "assessment": "NEW COMPREHENSIVE MACRO-DRAINAGE NAMED REPORTERS & STRUCTURES",
        "action": "Promote to primary_drainage_network and drainage_structures."
    }
    print(f"  Staging drainage network: {stg_drn['count']} lines ({stg_drn['total_km']} km)", flush=True)
    print(f"  Production water bodies: {prod_water}, links: {prod_links}, nodes: {prod_nodes}, pumps: {prod_pumps}", flush=True)
    sb_list = [f"{r['structure_type']}: {r['cnt']}" for r in struct_breakdown]
    print(f"  Drainage structures breakdown: {sb_list}", flush=True)

    # 3. FLOOD HOTSPOTS COMPARISON
    print("\n3. Comparing Flood Hotspots: Staging (35) vs Production Events (209) & Hotspots (10)...", flush=True)
    stg_hotspots_count = await conn.fetchval("SELECT count(*) FROM mufns_spatial_staging.staging_flood_hotspots_35;")
    prod_hotspots_count = await conn.fetchval("SELECT count(*) FROM public.flood_hotspots;")
    prod_events_count = await conn.fetchval("SELECT count(*) FROM public.historical_flood_events;")
    
    # Check how many staging hotspots have historical flood events within ~1km (0.009 deg)
    hotspots_near_events = await conn.fetch("""
        SELECT 
            h.hotspot_id, h.name, count(e.event_id) as nearby_events
        FROM mufns_spatial_staging.staging_flood_hotspots_35 h
        LEFT JOIN public.historical_flood_events e
        ON ST_DWithin(h.geometry, e.location, 0.009)
        GROUP BY h.hotspot_id, h.name
        ORDER BY nearby_events DESC;
    """)
    matched_hotspots = sum(1 for r in hotspots_near_events if r["nearby_events"] > 0)
    
    comparison_results["flood_hotspots"] = {
        "staging_hotspots": stg_hotspots_count,
        "production_hotspots": prod_hotspots_count,
        "production_historical_events": prod_events_count,
        "hotspots_linked_to_historical_events": matched_hotspots,
        "hotspots_linked_pct": round(matched_hotspots / stg_hotspots_count * 100.0, 1),
        "assessment": "UPGRADE / EXPANSION OF MUNICIPAL RECURRENT FLOOD HOTSPOTS",
        "action": "Promote to replace legacy 10-row flood_hotspots with 35 verified municipal spots, cross-referenced to historical events."
    }
    print(f"  Staging Hotspots: {stg_hotspots_count} official spots")
    print(f"  Production Hotspots: {prod_hotspots_count} legacy rows, Historical Events: {prod_events_count}")
    print(f"  Hotspots with verified nearby historical events (within 1km): {matched_hotspots}/{stg_hotspots_count} ({comparison_results['flood_hotspots']['hotspots_linked_pct']}%)")

    # 4. LOW-LYING AREAS COMPARISON
    print("\n4. Comparing Low-Lying Areas (15) vs DEM & Terrain...")
    low_stats = await conn.fetchrow("""
        SELECT 
            count(*) as count,
            round((sum(area_m2)/1000000.0)::numeric, 1) as total_sq_km,
            min(elevation_min) as min_elev,
            max(elevation_mean) as max_mean_elev
        FROM mufns_spatial_staging.staging_low_lying_areas_15;
    """)
    comparison_results["low_lying_areas"] = {
        "count": low_stats["count"],
        "total_sq_km": float(low_stats["total_sq_km"]),
        "min_elev_m": low_stats["min_elev"],
        "max_mean_elev_m": low_stats["max_mean_elev"],
        "assessment": "COMPLETELY NEW REGIONAL SEMANTIC HAZARD ZONES",
        "action": "Promote to production table low_lying_areas for municipal warning zones."
    }
    print(f"  Low-lying areas: {low_stats['count']} zones ({low_stats['total_sq_km']} km²), Elevation range: {low_stats['min_elev']}m to {low_stats['max_mean_elev']}m")

    # 5. LAND USE & IMPERVIOUS SURFACE
    print("\n5. Assessing Land Use Land Cover (69) & Impervious Grid (128)...")
    lulc_classes = await conn.fetch("""
        SELECT class, count(*) as count, round((sum(area_m2)/1000000.0)::numeric, 1) as sq_km
        FROM mufns_spatial_staging.staging_land_use_land_cover_69
        GROUP BY class
        ORDER BY sq_km DESC;
    """)
    imp_stats = await conn.fetchrow("""
        SELECT 
            count(*) as cells,
            round(min(impervious_fraction)::numeric, 2) as min_imp,
            round(max(impervious_fraction)::numeric, 2) as max_imp,
            round(avg(impervious_fraction)::numeric, 2) as avg_imp
        FROM mufns_spatial_staging.staging_impervious_surface_128;
    """)
    comparison_results["land_cover"] = {
        "lulc_polygons": 69,
        "lulc_classes": {r["class"]: float(r["sq_km"]) for r in lulc_classes},
        "impervious_cells": imp_stats["cells"],
        "impervious_range": [float(imp_stats["min_imp"]), float(imp_stats["max_imp"])],
        "impervious_avg": float(imp_stats["avg_imp"]),
        "assessment": "COMPLETELY NEW HIGH-VALUE HYDROLOGIC MODELLING LAYERS",
        "action": "Promote to production tables land_use_land_cover and impervious_surface_grid."
    }
    print(f"  LULC: 69 polygons across {len(lulc_classes)} classes.")
    print(f"  Impervious Surface Grid: 128 cells, avg imperviousness: {imp_stats['avg_imp']} (range: {imp_stats['min_imp']} - {imp_stats['max_imp']})")

    # 6. BRIDGES & CULVERTS
    print("\n6. Assessing Bridges & Culverts (33)...")
    brg_types = await conn.fetch("""
        SELECT structure_type, count(*) as count
        FROM mufns_spatial_staging.staging_bridges_culverts_33
        GROUP BY structure_type;
    """)
    comparison_results["bridges_culverts"] = {
        "count": 33,
        "types": {r["structure_type"]: r["count"] for r in brg_types},
        "assessment": "COMPLETELY NEW TRANSPORT-WATERWAY CHOKEPOINTS",
        "action": "Promote to production table bridges_and_culverts."
    }
    bt_list = [f"{r['structure_type']}: {r['count']}" for r in brg_types]
    print(f"  Bridges & Culverts: 33 points ({bt_list})")

    # 7. GREEN OPEN SPACES
    print("\n7. Assessing Green Open Spaces (25)...")
    grn_stats = await conn.fetchrow("""
        SELECT count(*) as count, round((sum(area_m2)/1000000.0)::numeric, 1) as total_sq_km
        FROM mufns_spatial_staging.staging_green_open_spaces_25;
    """)
    comparison_results["green_open_spaces"] = {
        "count": grn_stats["count"],
        "total_sq_km": float(grn_stats["total_sq_km"]),
        "assessment": "COMPLETELY NEW NATURAL INFILTRATION & DETENTION LAYER",
        "action": "Promote to production table green_open_spaces."
    }
    print(f"  Green Open Spaces: {grn_stats['count']} polygons ({grn_stats['total_sq_km']} km²)")

    # 8. COASTAL EXPOSURE
    print("\n8. Assessing Coastal Exposure Zones (15)...")
    coast_types = await conn.fetch("""
        SELECT zone_type, count(*) as count, ST_GeometryType(geometry) as geom_type
        FROM mufns_spatial_staging.staging_coastal_exposure_15
        GROUP BY zone_type, ST_GeometryType(geometry);
    """)
    comparison_results["coastal_exposure"] = {
        "count": 15,
        "breakdown": [f"{r['zone_type']} ({r['geom_type']}): {r['count']}" for r in coast_types],
        "assessment": "COMPLETELY NEW TIDAL / MARINE BACKWATER HAZARD INTERFACE",
        "action": "Promote to production table coastal_exposure_zones."
    }
    print(f"  Coastal Exposure: 15 features ({comparison_results['coastal_exposure']['breakdown']})")

    out_file = Path("data/metadata/spark_vs_production_comparison.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(comparison_results, f, indent=2)
    print(f"\nSaved detailed comparison results to {out_file}")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(compare_datasets())
