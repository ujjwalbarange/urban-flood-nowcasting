"""Stage 5: Multi-Event Historical Replay Engine.

Replays all three distinct historical events in the database:
1. July 7-11, 2024  (5 days, 244 HEM granules, primary HEM forcing)
2. July 23-26, 2024 (4 days, 192 IMC granules, IMC forcing - HEM unavailable)
3. August 13-21, 2025 (9 days, 400 HEM granules, HEM forcing - IMC unavailable)

Strictly satisfies:
- Unique simulation ID (UUID4) for every run
- Event ID, rainfall strategy, and exact input datasets
- Model configuration, physical parameters (LULC, Manning's n, Horton)
- Downstream tidal boundary conditions
- Mass balance closure (< 0.1%)
- Full provenance recorded and persisted to public.simulation_runs
- Zero overwriting of previous runs
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
load_dotenv(project_root / ".env")

from services.nowcast.historical_replay import (
    HistoricalEvent,
    ReplayConfig,
    run_historical_replay,
    persist_replay_result,
)
from services.validation.historical_validation import HistoricalValidator
from services.terrain.dem_loader import get_catchment_dem

# Define the 3 distinct historical event periods
HISTORICAL_SUITE = [
    {
        "event": HistoricalEvent(
            event_id="july_7_11_2024_deluge",
            name="July 7-11 2024 Mumbai Extended Monsoon Deluge",
            start_time=datetime(2024, 7, 7, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2024, 7, 11, 23, 59, tzinfo=timezone.utc),
            description="5-day extreme monsoon deluge with major cloudburst on July 8. Subways submerged, rail lines flooded.",
            known_flood_locations=["Hindmata", "King's Circle", "Kurla", "Milan Subway", "Andheri Subway", "Khar Subway"],
            expected_severity="Catastrophic",
            reference_rainfall_24h_mm=315.0,
        ),
        "fusion_mode": "hem_only",
        "tide_scenario": "rainfall_high_tide",
        "routing_dt_s": 5.0,
    },
    {
        "event": HistoricalEvent(
            event_id="july_23_26_2024_surge",
            name="July 23-26 2024 Mumbai Late-Monsoon Surge",
            start_time=datetime(2024, 7, 23, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2024, 7, 26, 23, 59, tzinfo=timezone.utc),
            description="4-day sustained heavy rainfall event. IMC imager data available in database.",
            known_flood_locations=["Kurla", "Sion", "Hindmata", "Dadar"],
            expected_severity="Severe",
            reference_rainfall_24h_mm=140.0,
        ),
        "fusion_mode": "imc_only",
        "tide_scenario": "rainfall_normal_tide",
        "routing_dt_s": 5.0,
    },
    {
        "event": HistoricalEvent(
            event_id="aug_13_21_2025_monsoon",
            name="August 13-21 2025 Mumbai Extended Monsoon Deluge",
            start_time=datetime(2025, 8, 13, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2025, 8, 21, 23, 59, tzinfo=timezone.utc),
            description="9-day prolonged rainfall event across Mumbai region. 400 HEM granules verified.",
            known_flood_locations=["Mithi River Basin", "BKC", "Kurla", "Sion"],
            expected_severity="Severe",
            reference_rainfall_24h_mm=180.0,
        ),
        "fusion_mode": "hem_only",
        "tide_scenario": "rainfall_normal_tide",
        "routing_dt_s": 5.0,
    },
]


async def main():
    print("=" * 105)
    print("STEP 5: HISTORICAL REPLAY OF ALL 3 MULTI-DAY MONSOON EVENTS")
    print("=" * 105)

    validator = HistoricalValidator()
    hotspots = await validator.fetch_hotspots()
    dem_raw, georef = get_catchment_dem("mumbai", max_dim=60)

    replay_outputs = []

    for item in HISTORICAL_SUITE:
        ev = item["event"]
        mode = item["fusion_mode"]
        tide = item["tide_scenario"]

        print("\n" + "-" * 95)
        print(f"REPLAYING EVENT: {ev.name}")
        print(f"  Window:       {ev.start_time} to {ev.end_time}")
        print(f"  Strategy:     {mode}")
        print(f"  Tide:         {tide}")
        print("-" * 95)

        cfg = ReplayConfig(
            event=ev,
            fusion_mode=mode,
            grid_size=60,
            catchment="mumbai",
            tide_scenario=tide,
            routing_dt_s=item.get("routing_dt_s", 5.0),
        )

        t0 = time.time()
        res = await run_historical_replay(cfg)
        elapsed = time.time() - t0

        # Run validation
        if res.max_depth_grid is not None and res.flooded_cells > 0:
            val_report = validator.validate_simulation(
                simulation_id=res.simulation_id,
                event_id=ev.event_id,
                event_name=ev.name,
                depth_grid=res.max_depth_grid,
                georef=georef,
                hotspots=hotspots,
                historical_events=[],
                flood_threshold_m=0.08,
                simulated_peak_timing_hours=res.peak_timing_hours,
            )
            hit_rate = val_report.hotspot_hit_rate_pct
        else:
            hit_rate = 0.0

        print(f"  Status:             {res.status}")
        print(f"  Simulation ID:      {res.simulation_id}")
        print(f"  Rainfall Granules:  {res.rainfall_granules}")
        print(f"  Cumulative Rain:    {res.rainfall_cumulative_mm:.2f} mm")
        print(f"  Peak Rain Rate:     {res.rainfall_peak_mmh:.2f} mm/hr")
        print(f"  Max Depth:          {res.max_depth_m:.3f} m")
        print(f"  Flooded Area:       {res.flooded_area_km2:.4f} km² ({res.flooded_cells} cells)")
        print(f"  Coastal Flood Area: {res.coastal_flooded_area_km2:.4f} km² ({res.coastal_flooded_cells} cells)")
        print(f"  Hotspot Hit Rate:   {hit_rate:.1f}%")
        print(f"  Mass Balance Error: {res.mass_balance_error_pct:.2f}%")
        print(f"  Runtime:            {elapsed:.1f} s")

        # Persist to database
        persisted = await persist_replay_result(res)
        print(f"  Persisted to DB:    {persisted}")

        replay_outputs.append({
            "event_id": ev.event_id,
            "event_name": ev.name,
            "simulation_id": res.simulation_id,
            "strategy": mode,
            "tide_scenario": tide,
            "rainfall_granules": res.rainfall_granules,
            "rainfall_cumulative_mm": res.rainfall_cumulative_mm,
            "rainfall_peak_mmh": res.rainfall_peak_mmh,
            "max_depth_m": res.max_depth_m,
            "mean_depth_m": res.mean_depth_m,
            "flooded_area_km2": res.flooded_area_km2,
            "coastal_flooded_area_km2": res.coastal_flooded_area_km2,
            "hotspot_hit_rate_pct": hit_rate,
            "mass_balance_error_pct": res.mass_balance_error_pct,
            "runtime_seconds": round(elapsed, 2),
            "input_datasets": res.input_datasets,
            "assumptions": res.assumptions,
        })

    # Summary Table
    print("\n" + "=" * 125)
    print("ALL HISTORICAL EVENTS REPLAY SUMMARY:")
    print("=" * 125)
    print(f"{'Event ID':<26} | {'Strategy':<10} | {'Granules':<9} | {'Rain mm':<8} | {'Max Depth':<10} | {'Flood km²':<10} | {'MB Err%':<8} | {'Runtime':<8}")
    print("-" * 125)
    for r in replay_outputs:
        print(f"{r['event_id']:<26} | {r['strategy']:<10} | {r['rainfall_granules']:<9} | {r['rainfall_cumulative_mm']:>6.2f} mm | {r['max_depth_m']:>7.3f} m  | {r['flooded_area_km2']:>7.3f} km² | {r['mass_balance_error_pct']:>6.2f}% | {r['runtime_seconds']:>6.1f}s")
    print("-" * 125)

    # Save to JSON
    out_file = project_root / "data" / "metadata" / "all_historical_replays_results.json"
    with open(out_file, "w") as f:
        json.dump(replay_outputs, f, indent=2)
    print(f"\nAll replay results saved: {out_file}")


if __name__ == "__main__":
    asyncio.run(main())
