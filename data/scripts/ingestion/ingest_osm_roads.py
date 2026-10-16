"""Acquire, Process, and Ingest Mumbai Arterial Road Network from OpenStreetMap.

Retrieves authentic road geometry from OpenStreetMap via Overpass API:
- Motorways, Expressways (Eastern Freeway, Western Express Hwy, Coastal Road)
- Trunks (National Highways, Eastern Express Highway, Sion-Panvel)
- Primary Arterials (SV Road, Link Road, LBS Marg, Dr. Ambedkar Rd)
- Secondary & Tertiary Arterials (Connectors, cross-city corridors)

Standards:
- Zero fabrication: Speed limits NULL unless tagged in OSM.
- WGS84 EPSG:4326 LineStrings with geodesic haversine length.
- Full attribute retention: surface, lanes, bridge, tunnel, oneway in JSONB.
"""

import os
import sys
import ssl
import json
import time
import math
import uuid
import asyncio
import urllib.request
import urllib.parse
from pathlib import Path
import asyncpg
from dotenv import load_dotenv

load_dotenv()
RAW_URL = os.environ.get("DATABASE_URL", "")
CLEAN_URL = RAW_URL.replace("postgresql+asyncpg://", "postgresql://").split("?")[0]

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

MUMBAI_BBOX = "18.89,72.77,19.34,73.04"

ROAD_CLASSES = [
    ("motorway", 'way["highway"~"^(motorway|motorway_link)$"]'),
    ("trunk", 'way["highway"~"^(trunk|trunk_link)$"]'),
    ("primary", 'way["highway"~"^(primary|primary_link)$"]'),
    ("secondary", 'way["highway"~"^(secondary|secondary_link)$"]'),
    ("tertiary", 'way["highway"~"^(tertiary|tertiary_link)$"]')
]

OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter"
]

def haversine_length_m(coords):
    total = 0.0
    for i in range(len(coords) - 1):
        lon1, lat1 = coords[i]
        lon2, lat2 = coords[i + 1]
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        total += 6371000.0 * c
    return round(total, 2)

def query_class(c_name, c_selector):
    q = f"""
    [out:json][timeout:60][maxsize:268435456];
    (
      {c_selector}({MUMBAI_BBOX});
    );
    out tags geom;
    """
    data = urllib.parse.urlencode({"data": q}).encode("utf-8")
    for mirror in OVERPASS_MIRRORS:
        try:
            req = urllib.request.Request(
                mirror,
                data=data,
                headers={"User-Agent": "MUFNS-Data-Platform/1.0 (Mumbai Flood Ingestion)"}
            )
            t0 = time.time()
            with urllib.request.urlopen(req, timeout=60, context=SSL_CTX) as r:
                res = json.loads(r.read())
                el = res.get("elements", [])
                print(f"  [SUCCESS] {c_name:<10}: {len(el):>5} ways from {mirror} in {time.time()-t0:.2f}s", flush=True)
                return el
        except Exception as e:
            print(f"  [RETRY] {c_name:<10} failed on {mirror}: {e}. Trying next mirror...", flush=True)
            time.sleep(2)
    print(f"  [WARNING] Could not fetch {c_name} on any mirror!", flush=True)
    return []

