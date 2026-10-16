"""Step 1 Audit: Comprehensive investigation of July 7-9 2024 INSAT-3DR HEM rainfall forcing.

Addresses the 14 audit points:
1. Raw HEM values
2. HEM units
3. Half-hour temporal conversion
4. Temporal accumulation
5. Number of expected vs available timestamps
6. Missing timestamps
7. Spatial averaging
8. Mumbai spatial clipping
9. 28x28 grid interpretation
10. NoData handling
11. Rainfall-rate -> rainfall-depth conversion
12. Event start/end timestamps
13. Peak rainfall calculation
14. Cumulative rainfall calculation
"""

import asyncio
import json
import os
import ssl
from datetime import datetime, timezone, timedelta
from pathlib import Path
import asyncpg
import numpy as np
from dotenv import load_dotenv

load_dotenv()

RAW_URL = os.environ.get("DATABASE_URL", "")
CLEAN_URL = RAW_URL.replace("postgresql+asyncpg://", "postgresql://").split("?")[0]

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


async def main():
    conn = await asyncpg.connect(CLEAN_URL, ssl=SSL_CTX)
    print("=" * 80)
    print("STEP 1: AUDIT OF JULY 7-9, 2024 REPLAY RAINFALL FORCING")
    print("=" * 80)

    # 1. Event Window
    start_time = datetime(2024, 7, 7, 18, 0, tzinfo=timezone.utc)
    end_time = datetime(2024, 7, 9, 6, 0, tzinfo=timezone.utc)
    total_window_hours = (end_time - start_time).total_seconds() / 3600.0
    expected_30min_granules = int(total_window_hours * 2) + 1  # 36 hours = 72 or 73 timestamps

    print(f"Event Window: {start_time} to {end_time}")
    print(f"Total window duration: {total_window_hours:.1f} hours")
    print(f"Expected 30-min granules: {expected_30min_granules}")

    # 2. Query HEM granules
    rows = await conn.fetch("""
        SELECT observation_id, observation_time, mean_value, max_value, min_value,
               mumbai_core_mean_value, mumbai_core_max_value,
               spatial_resolution_deg, spatial_resolution_km,
               raster_width, raster_height, valid_pixel_count, total_pixel_count,
               nodata_value, nodata_pixel_count, unit, canonical_file_path, grid_data
        FROM public.satellite_rainfall_observations
        WHERE product = 'HEM'
          AND observation_time >= $1
          AND observation_time <= $2
        ORDER BY observation_time ASC;
    """, start_time, end_time)

    print(f"\nAvailable HEM granules in window: {len(rows)}")

    # Also check IMC and GPM
    imc_count = await conn.fetchval("""
        SELECT count(*) FROM public.satellite_rainfall_observations
        WHERE product = 'IMC' AND observation_time >= $1 AND observation_time <= $2;
    """, start_time, end_time)
    gpm_count = await conn.fetchval("""
        SELECT count(*) FROM public.rainfall_satellite
        WHERE timestamp >= $1 AND timestamp <= $2;
    """, start_time, end_time)
    gauge_count = await conn.fetchval("""
        SELECT count(*) FROM public.rainfall_observations
        WHERE observed_at >= $1 AND observed_at <= $2;
    """, start_time, end_time)

    print(f"Available IMC granules in window: {imc_count}")
    print(f"Available GPM records in window: {gpm_count}")
    print(f"Available Gauge records in window: {gauge_count}")

    # Check timestamps and find missing timestamps
    timestamps = [r["observation_time"] for r in rows]
    print(f"\nFirst timestamp: {timestamps[0] if timestamps else 'None'}")
    print(f"Last timestamp:  {timestamps[-1] if timestamps else 'None'}")

    # Find expected half-hourly timestamps and gaps
    curr = start_time
    missing_ts = []
    found_ts_set = set(t.replace(second=0, microsecond=0) for t in timestamps)
    
    # Analyze delta between consecutive observations
    gaps = []
    for i in range(len(timestamps) - 1):
        delta_min = (timestamps[i+1] - timestamps[i]).total_seconds() / 60.0
        if delta_min > 35:
            gaps.append((timestamps[i], timestamps[i+1], delta_min))

    print(f"\nNumber of gaps > 35 min: {len(gaps)}")
    for g in gaps:
        print(f"  Gap: {g[0]} -> {g[1]} ({g[2]:.0f} minutes)")

    # Analyze units, raster dimensions, grid
    r0 = rows[0]
    print(f"\nRaster Dimensions: {r0['raster_width']} x {r0['raster_height']}")
    print(f"Resolution: {r0['spatial_resolution_deg']} deg (~{r0['spatial_resolution_km']} km)")
    print(f"Unit in DB: {r0['unit']}")
    print(f"NoData Value: {r0['nodata_value']}")
    print(f"Valid Pixels per granule: min={min(r['valid_pixel_count'] for r in rows)}, max={max(r['valid_pixel_count'] for r in rows)}")

    # Extract all values
    # Corridor mean (mean_value)
    # Mumbai-core mean (mumbai_core_mean_value)
    # Corridor max (max_value)
    # Mumbai-core max (mumbai_core_max_value)
    
    corridor_means = [r["mean_value"] or 0.0 for r in rows]
    corridor_maxs = [r["max_value"] or 0.0 for r in rows]
    mumbai_means = [r["mumbai_core_mean_value"] if r["mumbai_core_mean_value"] is not None else 0.0 for r in rows]
    mumbai_maxs = [r["mumbai_core_max_value"] if r["mumbai_core_max_value"] is not None else 0.0 for r in rows]

    # Accumulations (assuming 0.5 hr per granule)
    acc_corridor_mean = sum(v * 0.5 for v in corridor_means)
    acc_corridor_max = sum(v * 0.5 for v in corridor_maxs)
    acc_mumbai_mean = sum(v * 0.5 for v in mumbai_means)
    acc_mumbai_max = sum(v * 0.5 for v in mumbai_maxs)

    # Also compute pixel-level accumulation across the 28x28 grid
    grid_acc = np.zeros((28, 28), dtype=float)
    grid_peak = np.zeros((28, 28), dtype=float)
    valid_grid_counts = 0

    for r in rows:
        gd = r["grid_data"]
        if gd:
            if isinstance(gd, str):
                arr = np.array(json.loads(gd), dtype=float)
            else:
                arr = np.array(gd, dtype=float)
            # mask nodata
            valid_mask = (arr >= 0.0)
            clean = np.where(valid_mask, arr, 0.0)
            grid_acc += clean * 0.5
            grid_peak = np.maximum(grid_peak, clean)
            valid_grid_counts += 1

    max_pixel_cum_mm = float(np.max(grid_acc))
    mean_pixel_cum_mm = float(np.mean(grid_acc))
    min_pixel_cum_mm = float(np.min(grid_acc))
    peak_pixel_rate_mmh = float(np.max(grid_peak))

    print("\n" + "=" * 80)
    print("AGGREGATION COMPARISON (July 7 18:00 UTC to July 9 06:00 UTC):")
    print("=" * 80)
    print(f"1. Full 28x28 Corridor Spatial MEAN accumulation:   {acc_corridor_mean:.2f} mm")
    print(f"2. Mumbai Core Spatial MEAN accumulation (current):    {acc_mumbai_mean:.2f} mm")
    print(f"3. Full 28x28 Corridor Spatial MAX accumulation:    {acc_corridor_max:.2f} mm")
    print(f"4. Mumbai Core Spatial MAX accumulation:             {acc_mumbai_max:.2f} mm")
    print(f"5. Single Maximum Pixel (Fixed Cell) accumulation:   {max_pixel_cum_mm:.2f} mm")
    print(f"6. Mean of 28x28 cell accumulations:                 {mean_pixel_cum_mm:.2f} mm")
    print(f"Peak rainfall rate recorded (spatial max):           {max(corridor_maxs):.2f} mm/hr")
    print(f"Peak rainfall rate in Mumbai core:                   {max(mumbai_maxs):.2f} mm/hr")
    print(f"Peak pixel rate anywhere across all grids:           {peak_pixel_rate_mmh:.2f} mm/hr")

    # Let's inspect the Mumbai Core definition in the grid!
    # Where is Mumbai core located in the 28x28 grid?
    # Let's check how mumbai_core_mean_value was computed in audit report / ingestion.
    with open("data/metadata/mosdac_insat_audit_report.json", "r", encoding="utf-8") as f:
        meta = json.load(f)
    print("\nMetadata summary from audit report:")
    print("Spatial bounds of granules:", meta.get("mumbai_corridor_bbox"))
    print("Mumbai core bbox:", meta.get("mumbai_core_bbox"))

    # Table of representative timestamps around the peak
    # Find timestamp of peak
    peak_idx = int(np.argmax(mumbai_maxs))
    peak_time = timestamps[peak_idx]
    print(f"\nPeak Mumbai Max occurred at index {peak_idx}: {peak_time}")
    print(f"  corridor_mean={corridor_means[peak_idx]:.2f}, corridor_max={corridor_maxs[peak_idx]:.2f}")
    print(f"  mumbai_mean={mumbai_means[peak_idx]:.2f}, mumbai_max={mumbai_maxs[peak_idx]:.2f}")

    # Produce table around peak
    start_table_idx = max(0, peak_idx - 10)
    end_table_idx = min(len(rows), peak_idx + 12)

    print("\n" + "=" * 105)
    print("REPRESENTATIVE PERIOD TABLE AROUND JULY 8 PEAK:")
    print("=" * 105)
    print(f"{'timestamp (UTC)':<22} | {'corridor_mean':<14} | {'mumbai_mean':<12} | {'mumbai_max':<11} | {'corridor_max':<13} | {'step_mm (core)':<14} | {'accum_mm (core)':<14}")
    print("-" * 105)

    running_accum = 0.0
    for i, r in enumerate(rows):
        m_mean = mumbai_means[i]
        m_max = mumbai_maxs[i]
        c_mean = corridor_means[i]
        c_max = corridor_maxs[i]
        step_mm = m_mean * 0.5
        running_accum += step_mm

        if start_table_idx <= i <= end_table_idx:
            ts_str = r["observation_time"].strftime("%Y-%m-%d %H:%M")
            print(f"{ts_str:<22} | {c_mean:>11.2f} mm/h | {m_mean:>9.2f} mm/h | {m_max:>8.2f} mm/h | {c_max:>10.2f} mm/h | {step_mm:>11.2f} mm | {running_accum:>11.2f} mm")

    print("-" * 105)

    # Also check what GPM IMERG reported for the same window!
    gpm_rows = await conn.fetch("""
        SELECT timestamp, avg(precipitation_mm_hr) as mean_rate, max(precipitation_mm_hr) as max_rate
        FROM public.rainfall_satellite
        WHERE timestamp >= $1 AND timestamp <= $2
        GROUP BY timestamp ORDER BY timestamp ASC;
    """, start_time, end_time)
    
    gpm_cum = sum(float(r["mean_rate"] or 0) * 0.5 for r in gpm_rows)
    gpm_peak = max((float(r["max_rate"] or 0) for r in gpm_rows), default=0.0)
    print(f"\nGPM IMERG in same window ({len(gpm_rows)} timesteps):")
    print(f"  GPM Cumulative (spatial mean): {gpm_cum:.2f} mm")
    print(f"  GPM Peak rate:                 {gpm_peak:.2f} mm/hr")

    # Historical flood events
    hf_rows = await conn.fetch("""
        SELECT event_id, date, flood_depth_cm, flood_severity, rainfall_24h_mm, locality, ward
        FROM public.historical_flood_events
        WHERE date >= '2024-07-07' AND date <= '2024-07-10'
        ORDER BY date ASC;
    """)
    print(f"\nHistorical Flood Events in DB for July 2024 ({len(hf_rows)} records):")
    for hf in hf_rows[:10]:
        print(f"  {hf['date'].strftime('%Y-%m-%d %H:%M')} | ward={hf['ward']} | locality={hf['locality']} | severity={hf['flood_severity']} | depth={hf['flood_depth_cm']}cm | rain24h={hf['rainfall_24h_mm']}mm")

    # Let's inspect the spatial coordinates of the 28x28 INSAT grid
    # Get envelope WKT and bounds
    geom_wkt = await conn.fetchval("""
        SELECT ST_AsText(geometry) FROM public.satellite_rainfall_observations
        WHERE product = 'HEM' LIMIT 1;
    """)
    print(f"\nHEM Grid Bounding Polygon: {geom_wkt}")

    # Inspect Mumbai core mask
    # How was mumbai_core defined? Let's check attributes of a granule
    attrs_raw = await conn.fetchval("""
        SELECT attributes FROM public.satellite_rainfall_observations
        WHERE product = 'HEM' LIMIT 1;
    """)
    print(f"Sample Attributes: {attrs_raw}")

    # Let's find out how many pixels are in Mumbai Core vs the 28x28 grid
    # We can inspect the ingestion code or compute intersection with wards
    mumbai_union_geom = await conn.fetchval("""
        SELECT ST_AsText(ST_Envelope(ST_Union(geometry))) FROM public.wards;
    """)
    print(f"Wards Bounding Box: {mumbai_union_geom}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())

