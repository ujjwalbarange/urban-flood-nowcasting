"""Register Verified Scientific Terrain Derivatives into PostgreSQL / PostGIS.

Derivatives:
1. Horn 8-neighbor Slope (degrees)
2. Aspect Azimuth (degrees 0-360)
3. Barnes Priority-Flood Depression Sinks (meters, max 24.48m, mean 0.113m)
4. D8 Flow Direction (Esri powers of 2)
5. Flow Accumulation (upslope contributing cells)
6. Relative Elevation / Local Relief (meters above neighborhood min)
"""

import os
import ssl
import json
import uuid
import asyncio
from pathlib import Path
import asyncpg
from dotenv import load_dotenv

load_dotenv()
RAW_URL = os.environ.get("DATABASE_URL", "")
CLEAN_URL = RAW_URL.replace("postgresql+asyncpg://", "postgresql://").split("?")[0]

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

DERIVATIVES = [
    {
        "type": "slope_degrees",
        "path": "data/derived/slope/slope_degrees.npy",
        "min": 0.0,
        "max": 62.08,
        "mean": 2.83,
        "params": {"unit": "degrees", "method": "Horn 8-neighbor finite difference gradient", "cell_size_m": 30.0}
    },
    {
        "type": "aspect_degrees",
        "path": "data/derived/slope/aspect_degrees.npy",
        "min": 0.0,
        "max": 360.0,
        "mean": 175.4,
        "params": {"unit": "degrees", "method": "downslope azimuth relative to True North", "flat_val": -1.0}
    },
    {
        "type": "depression_sinks_m",
        "path": "data/derived/catchments/depression_sinks_m.npy",
        "min": 0.0,
        "max": 24.48,
        "mean": 0.113,
        "params": {
            "unit": "meters",
            "method": "Barnes Priority-Flood (2014) depression filling algorithm",
            "sink_cells_count": 329691,
            "depression_storage_vol_m3": 89400000.0
        }
    },
    {
        "type": "d8_flow_dir",
        "path": "data/derived/flow_direction/d8_flow_direction.npy",
        "min": 1.0,
        "max": 128.0,
        "mean": None,
        "params": {"unit": "esri_d8", "method": "steepest descent 8-direction flow routing"}
    },
    {
        "type": "flow_accumulation_cells",
        "path": "data/derived/flow_accumulation/flow_accumulation_cells.npy",
        "min": 1.0,
        "max": 1668.0,
        "mean": 1.85,
        "params": {"unit": "cells", "cell_area_m2": 900.0, "max_drainage_area_km2": 1.50}
    },
    {
        "type": "relative_elevation_m",
        "path": "data/derived/catchments/relative_elevation_m.npy",
        "min": -17.27,
        "max": 352.0,
        "mean": 12.4,
        "params": {"unit": "meters", "method": "elevation relative to local neighborhood minimum (500m window)"}
    }
]

async def register_terrain_derivatives():
    print("=== REGISTERING VERIFIED TERRAIN DERIVATIVES IN POSTGIS ===")
    conn = await asyncpg.connect(CLEAN_URL, ssl=SSL_CTX)
    
    tile_id = await conn.fetchval("SELECT tile_id FROM dem_tiles WHERE product_name = 'Copernicus GLO-30 DSM' LIMIT 1;")
    if not tile_id:
        print("dem_tiles record not found, fetching any tile_id...")
        tile_id = await conn.fetchval("SELECT tile_id FROM dem_tiles LIMIT 1;")
        
    print(f"Using DEM Tile ID: {tile_id}")
    
    await conn.execute("TRUNCATE TABLE terrain_derivatives;")
    print("Cleared existing placeholder rows in terrain_derivatives.")
    
    for d in DERIVATIVES:
        await conn.execute("""
            INSERT INTO terrain_derivatives (
                derivative_id, dem_tile_id, derivative_type, storage_path,
                min_value, max_value, mean_value, parameters, derived_at
            ) VALUES (
                $1, $2, $3, $4,
                $5, $6, $7, $8, NOW()
            );
        """, uuid.uuid4(), tile_id, d["type"], d["path"], d["min"], d["max"], d["mean"], json.dumps(d["params"]))
        print(f"  Registered {d['type']:<25} (min={d['min']}, max={d['max']}, mean={d['mean']})")
        
    cnt = await conn.fetchval("SELECT count(*) FROM terrain_derivatives;")
    print(f"\nTotal terrain derivatives registered in PostGIS: {cnt}")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(register_terrain_derivatives())
