"""OpenStreetMap Ingestion for Mumbai Water Bodies, Drainage Nullahs, Railways & Critical Assets.

Queries OpenStreetMap via Overpass API within Greater Mumbai bounding box:
(18.89, 72.77, 19.30, 73.00)

Extracts:
1. Rivers, nullahs, canals, streams (Mithi, Poisar, Oshiwara, Dahisar)
2. Water bodies, lakes, reservoirs (Powai Lake, Vihar Lake, Tulsi Lake)
3. Railway transit corridors (Western, Central, Harbour lines)
4. Critical infrastructure (hospitals, fire stations, substations)

Saves raw OSM JSON in data/raw/
Converts into standardized GeoJSON in data/processed/
"""

import os
import sys
import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

OVERPASS_ENDPOINTS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]
BBOX = "18.89,72.77,19.30,73.00"

def query_overpass(query_str):
    last_err = None
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            req = urllib.request.Request(
                endpoint,
                data=urllib.parse.urlencode({"data": query_str}).encode("utf-8"),
                headers={"User-Agent": "MUFNS-Urban-Flood-Data-Platform/1.0"}
            )
            with urllib.request.urlopen(req, timeout=75) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data
        except Exception as e:
            last_err = e
            print(f"    Mirror {endpoint} returned error: {e}. Trying next mirror...")
            time.sleep(1)
    raise last_err

def osm_elements_to_geojson(elements):
    features = []
    # Build node lookup for ways
    nodes = {}
    for el in elements:
        if el["type"] == "node":
            nodes[el["id"]] = (el["lon"], el["lat"])
            
    for el in elements:
        tags = el.get("tags", {})
        if el["type"] == "node":
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [el["lon"], el["lat"]]
                },
                "properties": {
                    "osm_id": el["id"],
                    "osm_type": "node",
                    **tags
                }
            })
        elif el["type"] == "way":
            coords = []
            if "geometry" in el:
                coords = [[pt["lon"], pt["lat"]] for pt in el["geometry"]]
            elif "nodes" in el:
                coords = [nodes[nid] for nid in el["nodes"] if nid in nodes]
                
            if len(coords) >= 2:
                # Check if closed polygon
                is_closed = coords[0] == coords[-1] and len(coords) >= 4
                geom_type = "Polygon" if is_closed and any(k in tags for k in ["natural", "water", "building", "landuse", "amenity"]) else "LineString"
                geom = {
                    "type": geom_type,
                    "coordinates": [coords] if geom_type == "Polygon" else coords
                }
                features.append({
                    "type": "Feature",
                    "geometry": geom,
                    "properties": {
                        "osm_id": el["id"],
                        "osm_type": "way",
                        **tags
                    }
                })
                
    return {
        "type": "FeatureCollection",
        "features": features
    }

def main():
    print("=== INGESTING OPENSTREETMAP DATA FOR MUMBAI ===")
    
    # 1. WATERWAYS & WATER BODIES
    print("\n1. Querying Mumbai Waterways, Rivers & Nullahs...")
    query_water = f"""
    [out:json][timeout:35];
    (
      way["waterway"~"river|canal|stream|drain"]({BBOX});
      way["natural"="water"]({BBOX});
    );
    out tags geom;
    """
    try:
        data_water = query_overpass(query_water)
        raw_water_file = Path("data/raw/rivers/osm_waterways_raw.json")
        raw_water_file.parent.mkdir(parents=True, exist_ok=True)
        with open(raw_water_file, "w", encoding="utf-8") as f:
            json.dump(data_water, f, indent=2)
            
        geojson_water = osm_elements_to_geojson(data_water.get("elements", []))
        proc_water_file = Path("data/processed/rivers/mumbai_waterways.geojson")
        proc_water_file.parent.mkdir(parents=True, exist_ok=True)
        with open(proc_water_file, "w", encoding="utf-8") as f:
            json.dump(geojson_water, f, indent=2)
            
        print(f"  Extracted {len(geojson_water['features'])} waterway & water body features -> {proc_water_file}")
    except Exception as e:
        print(f"  Waterway query failed: {e}")
        
    time.sleep(2)
    
    # 2. RAILWAY TRANSIT NETWORK (CRITICAL IN MUMBAI FOR FLOOD IMPACT)
    print("\n2. Querying Mumbai Railway Network & Stations...")
    query_rail = f"""
    [out:json][timeout:35];
    (
      way["railway"="rail"]({BBOX});
      node["railway"="station"]({BBOX});
    );
    out tags geom;
    """
    try:
        data_rail = query_overpass(query_rail)
        raw_rail_file = Path("data/raw/roads/osm_railways_raw.json")
        with open(raw_rail_file, "w", encoding="utf-8") as f:
            json.dump(data_rail, f, indent=2)
            
        geojson_rail = osm_elements_to_geojson(data_rail.get("elements", []))
        proc_rail_file = Path("data/processed/roads/mumbai_railways.geojson")
        with open(proc_rail_file, "w", encoding="utf-8") as f:
            json.dump(geojson_rail, f, indent=2)
            
        print(f"  Extracted {len(geojson_rail['features'])} railway tracks & stations -> {proc_rail_file}")
    except Exception as e:
        print(f"  Railway query failed: {e}")
        
    time.sleep(2)
    
    # 3. CRITICAL EMERGENCY INFRASTRUCTURE (HOSPITALS & FIRE STATIONS)
    print("\n3. Querying Mumbai Hospitals, Fire Stations & Emergency Assets...")
    query_infra = f"""
    [out:json][timeout:35];
    (
      node["amenity"~"hospital|clinic|fire_station|police"]({BBOX});
      way["amenity"~"hospital|clinic|fire_station|police"]({BBOX});
    );
    out tags geom;
    """
    try:
        data_infra = query_overpass(query_infra)
        raw_infra_file = Path("data/raw/critical_infrastructure/osm_emergency_raw.json")
        with open(raw_infra_file, "w", encoding="utf-8") as f:
            json.dump(data_infra, f, indent=2)
            
        geojson_infra = osm_elements_to_geojson(data_infra.get("elements", []))
        proc_infra_file = Path("data/processed/critical_infrastructure/mumbai_emergency_facilities.geojson")
        with open(proc_infra_file, "w", encoding="utf-8") as f:
            json.dump(geojson_infra, f, indent=2)
            
        print(f"  Extracted {len(geojson_infra['features'])} emergency infrastructure facilities -> {proc_infra_file}")
    except Exception as e:
        print(f"  Emergency infrastructure query failed: {e}")

if __name__ == "__main__":
    main()
