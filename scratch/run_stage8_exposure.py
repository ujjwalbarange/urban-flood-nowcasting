"""Stage 8: Run PostGIS Exposure and Impact Analysis on July 2024 Event.

Executes genuine PostGIS spatial overlays (ST_Intersects, ST_DWithin) on:
- road_segments (14,563 roads)
- buildings (30,000 footprints)
- population_grids (1,242 cells)
- critical_infrastructure (2,002 facilities)
- shelters (10 designated centers)
- wards (24 administrative wards)
- flood_hotspots (35 persistent hotspots)
- pumping_stations (8 storm water stations)
- water_bodies (1,730 features)

Saves results to data/metadata/july2024_exposure_results.json
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
load_dotenv(project_root / ".env")

from services.nowcast.historical_replay import HISTORICAL_EVENTS, ReplayConfig, run_historical_replay
from services.risk.exposure_engine import ExposureEngine
from services.terrain.dem_loader import get_catchment_dem


async def main():
    print("=" * 95)
    print("STEP 6: STAGE 8 POSTGIS EXPOSURE AND IMPACT OVERLAY ANALYSIS")
    print("=" * 95)

    event = HISTORICAL_EVENTS["july_2024_cloudburst"]
    cfg = ReplayConfig(
        event=event,
        fusion_mode="hem_only",
        grid_size=60,
        catchment="mumbai",
        tide_scenario="rainfall_high_tide",  # standard realistic flood scenario
        routing_dt_s=5.0,
    )

    print("\n1. Running Flood Simulation with High Tide (sim_id pending)...")
    sim_res = await run_historical_replay(cfg)
    print(f"   Simulation complete: sim_id={sim_res.simulation_id}, flooded_area={sim_res.flooded_area_km2:.3f} km2")

    dem_raw, georef = get_catchment_dem(cfg.catchment, max_dim=cfg.grid_size)

    print("\n2. Executing PostGIS Spatial Intersections...")
    engine = ExposureEngine()
    exposure = await engine.compute_exposure(
        simulation_id=sim_res.simulation_id,
        event_id=event.event_id,
        depth_grid=sim_res.max_depth_grid,
        georef=georef,
        flood_threshold_m=0.08,
    )

    print("\n" + "=" * 95)
    print("POSTGIS EXPOSURE AND IMPACT ASSESSMENT RESULTS:")
    print("=" * 95)
    print(f"Simulation ID:                 {exposure.simulation_id}")
    print(f"Flooded Surface Extent:        {exposure.flooded_area_km2:.4f} km²")
    print(f"Flood Depth Threshold:         {exposure.flood_threshold_m * 100:.0f} cm ({exposure.flood_threshold_m} m)")

    print(f"\n1. ROADS INFRASTRUCTURE (road_segments):")
    print(f"   Flooded Road Segments:      {exposure.flooded_road_segments_count:,} segments")
    print(f"   Total Flooded Road Length:  {exposure.flooded_road_length_km:.2f} km")
    print(f"   Roads by Classification:    {json.dumps(exposure.roads_by_class)}")

    print(f"\n2. BUILDINGS INFRASTRUCTURE (buildings):")
    print(f"   Affected Building Footprints: {exposure.affected_buildings_count:,} buildings")
    print(f"   Total Inundated Footprint:    {exposure.affected_building_footprint_m2:,.1f} m²")

    print(f"\n3. POPULATION EXPOSURE (population_grids):")
    print(f"   Directly Exposed Population:  {exposure.exposed_population_count:,} residents")
    print(f"   Flooded Population Grid Cells:{exposure.exposed_population_cells} cells (100m res)")

    print(f"\n4. CRITICAL INFRASTRUCTURE (critical_infrastructure):")
    print(f"   Affected Critical Facilities: {exposure.affected_critical_infra_count} facilities")
    print(f"   Affected by Category:         {json.dumps(exposure.affected_infra_by_category)}")
    print(f"   Sample Affected Facilities:")
    for fac in exposure.affected_infra_list[:8]:
        print(f"     • [{fac.get('category')}] {fac.get('name')} (Ward {fac.get('ward')})")

    print(f"\n5. DESIGNATED RELIEF SHELTERS (shelters):")
    print(f"   Shelters in Flood Extent:     {exposure.affected_shelters_count} of 10 designated centers")
    print(f"   Compromised Shelter Capacity: {exposure.affected_shelter_capacity:,} persons")
    for s in exposure.affected_shelters_list:
        print(f"     • {s.get('name')} (Capacity: {s.get('capacity_persons')} persons)")

    print(f"\n6. ADMINISTRATIVE WARDS (wards):")
    print(f"   Affected Municipal Wards:     {exposure.affected_wards_count} of 24 wards")
    for w in exposure.affected_wards_list:
        print(f"     • {w.get('name')} (Ward ID: {w.get('ward_id')}, Pop: {w.get('population'):,})")

    print(f"\n7. FLOOD HOTSPOTS OVERLAP (flood_hotspots):")
    print(f"   Directly Inundated Hotspots:  {exposure.covered_hotspots_count} of 35 hotspots")
    for h in exposure.covered_hotspots_list:
        print(f"     • {h.get('name')} (Severity: {h.get('severity')}, Ward: {h.get('ward')})")

    print(f"\n8. STORM WATER PUMPING STATIONS (pumping_stations):")
    print(f"   Pumping Stations within 500m: {exposure.nearby_pumping_stations_count} stations")
    for p in exposure.pumping_stations_list:
        print(f"     • {p.get('name')} ({p.get('num_pumps')} pumps, Ward {p.get('ward')})")

    print(f"\n9. WATER BODIES CONFLUENCE (water_bodies):")
    print(f"   Intersecting Water Features:  {exposure.interacting_water_bodies_count} features")
    print(f"   Total Water Body Area:        {exposure.interacting_water_bodies_area_m2:,.1f} m²")

    print("\n" + "=" * 95)
    print("PROVENANCE AND AUDIT TRAIL:")
    print("=" * 95)
    print("PostGIS Tables Queried:")
    for t in exposure.postgis_tables_queried:
        print(f"  [PostGIS] public.{t}")
    print("\nLimitations & Scientific Constraints:")
    for lim in exposure.limitations:
        print(f"  [LIMITATION] {lim}")
    print("=" * 95)

    # Persist to JSON
    out_dir = project_root / "data" / "metadata"
    out_file = out_dir / "july2024_exposure_results.json"
    serializable = {
        "simulation_id": exposure.simulation_id,
        "event_id": exposure.event_id,
        "evaluated_at": exposure.evaluated_at,
        "flood_threshold_m": exposure.flood_threshold_m,
        "flooded_area_km2": exposure.flooded_area_km2,
        "metrics": {
            "flooded_road_segments_count": exposure.flooded_road_segments_count,
            "flooded_road_length_km": exposure.flooded_road_length_km,
            "roads_by_class": exposure.roads_by_class,
            "affected_buildings_count": exposure.affected_buildings_count,
            "affected_building_footprint_m2": exposure.affected_building_footprint_m2,
            "exposed_population_count": exposure.exposed_population_count,
            "exposed_population_cells": exposure.exposed_population_cells,
            "affected_critical_infra_count": exposure.affected_critical_infra_count,
            "affected_infra_by_category": exposure.affected_infra_by_category,
            "affected_shelters_count": exposure.affected_shelters_count,
            "affected_shelter_capacity": exposure.affected_shelter_capacity,
            "affected_wards_count": exposure.affected_wards_count,
            "covered_hotspots_count": exposure.covered_hotspots_count,
            "nearby_pumping_stations_count": exposure.nearby_pumping_stations_count,
            "interacting_water_bodies_count": exposure.interacting_water_bodies_count,
            "interacting_water_bodies_area_m2": exposure.interacting_water_bodies_area_m2,
        },
        "affected_infrastructure_samples": exposure.affected_infra_list[:15],
        "affected_shelters": exposure.affected_shelters_list,
        "affected_wards": exposure.affected_wards_list,
        "covered_hotspots": exposure.covered_hotspots_list,
        "nearby_pumping_stations": exposure.pumping_stations_list,
        "provenance": {
            "postgis_tables_queried": exposure.postgis_tables_queried,
            "limitations": exposure.limitations,
        }
    }
    with open(out_file, "w") as f:
        json.dump(serializable, f, indent=2)
    print(f"\nExposure results saved: {out_file}")


if __name__ == "__main__":
    asyncio.run(main())
