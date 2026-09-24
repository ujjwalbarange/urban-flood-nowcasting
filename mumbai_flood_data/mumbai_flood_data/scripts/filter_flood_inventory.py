#!/usr/bin/env python3
"""
Filter the (national) India Flood Inventory v3 and NDEM flood-inundation datasets down
to Maharashtra / Mumbai, after downloading them with scripts/download_flood_observations.sh.
"""
import geopandas as gpd

MUMBAI_BBOX = (72.70, 18.80, 73.05, 19.35)  # west, south, east, north (with generous buffer)

for src, out in [
    ("../08_flood_observations/historical_events/INDIA_FLOOD_INVENTORY_V3.geojson",
     "../08_flood_observations/flood_polygons.geojson"),
    ("../08_flood_observations/historical_events/NDEM_All_India_Flood_Innundation_1998_to_2022.geojson",
     "../08_flood_observations/flood_points.geojson"),  # rename appropriately - these are polygons too
]:
    try:
        gdf = gpd.read_file(src)
        clipped = gdf.cx[MUMBAI_BBOX[0]:MUMBAI_BBOX[2], MUMBAI_BBOX[1]:MUMBAI_BBOX[3]]
        clipped.to_file(out, driver="GeoJSON")
        print(f"{src}: {len(gdf)} -> {len(clipped)} features after Mumbai bbox clip -> {out}")
    except Exception as e:
        print(f"Skipped {src}: {e} (download it first)")
