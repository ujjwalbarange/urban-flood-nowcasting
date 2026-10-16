"""Step 1 Audit Deep Dive:
Extracts all metrics and answers for the 14 audit items:
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
import rasterio
from dotenv import load_dotenv

load_dotenv()

RAW_URL = os.environ.get("DATABASE_URL", "")
CLEAN_URL = RAW_URL.replace("postgresql+asyncpg://", "postgresql://").split("?")[0]

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


async def run_audit():
    conn = await asyncpg.connect(CLEAN_URL, ssl=SSL_CTX)

    # July 7 18:00 UTC to July 9 06:00 UTC
    start_utc = datetime(2024, 7, 7, 18, 0, tzinfo=timezone.utc)
    end_utc = datetime(2024, 7, 9, 6, 0, tzinfo=timezone.utc)

    rows = await conn.fetch("""
        SELECT observation_id, observation_time,
               min_value, max_value, mean_value, std_value,
               p50_value, p90_value, p99_value,
               mumbai_core_mean_value, mumbai_core_max_value,
               raster_width, raster_height,
               spatial_resolution_deg, spatial_resolution_km,
               valid_pixel_count, total_pixel_count, nodata_value, nodata_pixel_count,
               unit, source_file, canonical_file_path, grid_data, attributes
        FROM public.satellite_rainfall_observations
        WHERE product = 'HEM'
          AND observation_time >= $1
          AND observation_time <= $2
        ORDER BY observation_time ASC;
    """, start_utc, end_utc)

    print(f"Total rows retrieved for July 7 18:00 to July 9 06:00 UTC: {len(rows)}")

    # 1. Raw HEM values analysis
    all_means = [r["mean_value"] for r in rows]
    all_maxs = [r["max_value"] for r in rows]
    all_mumbai_means = [r["mumbai_core_mean_value"] for r in rows]
    all_mumbai_maxs = [r["mumbai_core_max_value"] for r in rows]

    print("\n--- Point 1: Raw HEM Values Summary ---")
    print(f"Corridor Mean: min={min(all_means):.3f}, max={max(all_means):.3f}, mean={np.mean(all_means):.3f}")
    print(f"Corridor Max:  min={min(all_maxs):.3f}, max={max(all_maxs):.3f}, mean={np.mean(all_maxs):.3f}")
    print(f"Mumbai Mean:   min={min(all_mumbai_means):.3f}, max={max(all_mumbai_means):.3f}, mean={np.mean(all_mumbai_means):.3f}")
    print(f"Mumbai Max:    min={min(all_mumbai_maxs):.3f}, max={max(all_mumbai_maxs):.3f}, mean={np.mean(all_mumbai_maxs):.3f}")

    # 2. Units
    print("\n--- Point 2: Units ---")
    print(f"Declared Unit in DB: {rows[0]['unit']}")
    # Inspect GeoTIFF file on disk if available
    sample_tif = rows[0]["canonical_file_path"]
    if Path(sample_tif).exists():
        with rasterio.open(sample_tif) as src:
            print(f"Rasterio sample tags: {src.tags()}")
            print(f"Rasterio bounds: {src.bounds}")
            print(f"Rasterio nodata: {src.nodata}")
            print(f"Rasterio shape: {src.shape}")
            print(f"Rasterio crs: {src.crs}")
            sample_data = src.read(1)
            print(f"Raw TIF data min: {sample_data.min()}, max: {sample_data.max()}")

    # 3. Half-hour temporal conversion
    print("\n--- Point 3 & 4: Temporal Conversion & Accumulation ---")
    # In INSAT HEM, the instantaneous/half-hourly rainfall rate is given in mm/hr.
    # Therefore, 30-min rainfall depth = rate * 0.5 hours.
    # What was used: step_mm = rate * 0.5.
    
    # 5. Number of expected vs available timestamps
    window_hours = (end_utc - start_utc).total_seconds() / 3600.0
    expected_steps = int(window_hours / 0.5)  # 36 / 0.5 = 72 intervals
    print(f"Window duration: {window_hours} hours")
    print(f"Expected 30-min steps: {expected_steps}")
    print(f"Available granules: {len(rows)}")

    # 6. Missing timestamps
    print("\n--- Point 6: Missing Timestamps ---")
    ts_list = [r["observation_time"] for r in rows]
    for i in range(len(ts_list) - 1):
        dt = (ts_list[i+1] - ts_list[i]).total_seconds() / 60.0
        if dt > 35:
            print(f"  Missing timestamp between {ts_list[i]} and {ts_list[i+1]} (gap: {dt:.0f} min)")

    # 7, 8, 9: Spatial averaging, Mumbai clipping, 28x28 grid interpretation
    print("\n--- Points 7, 8, 9: Spatial Averaging & Mumbai Clipping & 28x28 Grid ---")
    # Inspect attributes of row 0
    attrs = json.loads(rows[0]["attributes"]) if isinstance(rows[0]["attributes"], str) else rows[0]["attributes"]
    bounds = attrs.get("bounds", [])
    print(f"Grid bounds [W, S, E, N]: {bounds}")
    # Compute pixel size
    res_deg = rows[0]["spatial_resolution_deg"]
    width = rows[0]["raster_width"]
    height = rows[0]["raster_height"]
    print(f"Grid shape: {height} rows x {width} cols, res={res_deg} deg")
    
    # Let's see how each cell maps to coordinates:
    # bounds = [min_lon, min_lat, max_lon, max_lat]
    min_lon, min_lat, max_lon, max_lat = bounds
    # Latitudes of rows: row 0 is top (max_lat), row 27 is bottom (min_lat)
    row_lats = [max_lat - (r + 0.5) * res_deg for r in range(height)]
    col_lons = [min_lon + (c + 0.5) * res_deg for c in range(width)]

    print(f"Top row center latitude:    {row_lats[0]:.4f} N")
    print(f"Bottom row center latitude: {row_lats[-1]:.4f} N")
    print(f"Left col center longitude:  {col_lons[0]:.4f} E")
    print(f"Right col center longitude: {col_lons[-1]:.4f} E")

    # Let's inspect where Mumbai Core was sliced in the ingestion script
    # Look at how mumbai_core was computed:
    # Let's see which cells have values in the grid_data
    # Reconstruct the accumulation 2D grid
    grid_acc_corridor = np.zeros((28, 28), dtype=float)
    grid_peak_rate = np.zeros((28, 28), dtype=float)

    for r in rows:
        gd = json.loads(r["grid_data"]) if isinstance(r["grid_data"], str) else r["grid_data"]
        arr = np.array(gd, dtype=float)
        valid = (arr >= 0.0)
        clean = np.where(valid, arr, 0.0)
        grid_acc_corridor += clean * 0.5
        grid_peak_rate = np.maximum(grid_peak_rate, clean)

    print("\nAccumulation 2D grid summary:")
    print(f"Min cell accumulation: {grid_acc_corridor.min():.2f} mm")
    print(f"Max cell accumulation: {grid_acc_corridor.max():.2f} mm")
    print(f"Mean of all cells:     {grid_acc_corridor.mean():.2f} mm")
    print(f"Median of all cells:   {np.median(grid_acc_corridor):.2f} mm")

    # Find the top 5 highest accumulated cells
    top_indices = np.unravel_index(np.argsort(grid_acc_corridor.ravel())[::-1][:10], grid_acc_corridor.shape)
    print("\nTop 10 highest accumulated cells in 28x28 grid:")
    print(f"{'Rank':<5} | {'Row':<4} | {'Col':<4} | {'Lat':<8} | {'Lon':<8} | {'Accum (mm)':<10} | {'Peak (mm/h)':<10}")
    for k in range(len(top_indices[0])):
        r_idx = top_indices[0][k]
        c_idx = top_indices[1][k]
        print(f"{k+1:<5} | {r_idx:<4} | {c_idx:<4} | {row_lats[r_idx]:<8.4f} | {col_lons[c_idx]:<8.4f} | {grid_acc_corridor[r_idx, c_idx]:<10.2f} | {grid_peak_rate[r_idx, c_idx]:<10.2f}")

    # Check which cells fall inside Mumbai City / Suburbs:
    # Island City + Suburbs bbox: 72.75 to 72.99 E, 18.89 to 19.28 N
    mumbai_cells = []
    for r_idx in range(height):
        for c_idx in range(width):
            lat = row_lats[r_idx]
            lon = col_lons[c_idx]
            if 18.89 <= lat <= 19.28 and 72.75 <= lon <= 72.99:
                mumbai_cells.append((r_idx, c_idx, lat, lon, grid_acc_corridor[r_idx, c_idx]))

    print(f"\nNumber of cells intersecting Mumbai bounding box (18.89-19.28 N, 72.75-72.99 E): {len(mumbai_cells)}")
    for r_idx, c_idx, lat, lon, acc in mumbai_cells:
        print(f"  Row {r_idx:2d}, Col {c_idx:2d} (Lat {lat:.4f} N, Lon {lon:.4f} E): Accum = {acc:6.2f} mm, Peak = {grid_peak_rate[r_idx, c_idx]:6.2f} mm/h")

    # 10. NoData handling
    print("\n--- Point 10: NoData Handling ---")
    print(f"Nodata value defined: {rows[0]['nodata_value']}")
    print(f"Nodata pixel count across all granules: {sum(r['nodata_pixel_count'] for r in rows)}")

    # 11. Rainfall-rate -> rainfall-depth conversion
    print("\n--- Point 11: Rate -> Depth Conversion ---")
    print("Formula: Depth (mm) = Rate (mm/hr) * dt (hr)")
    print("dt = 0.5 hr for 30-min intervals.")

    # 12. Event start/end timestamps
    print("\n--- Point 12: Event start/end timestamps ---")
    print(f"Event Start: {start_utc.isoformat()} (2024-07-07 23:30 IST)")
    print(f"Event End:   {end_utc.isoformat()} (2024-07-09 11:30 IST)")
    print(f"First Obs:   {ts_list[0].isoformat()} (2024-07-07 23:45 IST)")
    print(f"Last Obs:    {ts_list[-1].isoformat()} (2024-07-09 11:15 IST)")

    # 13 & 14: Peak rainfall & Cumulative rainfall calculation
    print("\n--- Points 13 & 14: Peak & Cumulative Calculations Summary ---")
    print(f"Corridor Mean Accumulation:       {sum(all_means)*0.5:.2f} mm")
    print(f"Mumbai Core Mean Accumulation:    {sum(all_mumbai_means)*0.5:.2f} mm")
    print(f"Mumbai Core Max Accumulation:     {sum(all_mumbai_maxs)*0.5:.2f} mm")
    print(f"Corridor Max Accumulation:        {sum(all_maxs)*0.5:.2f} mm")
    print(f"Single Max Pixel (Fixed Cell):    {grid_acc_corridor.max():.2f} mm")
    print(f"Mumbai Intersecting Max Cell:     {max(c[4] for c in mumbai_cells):.2f} mm")
    print(f"Mumbai Intersecting Mean Cell:    {np.mean([c[4] for c in mumbai_cells]):.2f} mm")
    print(f"Peak Hourly Rate in Corridor:     {max(all_maxs):.2f} mm/hr")
    print(f"Peak Hourly Rate in Mumbai Core:  {max(all_mumbai_maxs):.2f} mm/hr")

    # Also: Representative table requested:
    # timestamp | raw value | interpreted mm/hr | timestep | accumulated mm
    print("\n" + "=" * 115)
    print("REPRESENTATIVE PERIOD TABLE AROUND JULY 8 PEAK (01:00 to 07:00 IST / 19:30 July 7 to 01:30 July 8 UTC):")
    print("=" * 115)
    print(f"{'timestamp (UTC)':<20} | {'raw corridor':<14} | {'interpreted mm/h':<18} | {'timestep (hr)':<15} | {'step_mm':<10} | {'accum_mm (mean)':<16} | {'accum_mm (max_pix)':<18}")
    print("-" * 115)

    accum_mean = 0.0
    accum_max = 0.0
    for r in rows:
        t = r["observation_time"]
        raw_m = r["mumbai_core_mean_value"] or 0.0
        raw_max = r["mumbai_core_max_value"] or 0.0
        step_m = raw_m * 0.5
        step_max = raw_max * 0.5
        accum_mean += step_m
        accum_max += step_max

        # Show timestamps between 18:00 UTC July 7 and 04:00 UTC July 8 (the heavy rain period)
        if datetime(2024, 7, 7, 18, 0, tzinfo=timezone.utc) <= t <= datetime(2024, 7, 8, 4, 0, tzinfo=timezone.utc):
            t_str = t.strftime("%Y-%m-%d %H:%M")
            print(f"{t_str:<20} | {r['mean_value']:>10.2f} mm/h | {raw_m:>14.2f} mm/h | {'0.5':>15} | {step_m:>7.2f} mm | {accum_mean:>13.2f} mm | {accum_max:>15.2f} mm")

    print("-" * 115)
    await conn.close()


if __name__ == "__main__":
    asyncio.run(run_audit())