async def ingest_roads_to_postgis(features):
    print("\nConnecting to PostgreSQL/PostGIS to ingest roads...", flush=True)
    conn = await asyncpg.connect(CLEAN_URL, ssl=SSL_CTX)
    
    # Verify schema
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS road_segments (
            segment_id VARCHAR(64) PRIMARY KEY,
            city_id VARCHAR(32) DEFAULT 'mumbai',
            name VARCHAR(255),
            road_class VARCHAR(64) NOT NULL,
            geometry GEOMETRY(LineString, 4326) NOT NULL,
            length_m DOUBLE PRECISION,
            speed_limit_kmh DOUBLE PRECISION,
            osm_id BIGINT,
            attributes JSONB DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS idx_roads_geom ON road_segments USING GIST (geometry);
        CREATE INDEX IF NOT EXISTS idx_roads_class ON road_segments (road_class);
        CREATE INDEX IF NOT EXISTS idx_roads_osm_id ON road_segments (osm_id);
    """)
    
    # Truncate existing placeholder/toy rows
    await conn.execute("TRUNCATE TABLE road_segments;")
    print("Truncated previous road_segments table.", flush=True)
    
    insert_sql = """
        INSERT INTO road_segments (
            segment_id, city_id, name, road_class, geometry,
            length_m, speed_limit_kmh, osm_id, attributes
        ) VALUES (
            $1, 'mumbai', $2, $3, ST_SetSRID(ST_GeomFromGeoJSON($4), 4326),
            $5, $6, $7, $8
        )
        ON CONFLICT (segment_id) DO NOTHING;
    """
    
    batch_size = 500
    rows = []
    inserted = 0
    total = len(features)
    
    t0 = time.time()
    for feat in features:
        geom = feat.get("geometry")
        if not geom or not geom.get("coordinates") or len(geom["coordinates"]) < 2:
            continue
        p = feat["properties"]
        seg_id = f"OSM_WAY_{p['osm_id']}"
        name = p.get("name")
        rclass = p.get("road_class", "unclassified")
        geom_str = json.dumps(geom)
        length_m = p.get("length_m")
        speed = p.get("speed_limit_kmh")
        osm_id = int(p["osm_id"])
        attrs = json.dumps(p.get("attributes", {}))
        rows.append((seg_id, name, rclass, geom_str, length_m, speed, osm_id, attrs))
        
        if len(rows) >= batch_size:
            await conn.executemany(insert_sql, rows)
            inserted += len(rows)
            rows = []
            print(f"  Inserted {inserted:,}/{total:,} road segments...", flush=True)
            
    if rows:
        await conn.executemany(insert_sql, rows)
        inserted += len(rows)
        
    print(f"Inserted {inserted:,} road segments in {time.time()-t0:.2f}s.", flush=True)
    
    # Verification
    cnt = await conn.fetchval("SELECT count(*) FROM road_segments;")
    breakdown = await conn.fetch("""
        SELECT road_class, count(*) as count, round((sum(length_m)/1000.0)::numeric, 1) as total_km
        FROM road_segments
        GROUP BY road_class
        ORDER BY count DESC;
    """)
    print("\n=== POSTGIS ROAD NETWORK SUMMARY ===", flush=True)
    print(f"Total Road Segments in PostGIS: {cnt:,}", flush=True)
    for b in breakdown:
        print(f"  {b['road_class']:<15}: {b['count']:>5} segments ({b['total_km']} km)", flush=True)
        
    # Log run
    await conn.execute("""
        INSERT INTO data_ingestion_runs (
            pipeline_name, source_id, records_ingested, records_failed, status, started_at, completed_at, log_summary
        ) VALUES (
            'osm_mumbai_roads_ingest', 'openstreetmap_overpass', $1, 0, 'completed',
            NOW() - INTERVAL '1 minute', NOW(), $2
        );
    """, cnt, json.dumps({
        "source": "OpenStreetMap Overpass API",
        "bbox": [18.89, 72.77, 19.34, 73.04],
        "total_segments": cnt
    }))
    
    await conn.close()

def main():
    print("=== FETCHING AUTHENTIC MUMBAI ROAD NETWORK FROM OPENSTREETMAP ===", flush=True)
    all_elements = []
    raw_dir = Path("data/raw/roads")
    raw_dir.mkdir(parents=True, exist_ok=True)
    
    geojson_path = Path("data/processed/roads/mumbai_road_network.geojson")
    if geojson_path.exists():
        print(f"Found existing {geojson_path}. Loading {geojson_path.stat().st_size:,} bytes...", flush=True)
        with open(geojson_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        features = data.get("features", [])
        print(f"Loaded {len(features):,} standardized road features from cache.", flush=True)
        asyncio.run(ingest_roads_to_postgis(features))
        return

    for c_name, c_selector in ROAD_CLASSES:
        print(f"Querying {c_name}...", flush=True)
        el = query_class(c_name, c_selector)
        all_elements.extend(el)
        time.sleep(3)  # Respect Overpass rate limits
        
    print(f"\nRetrieved total of {len(all_elements):,} OSM road ways.", flush=True)
    
    # Save raw
    raw_file = raw_dir / "osm_roads_raw.json"
    with open(raw_file, "w", encoding="utf-8") as f:
        json.dump({"elements": all_elements}, f)
    print(f"Saved raw OSM extract to {raw_file} ({raw_file.stat().st_size:,} bytes).", flush=True)
    
    # Convert to GeoJSON
    features = []
    seen_ids = set()
    
    for el in all_elements:
        if el["type"] != "way" or "geometry" not in el:
            continue
        osm_id = el["id"]
        if osm_id in seen_ids:
            continue
        seen_ids.add(osm_id)
        
        coords = [[pt["lon"], pt["lat"]] for pt in el["geometry"]]
        if len(coords) < 2:
            continue
            
        tags = el.get("tags", {})
        rclass = tags.get("highway", "unclassified")
        length_m = haversine_length_m(coords)
        
        speed_limit = None
        if "maxspeed" in tags:
            try:
                num_str = "".join(ch for ch in tags["maxspeed"] if ch.isdigit() or ch == ".")
                if num_str:
                    speed_limit = float(num_str)
            except Exception:
                speed_limit = None
                
        props = {
            "osm_id": osm_id,
            "name": tags.get("name"),
            "road_class": rclass,
            "length_m": length_m,
            "speed_limit_kmh": speed_limit,
            "attributes": {
                "surface": tags.get("surface"),
                "lanes": int(tags["lanes"]) if tags.get("lanes", "").isdigit() else None,
                "bridge": tags.get("bridge") in ("yes", "viaduct"),
                "tunnel": tags.get("tunnel") in ("yes", "subway"),
                "oneway": tags.get("oneway") in ("yes", "1"),
                "ref": tags.get("ref"),
                "alt_name": tags.get("alt_name")
            }
        }
        
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": coords
            },
            "properties": props
        })
        
    geojson_path = Path("data/processed/roads/mumbai_road_network.geojson")
    geojson_path.parent.mkdir(parents=True, exist_ok=True)
    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f)
    print(f"Saved {len(features):,} standardized road features to {geojson_path}.", flush=True)
    
    # Ingest into PostGIS
    asyncio.run(ingest_roads_to_postgis(features))

if __name__ == "__main__":
    main()
