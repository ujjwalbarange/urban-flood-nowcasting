"""Stage 7: Historical Validation Script for July 8 2024 Mumbai Event.

Compares simulated flood results against:
1. public.historical_flood_events (19 ground records on July 8 2024)
2. public.flood_hotspots (35 persistent BMC flood hotspots)

Produces:
- Hotspot hit rate (recall)
- Precision & F1 score
- Depth MAE
- Timing comparison
- Categorization into OBSERVED vs SIMULATED vs ASSUMED
- Persisted JSON report
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

from services.validation.historical_validation import HistoricalValidator
from services.nowcast.historical_replay import HISTORICAL_EVENTS, ReplayConfig, run_historical_replay
from services.terrain.dem_loader import get_catchment_dem
from services.terrain.conditioning import fill_sinks


async def main():
    print("=" * 95)
    print("STAGE 7: HISTORICAL VALIDATION REPORT (JULY 8 2024 MUMBAI MONSOON DELUGE)")
    print("=" * 95)

    validator = HistoricalValidator()
    hotspots = await validator.fetch_hotspots()
    events = await validator.fetch_historical_events(start_date="2024-07-07", end_date="2024-07-09")

    print(f"\n1. Observational Datasets Loaded from PostGIS:")
    print(f"   • flood_hotspots:          {len(hotspots)} locations (persistent BMC hotspots)")
    print(f"   • historical_flood_events: {len(events)} verified records (July 7-9 2024 event window)")

    # Run replay with rainfall + high tide for realistic validation
    event = HISTORICAL_EVENTS["july_2024_cloudburst"]
    cfg = ReplayConfig(
        event=event,
        fusion_mode="hem_only",
        grid_size=60,
        catchment="mumbai",
        tide_scenario="rainfall_high_tide",
    )

    print(f"\n2. Executing Simulation for Validation (mode=hem_only, tide=rainfall_high_tide)...")
    sim_res = await run_historical_replay(cfg)
    print(f"   Simulation complete: sim_id={sim_res.simulation_id}, max_depth={sim_res.max_depth_m:.3f}m, flooded_area={sim_res.flooded_area_km2:.3f} km2")

    # Get georef
    dem_raw, georef = get_catchment_dem(cfg.catchment, max_dim=cfg.grid_size)

    # Validate
    report = validator.validate_simulation(
        simulation_id=sim_res.simulation_id,
        event_id=event.event_id,
        event_name=event.name,
        depth_grid=sim_res.max_depth_grid,
        georef=georef,
        hotspots=hotspots,
        historical_events=events,
        flood_threshold_m=0.08,
        simulated_peak_timing_hours=sim_res.peak_timing_hours,
    )

    # Display Validation Report
    print("\n" + "=" * 95)
    print("STAGE 7 VALIDATION METRICS:")
    print("=" * 95)
    print(f"Simulation ID:                 {report.simulation_id}")
    print(f"Catchment Domain Bounds:       Lon [{report.domain_bounds['west']:.3f}, {report.domain_bounds['east']:.3f}], Lat [{report.domain_bounds['south']:.3f}, {report.domain_bounds['north']:.3f}]")
    print(f"Simulation Cell Size:          {report.cell_size_m:.1f} m")
    print(f"Flood Depth Threshold:         {report.flood_threshold_m * 100:.0f} cm ({report.flood_threshold_m} m)")
    print(f"Simulated Flooded Area:        {report.simulated_flooded_area_km2:.4f} km² ({report.simulated_flooded_cells} cells)")

    print(f"\nA. FLOOD HOTSPOT METRICS (Stage 7.1):")
    print(f"   Total Hotspots in DB:       {report.hotspots_total_db}")
    print(f"   Hotspots in Sim Domain:     {report.hotspots_in_domain}")
    print(f"   Hotspots Detected (Hits):   {report.hotspots_hit}")
    print(f"   Hotspots Missed:            {report.hotspots_missed}")
    print(f"   Hotspot Hit Rate (Recall):  {report.hotspot_hit_rate_pct:.1f}%")
    print(f"   Hotspot Precision:          {report.precision:.3f}")
    print(f"   Hotspot F1-Score:           {report.f1_score:.3f}")

    print(f"\nB. HISTORICAL EVENT OBSERVATIONS METRICS (Stage 7.2):")
    print(f"   Observed Records in Window: {report.events_observed_in_window}")
    print(f"   Observations in Sim Domain: {report.events_in_domain}")
    print(f"   Observations Hit:           {report.events_hit}")
    print(f"   Observations Missed:        {report.events_missed}")
    print(f"   Observation Hit Rate:       {report.event_hit_rate_pct:.1f}%")
    if report.mean_depth_mae_m is not None:
        print(f"   Mean Observed Depth:        {report.mean_observed_depth_m:.3f} m")
        print(f"   Mean Simulated Depth:       {report.mean_simulated_depth_m:.3f} m")
        print(f"   Depth MAE:                  {report.mean_depth_mae_m:.3f} m")

    print(f"\nC. TIMING METRICS:")
    print(f"   Simulated Peak Timing:      t = {report.simulated_peak_timing_hours:.2f} hours")
    print(f"   Observed Deluge Peak Window: 01:00 - 07:00 IST July 8 (19:30 July 7 - 01:30 July 8 UTC)")

    print("\n" + "-" * 95)
    print("DETAILED HOTSPOT VERIFICATION TABLE:")
    print("-" * 95)
    print(f"{'Hotspot Name':<32} | {'Ward':<10} | {'Obs Depth':<11} | {'Sim Depth':<11} | {'Status':<12}")
    print("-" * 95)
    for h in report.hotspot_details:
        if h.in_simulation_domain:
            obs_d = f"{h.observed_typical_depth_m:.2f} m" if h.observed_typical_depth_m else "N/A"
            print(f"{h.name:<32} | {h.ward:<10} | {obs_d:<11} | {h.simulated_depth_m:>7.3f} m   | {h.classification:<12}")
    print("-" * 95)

    print("\n" + "-" * 95)
    print("DETAILED HISTORICAL EVENT OBSERVATIONS TABLE:")
    print("-" * 95)
    print(f"{'Locality / Landmark':<38} | {'Ward':<10} | {'Obs Depth':<10} | {'Sim Depth':<10} | {'Error (m)':<10} | {'Status':<8}")
    print("-" * 95)
    for ev in report.event_details:
        if ev.in_simulation_domain:
            print(f"{ev.locality[:38]:<38} | {ev.ward:<10} | {ev.observed_depth_m:>6.2f} m   | {ev.simulated_depth_m:>6.3f} m   | {ev.depth_error_m:>+8.3f} m | {ev.classification:<8}")
    print("-" * 95)

    print("\n" + "=" * 95)
    print("SCIENTIFIC INTEGRITY BREAKDOWN:")
    print("=" * 95)
    print("1. OBSERVED (Ground Truth from Database):")
    for o in report.observed_facts:
        print(f"   [OBSERVED]  {o}")
    print("\n2. SIMULATED (Model Physics Outputs):")
    for s in report.simulated_results:
        print(f"   [SIMULATED] {s}")
    print("\n3. ASSUMED (Methodological Constraints & Parameters):")
    for a in report.scientific_assumptions:
        print(f"   [ASSUMED]   {a}")
    print("=" * 95)

    # Persist report to JSON
    out_dir = project_root / "data" / "metadata"
    out_file = out_dir / "july2024_historical_validation_report.json"
    serializable = {
        "simulation_id": report.simulation_id,
        "event_id": report.event_id,
        "event_name": report.event_name,
        "evaluation_time": report.evaluation_time,
        "domain_bounds": report.domain_bounds,
        "cell_size_m": report.cell_size_m,
        "flood_threshold_m": report.flood_threshold_m,
        "metrics": {
            "hotspots_total_db": report.hotspots_total_db,
            "hotspots_in_domain": report.hotspots_in_domain,
            "hotspots_hit": report.hotspots_hit,
            "hotspots_missed": report.hotspots_missed,
            "hotspot_hit_rate_pct": report.hotspot_hit_rate_pct,
            "precision": report.precision,
            "recall": report.recall,
            "f1_score": report.f1_score,
            "events_observed_in_window": report.events_observed_in_window,
            "events_in_domain": report.events_in_domain,
            "events_hit": report.events_hit,
            "events_missed": report.events_missed,
            "event_hit_rate_pct": report.event_hit_rate_pct,
            "mean_depth_mae_m": report.mean_depth_mae_m,
            "mean_observed_depth_m": report.mean_observed_depth_m,
            "mean_simulated_depth_m": report.mean_simulated_depth_m,
            "simulated_flooded_cells": report.simulated_flooded_cells,
            "simulated_flooded_area_km2": report.simulated_flooded_area_km2,
            "simulated_peak_timing_hours": report.simulated_peak_timing_hours,
        },
        "hotspot_details": [
            {
                "hotspot_id": h.hotspot_id,
                "name": h.name,
                "ward": h.ward,
                "lon": h.lon,
                "lat": h.lat,
                "in_domain": h.in_simulation_domain,
                "observed_typical_depth_m": h.observed_typical_depth_m,
                "simulated_depth_m": h.simulated_depth_m,
                "classification": h.classification,
            }
            for h in report.hotspot_details
        ],
        "event_details": [
            {
                "event_id": ev.event_id,
                "locality": ev.locality,
                "ward": ev.ward,
                "date": ev.date_observed,
                "observed_depth_m": ev.observed_depth_m,
                "simulated_depth_m": ev.simulated_depth_m,
                "depth_error_m": ev.depth_error_m,
                "classification": ev.classification,
            }
            for ev in report.event_details
        ],
        "scientific_provenance": {
            "observed": report.observed_facts,
            "simulated": report.simulated_results,
            "assumed": report.scientific_assumptions,
        }
    }
    with open(out_file, "w") as f:
        json.dump(serializable, f, indent=2)
    print(f"\nHistorical Validation Report saved: {out_file}")


if __name__ == "__main__":
    asyncio.run(main())
