"""Test: Run the July 8 2024 Mumbai historical flood event replay.

This is the MAIN MILESTONE test — proving the complete pipeline works
end-to-end with real data.

Chain tested:
INSAT HEM → FUSION → HORTON INFILTRATION → RUNOFF → 2D DIFFUSIVE WAVE
  → DRAINAGE COUPLING → FLOOD DEPTH → PERSISTENCE
"""

import asyncio
import json
import sys
import os
import time
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
project_root = Path(__file__).resolve().parent
while not (project_root / ".env").exists() and project_root != project_root.parent:
    project_root = project_root.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")


async def main():
    from services.nowcast.historical_replay import (
        HISTORICAL_EVENTS,
        ReplayConfig,
        run_historical_replay,
        persist_replay_result,
    )

    print("=" * 70)
    print("MUFNS MILESTONE TEST: July 8 2024 Mumbai Historical Flood Replay")
    print("=" * 70)

    event = HISTORICAL_EVENTS["july_2024_cloudburst"]
    print(f"\nEvent: {event.name}")
    print(f"Window: {event.start_time} -> {event.end_time}")
    print(f"Severity: {event.expected_severity}")
    print(f"Known flood locations: {', '.join(event.known_flood_locations)}")
    print(f"Reference 24h rainfall: {event.reference_rainfall_24h_mm} mm")

    # Test with HEM_ONLY first (primary INSAT product)
    modes_to_test = [
        ("hem_only", "Primary INSAT-3DR HEM"),
        # ("gpm_hem", "GPM + HEM blend"),  # Uncomment for comparison
    ]

    results = []

    for mode, desc in modes_to_test:
        print(f"\n{'─' * 60}")
        print(f"Running replay: {desc} (mode={mode})")
        print(f"{'─' * 60}")

        config = ReplayConfig(
            event=event,
            fusion_mode=mode,
            grid_size=60,
            catchment="mumbai",
            tide_scenario="observed",
        )

        t0 = time.time()
        result = await run_historical_replay(config)
        elapsed = time.time() - t0

        print(f"\n--- Result ---")
        print(f"  Simulation ID: {result.simulation_id}")
        print(f"  Status: {result.status}")
        if result.error:
            print(f"  Error: {result.error}")
        print(f"  Runtime: {elapsed:.1f}s")

        print(f"\n  RAINFALL:")
        print(f"    Source: {result.rainfall_source}")
        print(f"    Granules: {result.rainfall_granules}")
        print(f"    Cumulative: {result.rainfall_cumulative_mm} mm")
        print(f"    Peak rate: {result.rainfall_peak_mmh} mm/hr")

        print(f"\n  SPATIAL PARAMS:")
        print(f"    Avg imperviousness: {result.avg_imperviousness}")
        print(f"    Avg Manning's n: {result.avg_manning_n}")
        print(f"    Source: {result.spatial_param_source}")
        print(f"    Coverage: {result.spatial_coverage_pct}%")

        print(f"\n  FLOOD RESULTS:")
        print(f"    Max depth: {result.max_depth_m:.3f} m")
        print(f"    Mean depth (flooded): {result.mean_depth_m:.3f} m")
        print(f"    Flooded cells: {result.flooded_cells}")
        print(f"    Flooded area: {result.flooded_area_km2:.4f} km²")

        print(f"\n  DRAINAGE:")
        print(f"    Nodes coupled: {result.drainage_nodes_coupled}")
        print(f"    Coupling events: {result.coupling_events}")

        print(f"\n  MASS BALANCE:")
        print(f"    Rainfall volume: {result.total_rainfall_volume_m3:.0f} m³")
        print(f"    Surface storage: {result.total_surface_storage_m3:.0f} m³")
        print(f"    Mass balance error: {result.mass_balance_error_pct:.1f}%")

        print(f"\n  PROVENANCE:")
        for ds in result.input_datasets:
            print(f"    • {ds}")
        print(f"\n  ASSUMPTIONS:")
        for a in result.assumptions:
            print(f"    ⚠ {a}")

        # Persist to database
        print(f"\n  Persisting to PostGIS...")
        persisted = await persist_replay_result(result)
        print(f"  Persisted: {persisted}")

        results.append(result)

    # Save results JSON
    out_dir = project_root / "data" / "metadata"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "july2024_replay_results.json"
    with open(out_file, "w") as f:
        # Exclude numpy arrays
        serializable = []
        for r in results:
            d = {
                "simulation_id": r.simulation_id,
                "event_id": r.event_id,
                "event_name": r.event_name,
                "status": r.status,
                "error": r.error,
                "fusion_mode": r.fusion_mode,
                "rainfall_source": r.rainfall_source,
                "rainfall_granules": r.rainfall_granules,
                "rainfall_cumulative_mm": r.rainfall_cumulative_mm,
                "rainfall_peak_mmh": r.rainfall_peak_mmh,
                "max_depth_m": r.max_depth_m,
                "mean_depth_m": r.mean_depth_m,
                "flooded_cells": r.flooded_cells,
                "flooded_area_km2": r.flooded_area_km2,
                "drainage_nodes_coupled": r.drainage_nodes_coupled,
                "total_rainfall_volume_m3": r.total_rainfall_volume_m3,
                "total_surface_storage_m3": r.total_surface_storage_m3,
                "mass_balance_error_pct": r.mass_balance_error_pct,
                "avg_imperviousness": r.avg_imperviousness,
                "avg_manning_n": r.avg_manning_n,
                "runtime_seconds": r.runtime_seconds,
                "input_datasets": r.input_datasets,
                "assumptions": r.assumptions,
                "fusion_metadata": r.fusion_metadata,
            }
            serializable.append(d)
        json.dump(serializable, f, indent=2)
    print(f"\nResults saved: {out_file}")

    # Final verdict
    print(f"\n{'=' * 70}")
    if all(r.status == "completed" for r in results):
        print("✅ MILESTONE PASSED: Historical replay pipeline functional")
        if results[0].flooded_cells > 0:
            print("✅ Flood depths produced from real INSAT rainfall data")
        else:
            print("⚠  No flooding detected — check rainfall magnitude vs grid resolution")
    else:
        print("❌ MILESTONE FAILED — errors occurred during replay")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
