"""Stage 6: Test and Benchmark All 5 Coastal Tide Scenarios on July 8 2024 Event.

Scenarios:
1. rainfall_only          (no tide / free ocean outflow)
2. tide_only              (pure tidal inundation, zero rainfall)
3. rainfall_normal_tide   (rainfall + MHWN 3.48m CD -> +0.97m MSL)
4. rainfall_high_tide     (rainfall + MHWS 4.45m CD -> +1.94m MSL, calibrated from Apollo Bunder)
5. rainfall_extreme_tide  (rainfall + 5.00m CD -> +2.49m MSL extreme surge)

Records for each run:
- max depth (m)
- flooded area (km2)
- peak timing (hours)
- coastal flooded area (km2)
- mass balance closure error (%)
- computational runtime (s)
- persistence to PostGIS
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
load_dotenv(project_root / ".env")

from services.nowcast.historical_replay import (
    HISTORICAL_EVENTS,
    ReplayConfig,
    run_historical_replay,
    persist_replay_result,
)


async def main():
    event = HISTORICAL_EVENTS["july_2024_cloudburst"]

    scenarios = [
        ("rainfall_only", "Scenario 1: Rainfall Only (Free Ocean Drainage, No Tide)"),
        ("tide_only", "Scenario 2: Tide Only (No Rain, Spring High Tide Surge)"),
        ("rainfall_normal_tide", "Scenario 3: Rainfall + Normal Neap Tide (3.50m CD / +0.97m MSL)"),
        ("rainfall_high_tide", "Scenario 4: Rainfall + Spring High Tide (4.45m CD / +1.94m MSL)"),
        ("rainfall_extreme_tide", "Scenario 5: Rainfall + Extreme Surge Tide (5.00m CD / +2.49m MSL)"),
    ]

    results = []

    print("=" * 95)
    print("STEP 2: STAGE 6 COASTAL TIDE INTEGRATION BENCHMARK (JULY 2024 DELUGE)")
    print("=" * 95)

    for sc_key, sc_name in scenarios:
        print("\n" + "-" * 90)
        print(f"RUNNING: {sc_name}")
        print("-" * 90)


        cfg = ReplayConfig(
            event=event,
            fusion_mode="hem_only",
            grid_size=60,
            catchment="mumbai",
            tide_scenario=sc_key,
        )

        t0 = time.time()
        res = await run_historical_replay(cfg)
        elapsed = time.time() - t0

        print(f"  Status:             {res.status}")
        print(f"  Simulation ID:      {res.simulation_id}")
        print(f"  Runtime:            {elapsed:.2f} s")
        print(f"  Max Depth:          {res.max_depth_m:.3f} m")
        print(f"  Mean Depth (flood): {res.mean_depth_m:.3f} m")
        print(f"  Flooded Area:       {res.flooded_area_km2:.4f} km² ({res.flooded_cells} cells)")
        print(f"  Coastal Flood Area: {res.coastal_flooded_area_km2:.4f} km² ({res.coastal_flooded_cells} cells)")
        print(f"  Peak Timing:        t = {res.peak_timing_hours:.2f} hours")
        print(f"  Tide Peak Level:    {res.tide_peak_m_cd:.2f} m CD / {res.tide_peak_m_msl:.2f} m MSL")
        print(f"  Rainfall Volume:    {res.total_rainfall_volume_m3:.0f} m³")
        print(f"  Tidal Inflow Vol:   {res.total_tide_inflow_m3:.0f} m³")
        print(f"  Surface Storage:    {res.total_surface_storage_m3:.0f} m³")
        print(f"  Mass Balance Error: {res.mass_balance_error_pct:.2f}%")

        # Persist to database
        persisted = await persist_replay_result(res)
        print(f"  Persisted to DB:    {persisted}")

        results.append({
            "scenario": sc_key,
            "description": sc_name,
            "simulation_id": res.simulation_id,
            "max_depth_m": res.max_depth_m,
            "mean_depth_m": res.mean_depth_m,
            "flooded_area_km2": res.flooded_area_km2,
            "flooded_cells": res.flooded_cells,
            "coastal_flooded_area_km2": res.coastal_flooded_area_km2,
            "coastal_flooded_cells": res.coastal_flooded_cells,
            "peak_timing_hours": res.peak_timing_hours,
            "tide_peak_m_cd": res.tide_peak_m_cd,
            "tide_peak_m_msl": res.tide_peak_m_msl,
            "rainfall_volume_m3": res.total_rainfall_volume_m3,
            "tide_inflow_m3": res.total_tide_inflow_m3,
            "surface_storage_m3": res.total_surface_storage_m3,
            "mass_balance_error_pct": res.mass_balance_error_pct,
            "runtime_seconds": round(elapsed, 2),
        })

    # Summary Comparison Table
    print("\n" + "=" * 115)
    print("STAGE 6 TIDE INTEGRATION COMPARISON TABLE:")
    print("=" * 115)
    print(f"{'Scenario':<23} | {'Max Depth':<10} | {'Total Flood':<12} | {'Coastal Flood':<14} | {'Peak Time':<10} | {'MB Err %':<9} | {'Runtime':<8}")
    print("-" * 115)
    for r in results:
        print(f"{r['scenario']:<23} | {r['max_depth_m']:>7.3f} m  | {r['flooded_area_km2']:>7.3f} km² | {r['coastal_flooded_area_km2']:>9.3f} km² | {r['peak_timing_hours']:>6.2f} h  | {r['mass_balance_error_pct']:>6.2f}%  | {r['runtime_seconds']:>6.1f}s")
    print("-" * 115)

    # Save results to json
    out_file = project_root / "data" / "metadata" / "stage6_tide_benchmark_results.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nBenchmark results saved: {out_file}")


if __name__ == "__main__":
    asyncio.run(main())
