"""Stage 4: Multiple Rainfall Forcing Experiments on July 8 2024 Event.

Executes controlled experiments across 6 rainfall forcing strategies:
A. HEM_ONLY      — Primary INSAT-3DR Hydro-Estimator Method
B. IMC_ONLY      — Secondary INSAT-3DR IMAGER Precipitation Retrieval
C. GPM_ONLY      — NASA GPM IMERG Satellite Precipitation (audited availability)
D. GPM_HEM       — Dual satellite blend (GPM + INSAT HEM)
E. GPM_IMC       — Dual satellite blend (GPM + INSAT IMC)
F. FULL_FUSION   — Multi-sensor fusion (HEM + IMC + GPM + Surface Gauge Calibration)

For each experiment, records:
- rainfall statistics (cumulative mm, peak rate mm/hr, granules)
- flood depth (max depth m, mean depth m)
- flooded area (km2)
- hotspot hit rate (%)
- mass balance error (%)
- peak timing (hours)
- computational runtime (s)
- provenance

Saves comparative results to data/metadata/stage4_rainfall_experiments_results.json
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
from services.validation.historical_validation import HistoricalValidator
from services.terrain.dem_loader import get_catchment_dem


async def main():
    print("=" * 105)
    print("STEP 4: MULTIPLE RAINFALL FORCING CONTROLLED EXPERIMENTS (JULY 8 2024 EVENT)")
    print("=" * 105)

    event = HISTORICAL_EVENTS["july_2024_cloudburst"]

    experiments = [
        ("hem_only", "Exp A: HEM_ONLY (Primary INSAT-3DR Hydro-Estimator)"),
        ("imc_only", "Exp B: IMC_ONLY (Secondary INSAT-3DR IMAGER Retrieval)"),
        ("gpm_only", "Exp C: GPM_ONLY (NASA GPM IMERG V06B/V07B)"),
        ("gpm_hem",  "Exp D: HEM + GPM (Dual Satellite Blend: HEM Primary + GPM)"),
        ("gpm_imc",  "Exp E: IMC + GPM (Dual Satellite Blend: IMC Primary + GPM)"),
        ("full_fusion", "Exp F: FULL_FUSION (Multi-Sensor: HEM + IMC + GPM + Gauges)"),
    ]

    validator = HistoricalValidator()
    hotspots = await validator.fetch_hotspots()
    hist_events = await validator.fetch_historical_events("2024-07-07", "2024-07-09")

    # Catchment DEM and georef
    dem_raw, georef = get_catchment_dem("mumbai", max_dim=60)

    results = []

    for mode_key, exp_desc in experiments:
        print("\n" + "-" * 95)
        print(f"RUNNING: {exp_desc}")
        print("-" * 95)

        cfg = ReplayConfig(
            event=event,
            fusion_mode=mode_key,
            grid_size=60,
            catchment="mumbai",
            tide_scenario="rainfall_normal_tide",  # standard baseline tide
        )

        t0 = time.time()
        res = await run_historical_replay(cfg)
        elapsed = time.time() - t0

        # Evaluate against hotspots
        if res.max_depth_grid is not None and res.flooded_cells > 0:
            val_report = validator.validate_simulation(
                simulation_id=res.simulation_id,
                event_id=event.event_id,
                event_name=event.name,
                depth_grid=res.max_depth_grid,
                georef=georef,
                hotspots=hotspots,
                historical_events=hist_events,
                flood_threshold_m=0.08,
                simulated_peak_timing_hours=res.peak_timing_hours,
            )
            hotspot_hit_rate = val_report.hotspot_hit_rate_pct
            event_hit_rate = val_report.event_hit_rate_pct
            precision = val_report.precision
            f1 = val_report.f1_score
            mae = val_report.mean_depth_mae_m
        else:
            hotspot_hit_rate = 0.0
            event_hit_rate = 0.0
            precision = 0.0
            f1 = 0.0
            mae = None

        print(f"  Status:             {res.status}")
        print(f"  Simulation ID:      {res.simulation_id}")
        print(f"  Rainfall Granules:  {res.rainfall_granules}")
        print(f"  Cumulative Rain:    {res.rainfall_cumulative_mm:.2f} mm")
        print(f"  Peak Rain Rate:     {res.rainfall_peak_mmh:.2f} mm/hr")
        print(f"  Max Flood Depth:    {res.max_depth_m:.3f} m")
        print(f"  Flooded Area:       {res.flooded_area_km2:.4f} km² ({res.flooded_cells} cells)")
        print(f"  Hotspot Hit Rate:   {hotspot_hit_rate:.1f}%")
        print(f"  Precision / F1:     {precision:.3f} / {f1:.3f}")
        print(f"  Mass Balance Error: {res.mass_balance_error_pct:.2f}%")
        print(f"  Runtime:            {elapsed:.2f} s")
        print(f"  Provenance:         {res.rainfall_source}")

        # Persist simulation
        await persist_replay_result(res)

        results.append({
            "mode": mode_key,
            "description": exp_desc,
            "simulation_id": res.simulation_id,
            "status": res.status,
            "granules": res.rainfall_granules,
            "cumulative_mm": res.rainfall_cumulative_mm,
            "peak_rate_mmh": res.rainfall_peak_mmh,
            "max_depth_m": res.max_depth_m,
            "mean_depth_m": res.mean_depth_m,
            "flooded_area_km2": res.flooded_area_km2,
            "flooded_cells": res.flooded_cells,
            "hotspot_hit_rate_pct": hotspot_hit_rate,
            "event_hit_rate_pct": event_hit_rate,
            "precision": precision,
            "f1_score": f1,
            "depth_mae_m": mae,
            "peak_timing_hours": res.peak_timing_hours,
            "mass_balance_error_pct": res.mass_balance_error_pct,
            "runtime_seconds": round(elapsed, 2),
            "provenance": res.rainfall_source,
            "assumptions": res.assumptions,
        })

    # Summary Comparison Table
    print("\n" + "=" * 125)
    print("STAGE 4 MULTI-SENSOR RAINFALL EXPERIMENTS COMPARISON:")
    print("=" * 125)
    print(f"{'Mode':<14} | {'Rain mm':<8} | {'Peak mm/h':<10} | {'Max Depth':<10} | {'Flood Area':<11} | {'Hotspot Hit%':<13} | {'MB Err%':<8} | {'Runtime':<8}")
    print("-" * 125)
    for r in results:
        print(f"{r['mode']:<14} | {r['cumulative_mm']:>6.2f} mm | {r['peak_rate_mmh']:>7.2f} mm/h | {r['max_depth_m']:>7.3f} m  | {r['flooded_area_km2']:>7.3f} km² | {r['hotspot_hit_rate_pct']:>10.1f}%  | {r['mass_balance_error_pct']:>6.2f}% | {r['runtime_seconds']:>6.1f}s")
    print("-" * 125)

    # Persist JSON
    out_dir = project_root / "data" / "metadata"
    out_file = out_dir / "stage4_rainfall_experiments_results.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nRainfall experiment results saved: {out_file}")


if __name__ == "__main__":
    asyncio.run(main())
